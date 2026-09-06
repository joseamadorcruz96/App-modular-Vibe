"""
Módulo de Servicios para Gestión de Comandas de Salón (Mesas Abiertas).

Permite aperturar mesas, acumular rondas de consumo a lo largo de la jornada,
consultar el estado de ocupación del salón y cancelar comandas.
"""

import sqlite3
import datetime
from typing import List, Optional, Dict, Any

from app.models.schemas import (
    ComandaCreate,
    ComandaItemAdd,
)
from app.services.order_service import OrderService, StockInsuficienteError


class ComandaService:
    """
    Servicio con lógica de negocio desacoplada para comandas de salón.
    
    Gestiona el ciclo de vida de la comanda ('Abierta' -> 'En preparación' -> 'Servida' -> 'Cobrada' / 'Cancelada')
    y de cada ítem consumido ('En preparación' -> 'Servido' -> 'Cancelado').
    Asegura que el stock se descuente exactamente cuando el producto se sirve en mesa,
    evitando doble descuento al momento del pago final y ofreciendo opción de merma en cancelaciones.
    """

    @staticmethod
    def generar_numero_comanda(conn: sqlite3.Connection) -> str:
        """Genera un identificador secuencial diario único (ej: CMD-20260905-001)."""
        hoy = datetime.date.today().strftime("%Y%m%d")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM comandas WHERE numero_comanda LIKE ?;",
            (f"CMD-{hoy}-%",)
        )
        conteo = cursor.fetchone()[0]
        cursor.close()
        return f"CMD-{hoy}-{(conteo + 1):03d}"

    @staticmethod
    def listar_estado_mesas(conn: sqlite3.Connection, total_mesas: int) -> List[Dict[str, Any]]:
        """
        Retorna el estado de todas las mesas del salón (1 a N),
        indicando si están Libres u Ocupadas con su subtotal acumulado y estado actual.
        """
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT c.id, c.numero_comanda, c.mesa, c.cliente, c.estado as comanda_estado, c.creado_en,
                   COALESCE(SUM(cd.subtotal), 0.0) as subtotal,
                   COALESCE(SUM(cd.cantidad), 0) as items_count
            FROM comandas c
            LEFT JOIN comanda_detalles cd ON c.id = cd.comanda_id AND cd.estado != 'Cancelado'
            WHERE c.estado IN ('Abierta', 'En preparación', 'Servida')
            GROUP BY c.id;
            """
        )
        filas = cursor.fetchall()
        cursor.close()

        comandas_activas = {f["mesa"]: dict(f) for f in filas}
        resultado = []

        for i in range(1, total_mesas + 1):
            nombre_mesa = f"Mesa {i}"
            if nombre_mesa in comandas_activas:
                c = comandas_activas[nombre_mesa]
                resultado.append({
                    "mesa": nombre_mesa,
                    "ocupada": True,
                    "comanda_id": c["id"],
                    "numero_comanda": c["numero_comanda"],
                    "estado": c["comanda_estado"],
                    "subtotal": round(float(c["subtotal"]), 2),
                    "cliente": c["cliente"],
                    "items_count": int(c["items_count"]),
                    "tiempo_abierta": str(c["creado_en"])
                })
            else:
                resultado.append({
                    "mesa": nombre_mesa,
                    "ocupada": False,
                    "comanda_id": None,
                    "numero_comanda": None,
                    "estado": None,
                    "subtotal": 0.0,
                    "cliente": None,
                    "items_count": 0,
                    "tiempo_abierta": None
                })

        return resultado

    @staticmethod
    def obtener_comanda_por_id(conn: sqlite3.Connection, comanda_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene una comanda y todas sus líneas activas de consumo con estado de servicio y descuento de stock."""
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, numero_comanda, mesa, cliente, estado, pedido_id, creado_en, cerrado_en
            FROM comandas
            WHERE id = ?;
            """,
            (comanda_id,)
        )
        comanda = cursor.fetchone()
        if not comanda:
            cursor.close()
            return None

        cursor.execute(
            """
            SELECT cd.id, cd.producto_id, p.codigo, p.nombre, cd.cantidad,
                   cd.precio_unitario, cd.subtotal, cd.notas, cd.creado_en,
                   cd.estado, cd.descontado_stock, cd.servido_en
            FROM comanda_detalles cd
            JOIN productos p ON cd.producto_id = p.id
            WHERE cd.comanda_id = ? AND cd.estado != 'Cancelado'
            ORDER BY cd.id ASC;
            """,
            (comanda_id,)
        )
        detalles = cursor.fetchall()
        cursor.close()

        lista_detalles = [dict(d) for d in detalles]
        subtotal = round(sum(d["subtotal"] for d in lista_detalles), 2)
        total_items = sum(d["cantidad"] for d in lista_detalles)

        res = dict(comanda)
        res["subtotal"] = subtotal
        res["total_items"] = total_items
        res["detalles"] = lista_detalles
        return res

    @staticmethod
    def obtener_comanda_activa_mesa(conn: sqlite3.Connection, mesa: str) -> Optional[Dict[str, Any]]:
        """Recupera la comanda activa (Abierta, En preparación o Servida) para una mesa determinada."""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM comandas WHERE mesa = ? AND estado IN ('Abierta', 'En preparación', 'Servida');",
            (mesa,)
        )
        fila = cursor.fetchone()
        cursor.close()
        if not fila:
            return None
        return ComandaService.obtener_comanda_por_id(conn, fila["id"])

    @staticmethod
    def abrir_comanda(conn: sqlite3.Connection, data: ComandaCreate) -> Dict[str, Any]:
        """Abre una nueva comanda en una mesa si no tiene comanda activa previa."""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM comandas WHERE mesa = ? AND estado IN ('Abierta', 'En preparación', 'Servida');",
            (data.mesa,)
        )
        existente = cursor.fetchone()
        if existente:
            cursor.close()
            raise ValueError(f"La {data.mesa} ya tiene una comanda abierta (ID {existente['id']}).")

        numero_cmd = ComandaService.generar_numero_comanda(conn)
        cursor.execute(
            """
            INSERT INTO comandas (numero_comanda, mesa, cliente, estado)
            VALUES (?, ?, ?, 'Abierta');
            """,
            (numero_cmd, data.mesa, data.cliente or "Consumidor Final")
        )
        comanda_id = cursor.lastrowid
        cursor.close()

        return ComandaService.obtener_comanda_por_id(conn, comanda_id)  # type: ignore

    @staticmethod
    def agregar_items_comanda(
        conn: sqlite3.Connection,
        comanda_id: int,
        items: List[ComandaItemAdd]
    ) -> Dict[str, Any]:
        """
        Agrega una ronda de productos a una comanda activa.
        Los ítems se crean con estado 'En preparación' y descontado_stock = 0.
        El estado general de la comanda pasa a 'En preparación'.
        """
        cursor = conn.cursor()
        cursor.execute("SELECT id, estado FROM comandas WHERE id = ?;", (comanda_id,))
        comanda = cursor.fetchone()
        if not comanda:
            cursor.close()
            raise ValueError(f"Comanda ID {comanda_id} no encontrada.")
        if comanda["estado"] in ("Cobrada", "Cancelada"):
            cursor.close()
            raise ValueError(f"No se pueden agregar ítems a una comanda con estado '{comanda['estado']}'.")

        for item in items:
            cursor.execute(
                "SELECT id, precio_venta, activo FROM productos WHERE id = ?;",
                (item.producto_id,)
            )
            prod = cursor.fetchone()
            if not prod:
                cursor.close()
                raise ValueError(f"Producto ID {item.producto_id} no existe.")
            if prod["activo"] != 1:
                cursor.close()
                raise ValueError(f"El producto ID {item.producto_id} está inactivo.")

            subtotal = round(prod["precio_venta"] * item.cantidad, 2)
            cursor.execute(
                """
                INSERT INTO comanda_detalles (comanda_id, producto_id, cantidad, precio_unitario, subtotal, notas, estado, descontado_stock)
                VALUES (?, ?, ?, ?, ?, ?, 'En preparación', 0);
                """,
                (comanda_id, item.producto_id, item.cantidad, prod["precio_venta"], subtotal, item.notas)
            )

        # La comanda queda en preparación porque contiene consumos recién enviados a barra/cocina
        cursor.execute(
            "UPDATE comandas SET estado = 'En preparación' WHERE id = ?;",
            (comanda_id,)
        )
        cursor.close()
        return ComandaService.obtener_comanda_por_id(conn, comanda_id)  # type: ignore

    @staticmethod
    def marcar_comanda_servida(conn: sqlite3.Connection, comanda_id: int) -> Dict[str, Any]:
        """
        Marca todos los ítems pendientes de la comanda como 'Servidos'.
        Descuenta atómicamente el stock de productos y recetas asociadas.
        Actualiza el estado general de la comanda a 'Servida'.
        """
        cursor = conn.cursor()
        cursor.execute("SELECT id, estado FROM comandas WHERE id = ?;", (comanda_id,))
        comanda = cursor.fetchone()
        if not comanda:
            cursor.close()
            raise ValueError(f"Comanda ID {comanda_id} no encontrada.")
        if comanda["estado"] in ("Cobrada", "Cancelada"):
            cursor.close()
            raise ValueError(f"No se puede servir una comanda cerrada o cancelada ({comanda['estado']}).")

        # Obtener ítems que aún no hayan descontado stock
        cursor.execute(
            """
            SELECT id, producto_id, cantidad
            FROM comanda_detalles
            WHERE comanda_id = ? AND descontado_stock = 0 AND estado != 'Cancelado';
            """,
            (comanda_id,)
        )
        pendientes = cursor.fetchall()

        if pendientes:
            items_descuento = [
                {"producto_id": row["producto_id"], "cantidad": row["cantidad"]}
                for row in pendientes
            ]
            # Descuento atómico de existencias (productos + recetas)
            OrderService.descontar_stock_items(cursor, items_descuento)

            cursor.execute(
                """
                UPDATE comanda_detalles
                SET estado = 'Servido',
                    descontado_stock = 1,
                    servido_en = CURRENT_TIMESTAMP
                WHERE comanda_id = ? AND descontado_stock = 0 AND estado != 'Cancelado';
                """,
                (comanda_id,)
            )

        cursor.execute(
            "UPDATE comandas SET estado = 'Servida' WHERE id = ?;",
            (comanda_id,)
        )
        cursor.close()
        return ComandaService.obtener_comanda_por_id(conn, comanda_id)  # type: ignore

    @staticmethod
    def marcar_item_servido(conn: sqlite3.Connection, comanda_id: int, detalle_id: int) -> Dict[str, Any]:
        """
        Marca un ítem individual como 'Servido', descontando su stock y el de su receta de inmediato.
        Si todos los ítems de la comanda quedan servidos, la comanda pasa a 'Servida'.
        """
        cursor = conn.cursor()
        cursor.execute("SELECT id, estado FROM comandas WHERE id = ?;", (comanda_id,))
        comanda = cursor.fetchone()
        if not comanda:
            cursor.close()
            raise ValueError(f"Comanda ID {comanda_id} no encontrada.")
        if comanda["estado"] in ("Cobrada", "Cancelada"):
            cursor.close()
            raise ValueError(f"No se puede alterar una comanda en estado '{comanda['estado']}'.")

        cursor.execute(
            """
            SELECT id, producto_id, cantidad, descontado_stock, estado
            FROM comanda_detalles
            WHERE id = ? AND comanda_id = ?;
            """,
            (detalle_id, comanda_id)
        )
        detalle = cursor.fetchone()
        if not detalle or detalle["estado"] == "Cancelado":
            cursor.close()
            raise ValueError(f"Ítem ID {detalle_id} no encontrado en la comanda {comanda_id}.")

        # Si aún no descuenta stock, lo descontamos
        if detalle["descontado_stock"] == 0:
            OrderService.descontar_stock_items(
                cursor,
                [{"producto_id": detalle["producto_id"], "cantidad": detalle["cantidad"]}]
            )
            cursor.execute(
                """
                UPDATE comanda_detalles
                SET estado = 'Servido',
                    descontado_stock = 1,
                    servido_en = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (detalle_id,)
            )

        # Verificar si todos los ítems activos de la comanda están servidos
        cursor.execute(
            """
            SELECT COUNT(*) FROM comanda_detalles
            WHERE comanda_id = ? AND estado != 'Servido' AND estado != 'Cancelado';
            """,
            (comanda_id,)
        )
        pendientes_count = cursor.fetchone()[0]

        nuevo_estado = "Servida" if pendientes_count == 0 else "En preparación"
        cursor.execute(
            "UPDATE comandas SET estado = ? WHERE id = ?;",
            (nuevo_estado, comanda_id)
        )
        cursor.close()
        return ComandaService.obtener_comanda_por_id(conn, comanda_id)  # type: ignore

    @staticmethod
    def eliminar_item_comanda(
        conn: sqlite3.Connection,
        comanda_id: int,
        detalle_id: int,
        restaurar_stock: bool = False
    ) -> Dict[str, Any]:
        """
        Elimina o anula una línea de una comanda activa.
        Si el ítem ya había sido servido (descontado_stock == 1):
        - Por defecto (restaurar_stock=False), se asume merma/desperdicio de alimentos y el stock NO se reintegra.
        - Si restaurar_stock=True, se reincorpora la cantidad al inventario (productos e insumos).
        """
        cursor = conn.cursor()
        cursor.execute("SELECT estado FROM comandas WHERE id = ?;", (comanda_id,))
        comanda = cursor.fetchone()
        if not comanda or comanda["estado"] in ("Cobrada", "Cancelada"):
            cursor.close()
            raise ValueError("Comanda no válida para modificación.")

        cursor.execute(
            "SELECT id, producto_id, cantidad, descontado_stock, estado FROM comanda_detalles WHERE id = ? AND comanda_id = ?;",
            (detalle_id, comanda_id)
        )
        detalle = cursor.fetchone()
        if not detalle:
            cursor.close()
            raise ValueError(f"Ítem ID {detalle_id} no encontrado en la comanda.")

        if detalle["descontado_stock"] == 1 and restaurar_stock:
            OrderService.reintegrar_stock_items(
                cursor,
                [{"producto_id": detalle["producto_id"], "cantidad": detalle["cantidad"]}]
            )

        # Eliminar físicamente la línea para mantener total coherente
        cursor.execute(
            "DELETE FROM comanda_detalles WHERE id = ? AND comanda_id = ?;",
            (detalle_id, comanda_id)
        )

        # Ajustar estado resultante de la comanda
        cursor.execute(
            """
            SELECT COUNT(*),
                   SUM(CASE WHEN estado = 'Servido' THEN 1 ELSE 0 END)
            FROM comanda_detalles
            WHERE comanda_id = ?;
            """,
            (comanda_id,)
        )
        row = cursor.fetchone()
        total_items = row[0] or 0
        servidos = row[1] or 0

        if total_items == 0:
            nuevo_estado = "Abierta"
        elif servidos == total_items:
            nuevo_estado = "Servida"
        else:
            nuevo_estado = "En preparación"

        cursor.execute(
            "UPDATE comandas SET estado = ? WHERE id = ?;",
            (nuevo_estado, comanda_id)
        )
        cursor.close()
        return ComandaService.obtener_comanda_por_id(conn, comanda_id)  # type: ignore

    @staticmethod
    def cancelar_comanda(
        conn: sqlite3.Connection,
        comanda_id: int,
        restaurar_stock: bool = False
    ) -> Dict[str, Any]:
        """
        Cancela una comanda activa y libera la mesa.
        - Si restaurar_stock=False (por defecto para alimentos preparados/servidos):
          se registra como merma y no se reincorpora el stock.
        - Si restaurar_stock=True:
          se devuelven las existencias de todos los ítems servidos al catálogo e insumos.
        """
        cursor = conn.cursor()
        cursor.execute("SELECT estado FROM comandas WHERE id = ?;", (comanda_id,))
        comanda = cursor.fetchone()
        if not comanda:
            cursor.close()
            raise ValueError("Comanda no encontrada.")
        if comanda["estado"] in ("Cobrada", "Cancelada"):
            cursor.close()
            raise ValueError(f"Solo se pueden cancelar comandas activas. Estado actual: {comanda['estado']}.")

        if restaurar_stock:
            cursor.execute(
                """
                SELECT producto_id, cantidad
                FROM comanda_detalles
                WHERE comanda_id = ? AND descontado_stock = 1 AND estado != 'Cancelado';
                """,
                (comanda_id,)
            )
            servidos = cursor.fetchall()
            if servidos:
                items_restaurar = [
                    {"producto_id": r["producto_id"], "cantidad": r["cantidad"]}
                    for r in servidos
                ]
                OrderService.reintegrar_stock_items(cursor, items_restaurar)

        cursor.execute(
            "UPDATE comandas SET estado = 'Cancelada', cerrado_en = CURRENT_TIMESTAMP WHERE id = ?;",
            (comanda_id,)
        )
        cursor.execute(
            "UPDATE comanda_detalles SET estado = 'Cancelado' WHERE comanda_id = ?;",
            (comanda_id,)
        )
        cursor.close()
        return {
            "id": comanda_id,
            "estado": "Cancelada",
            "restaurar_stock": restaurar_stock,
            "mensaje": "Comanda cancelada y mesa liberada."
        }
