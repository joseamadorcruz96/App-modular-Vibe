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


class ComandaService:
    """Servicio con lógica de negocio para comandas de mesas."""

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
        indicando si están Libres u Ocupadas con su subtotal acumulado.
        """
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT c.id, c.numero_comanda, c.mesa, c.cliente, c.creado_en,
                   COALESCE(SUM(cd.subtotal), 0.0) as subtotal,
                   COALESCE(SUM(cd.cantidad), 0) as items_count
            FROM comandas c
            LEFT JOIN comanda_detalles cd ON c.id = cd.comanda_id
            WHERE c.estado = 'Abierta'
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
                    "subtotal": 0.0,
                    "cliente": None,
                    "items_count": 0,
                    "tiempo_abierta": None
                })

        return resultado

    @staticmethod
    def obtener_comanda_por_id(conn: sqlite3.Connection, comanda_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene una comanda y todas sus líneas de consumo."""
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
                   cd.precio_unitario, cd.subtotal, cd.notas, cd.creado_en
            FROM comanda_detalles cd
            JOIN productos p ON cd.producto_id = p.id
            WHERE cd.comanda_id = ?
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
        """Recupera la comanda abierta para una mesa determinada."""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM comandas WHERE mesa = ? AND estado = 'Abierta';",
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
            "SELECT id FROM comandas WHERE mesa = ? AND estado = 'Abierta';",
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
        """Agrega una ronda de productos a una comanda abierta."""
        cursor = conn.cursor()
        cursor.execute("SELECT id, estado FROM comandas WHERE id = ?;", (comanda_id,))
        comanda = cursor.fetchone()
        if not comanda:
            cursor.close()
            raise ValueError(f"Comanda ID {comanda_id} no encontrada.")
        if comanda["estado"] != "Abierta":
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
                INSERT INTO comanda_detalles (comanda_id, producto_id, cantidad, precio_unitario, subtotal, notas)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (comanda_id, item.producto_id, item.cantidad, prod["precio_venta"], subtotal, item.notas)
            )

        cursor.close()
        return ComandaService.obtener_comanda_por_id(conn, comanda_id)  # type: ignore

    @staticmethod
    def eliminar_item_comanda(conn: sqlite3.Connection, comanda_id: int, detalle_id: int) -> Dict[str, Any]:
        """Elimina una línea individual de una comanda abierta."""
        cursor = conn.cursor()
        cursor.execute("SELECT estado FROM comandas WHERE id = ?;", (comanda_id,))
        comanda = cursor.fetchone()
        if not comanda or comanda["estado"] != "Abierta":
            cursor.close()
            raise ValueError("Comanda no válida para modificación.")

        cursor.execute(
            "DELETE FROM comanda_detalles WHERE id = ? AND comanda_id = ?;",
            (detalle_id, comanda_id)
        )
        cursor.close()
        return ComandaService.obtener_comanda_por_id(conn, comanda_id)  # type: ignore

    @staticmethod
    def cancelar_comanda(conn: sqlite3.Connection, comanda_id: int) -> Dict[str, Any]:
        """Cancela una comanda abierta sin generar cobro ni alterar existencias."""
        cursor = conn.cursor()
        cursor.execute("SELECT estado FROM comandas WHERE id = ?;", (comanda_id,))
        comanda = cursor.fetchone()
        if not comanda:
            cursor.close()
            raise ValueError("Comanda no encontrada.")
        if comanda["estado"] != "Abierta":
            cursor.close()
            raise ValueError(f"Solo se pueden cancelar comandas abiertas. Estado actual: {comanda['estado']}.")

        cursor.execute(
            "UPDATE comandas SET estado = 'Cancelada', cerrado_en = CURRENT_TIMESTAMP WHERE id = ?;",
            (comanda_id,)
        )
        cursor.close()
        return {"id": comanda_id, "estado": "Cancelada", "mensaje": "Comanda cancelada y mesa liberada."}
