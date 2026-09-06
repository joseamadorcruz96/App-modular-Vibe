"""
Capa de Servicio Transaccional para la Emisión de Comandas, Checkout y Tickets.

Implementa la regla de negocio crítica: verificación y descuento atómico de stock (ACID).
Soporta doble modalidad:
- Todos los productos descuentan su stock actual en catálogo.
- Si el producto tiene receta (escandallo), descuenta ADEMÁS atómicamente los insumos correspondientes.
Si un solo producto o insumo carece de existencias, la operación completa se aborta con ROLLBACK.
"""

import sqlite3
import datetime
from typing import Dict, Any, Optional, List
from app.models.schemas import PedidoCreate, ItemPedidoCreate, ComandaCheckout


class StockInsuficienteError(Exception):
    """Excepción de regla de negocio lanzada cuando no hay existencias para cubrir la comanda."""

    def __init__(
        self,
        item_id: int,
        item_nombre: str,
        solicitado: float,
        disponible: float,
        unidad: str = "unidades"
    ):
        self.item_id = item_id
        self.item_nombre = item_nombre
        self.producto_id = item_id
        self.producto_nombre = item_nombre
        self.solicitado = solicitado
        self.disponible = disponible
        self.unidad = unidad
        super().__init__(
            f"Stock insuficiente para '{item_nombre}' (ID: {item_id}). "
            f"Solicitado: {solicitado} {unidad}, Disponible: {disponible} {unidad}."
        )


class OrderService:
    """Servicio para procesar pedidos de forma atómica y liquidar comandas."""

    @staticmethod
    def generar_numero_ticket(conn: sqlite3.Connection) -> str:
        """
        Genera un número de ticket correlativo diario en formato TCK-YYYYMMDD-XXXX.
        """
        hoy_str = datetime.date.today().strftime("%Y%m%d")
        prefijo = f"TCK-{hoy_str}-%"

        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(id) FROM pedidos WHERE numero_ticket LIKE ?;",
            (prefijo,)
        )
        conteo_hoy = cursor.fetchone()[0]
        correlativo = conteo_hoy + 1
        return f"TCK-{hoy_str}-{correlativo:04d}"

    @staticmethod
    def procesar_checkout(conn: sqlite3.Connection, pedido_data: PedidoCreate) -> Dict[str, Any]:
        """
        Ejecuta el cobro atómico del pedido:
        1. Valida que cada producto exista, esté activo y cuente con stock suficiente.
        2. Si el producto tiene receta asociada, valida que todos sus insumos tengan stock suficiente.
        3. Si falta cualquier elemento, aborta con StockInsuficienteError (ROLLBACK total).
        4. Descuenta existencias en productos y en insumos (si tiene receta).
        5. Inserta el ticket en `pedidos` y `pedido_detalles`.
        """
        cursor = conn.cursor()

        # Agrupar cantidades de productos solicitados
        cantidades_solicitadas: Dict[int, int] = {}
        for item in pedido_data.items:
            cantidades_solicitadas[item.producto_id] = (
                cantidades_solicitadas.get(item.producto_id, 0) + item.cantidad
            )

        items_procesados = []
        total_calculado = 0.0

        # Mapeo de insumos totales requeridos: {insumo_id: {info, total_necesario}}
        insumos_requeridos: Dict[int, Dict[str, Any]] = {}

        # Paso 1: Inspeccionar cada producto en catálogo
        for prod_id, cant_requerida in cantidades_solicitadas.items():
            cursor.execute(
                """
                SELECT id, codigo, nombre, stock_actual, precio_venta, activo
                FROM productos
                WHERE id = ?;
                """,
                (prod_id,)
            )
            prod_row = cursor.fetchone()

            if not prod_row:
                raise ValueError(f"El producto con ID {prod_id} no existe en el catálogo.")

            if prod_row["activo"] != 1:
                raise ValueError(f"El producto '{prod_row['nombre']}' se encuentra deshabilitado.")

            # Validación de stock del producto
            if prod_row["stock_actual"] < cant_requerida:
                raise StockInsuficienteError(
                    item_id=prod_id,
                    item_nombre=prod_row["nombre"],
                    solicitado=cant_requerida,
                    disponible=prod_row["stock_actual"],
                    unidad="unidades"
                )

            # Consultar si el producto tiene receta (insumos requeridos)
            cursor.execute(
                """
                SELECT rd.insumo_id, i.codigo, i.nombre, i.unidad_medida, i.stock_actual,
                       i.activo, rd.cantidad as cant_por_porcion
                FROM receta_detalles rd
                JOIN insumos i ON rd.insumo_id = i.id
                WHERE rd.producto_id = ?;
                """,
                (prod_id,)
            )
            receta_rows = cursor.fetchall()

            for r in receta_rows:
                if r["activo"] != 1:
                    raise ValueError(
                        f"El insumo '{r['nombre']}' necesario para '{prod_row['nombre']}' está inactivo."
                    )
                insumo_id = r["insumo_id"]
                necesario = r["cant_por_porcion"] * cant_requerida

                if insumo_id not in insumos_requeridos:
                    insumos_requeridos[insumo_id] = {
                        "id": insumo_id,
                        "nombre": r["nombre"],
                        "unidad_medida": r["unidad_medida"],
                        "stock_actual": r["stock_actual"],
                        "total_solicitado": 0.0
                    }
                insumos_requeridos[insumo_id]["total_solicitado"] += necesario

            subtotal_linea = float(prod_row["precio_venta"]) * cant_requerida
            total_calculado += subtotal_linea

            items_procesados.append({
                "producto_id": prod_id,
                "codigo": prod_row["codigo"],
                "nombre": prod_row["nombre"],
                "cantidad": cant_requerida,
                "precio_unitario": float(prod_row["precio_venta"]),
                "subtotal": subtotal_linea
            })

        # Paso 2: Validación previa de todos los insumos acumulados
        for insumo_id, ins_data in insumos_requeridos.items():
            if ins_data["stock_actual"] < ins_data["total_solicitado"]:
                raise StockInsuficienteError(
                    item_id=insumo_id,
                    item_nombre=ins_data["nombre"],
                    solicitado=ins_data["total_solicitado"],
                    disponible=ins_data["stock_actual"],
                    unidad=ins_data["unidad_medida"]
                )

        # Paso 3: Descuento atómico de existencias
        # A) Descontar productos
        for prod_id, cant in cantidades_solicitadas.items():
            cursor.execute(
                """
                UPDATE productos
                SET stock_actual = stock_actual - ?,
                    actualizado_en = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (cant, prod_id)
            )

        # B) Descontar insumos (si aplica)
        for insumo_id, ins_data in insumos_requeridos.items():
            cursor.execute(
                """
                UPDATE insumos
                SET stock_actual = stock_actual - ?,
                    actualizado_en = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (ins_data["total_solicitado"], insumo_id)
            )

        # Paso 4: Inserción de cabecera de pedido
        numero_ticket = OrderService.generar_numero_ticket(conn)
        fecha_hora_local = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            INSERT INTO pedidos (numero_ticket, fecha_hora, mesa, cliente, medio_pago, subtotal, descuento, total, estado)
            VALUES (?, ?, ?, ?, ?, ?, 0.0, ?, 'Completado');
            """,
            (
                numero_ticket,
                fecha_hora_local,
                pedido_data.mesa,
                pedido_data.cliente or "Consumidor Final",
                pedido_data.medio_pago,
                total_calculado,
                total_calculado
            )
        )
        pedido_id = cursor.lastrowid

        # Paso 5: Inserción de líneas de ticket
        for item in items_procesados:
            cursor.execute(
                """
                INSERT INTO pedido_detalles (pedido_id, producto_id, cantidad, precio_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?);
                """,
                (
                    pedido_id,
                    item["producto_id"],
                    item["cantidad"],
                    item["precio_unitario"],
                    item["subtotal"]
                )
            )

        cursor.execute("SELECT fecha_hora FROM pedidos WHERE id = ?;", (pedido_id,))
        fecha_hora = cursor.fetchone()["fecha_hora"]

        return {
            "id": pedido_id,
            "numero_ticket": numero_ticket,
            "fecha_hora": str(fecha_hora),
            "mesa": pedido_data.mesa,
            "cliente": pedido_data.cliente or "Consumidor Final",
            "medio_pago": pedido_data.medio_pago,
            "subtotal": total_calculado,
            "descuento": 0.0,
            "total": total_calculado,
            "estado": "Completado",
            "detalles": items_procesados
        }

    @staticmethod
    def procesar_checkout_comanda(
        conn: sqlite3.Connection,
        comanda_id: int,
        checkout_data: ComandaCheckout
    ) -> Dict[str, Any]:
        """
        Liquida una comanda abierta de salón:
        1. Consulta los consumos acumulados en la comanda.
        2. Procesa el cobro y descuenta el inventario mediante procesar_checkout.
        3. Cierra la comanda ('Cobrada') y la asocia al número de pedido emitido.
        """
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, mesa, cliente, estado FROM comandas WHERE id = ?;",
            (comanda_id,)
        )
        comanda = cursor.fetchone()
        if not comanda:
            cursor.close()
            raise ValueError(f"Comanda ID {comanda_id} no encontrada.")
        if comanda["estado"] != "Abierta":
            cursor.close()
            raise ValueError(f"La comanda no está abierta (Estado actual: '{comanda['estado']}').")

        # Obtener ítems de la comanda
        cursor.execute(
            "SELECT producto_id, cantidad FROM comanda_detalles WHERE comanda_id = ?;",
            (comanda_id,)
        )
        detalles = cursor.fetchall()
        if not detalles:
            cursor.close()
            raise ValueError("No se puede cobrar una comanda sin productos agregados.")

        # Construir pedido equivalente
        items_pedido = [
            ItemPedidoCreate(producto_id=d["producto_id"], cantidad=d["cantidad"])
            for d in detalles
        ]
        pedido_create = PedidoCreate(
            mesa=comanda["mesa"],
            cliente=comanda["cliente"],
            medio_pago=checkout_data.medio_pago,
            items=items_pedido
        )

        # Ejecutar cobro atómico
        resultado_pedido = OrderService.procesar_checkout(conn, pedido_create)

        # Actualizar comanda a Cobrada
        cursor.execute(
            """
            UPDATE comandas
            SET estado = 'Cobrada',
                pedido_id = ?,
                cerrado_en = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (resultado_pedido["id"], comanda_id)
        )
        cursor.close()

        resultado_pedido["comanda_id"] = comanda_id
        return resultado_pedido

    @staticmethod
    def obtener_pedido_por_id(conn: sqlite3.Connection, pedido_id: int) -> Optional[Dict[str, Any]]:
        """Recupera el pedido completo con sus líneas de detalle."""
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, numero_ticket, fecha_hora, mesa, cliente, medio_pago,
                   subtotal, descuento, total, estado
            FROM pedidos
            WHERE id = ?;
            """,
            (pedido_id,)
        )
        cabecera = cursor.fetchone()
        if not cabecera:
            return None

        pedido_dict = dict(cabecera)
        cursor.execute(
            """
            SELECT d.producto_id, p.codigo, p.nombre, d.cantidad, d.precio_unitario, d.subtotal
            FROM pedido_detalles d
            JOIN productos p ON d.producto_id = p.id
            WHERE d.pedido_id = ?;
            """,
            (pedido_id,)
        )
        lineas = [dict(row) for row in cursor.fetchall()]
        pedido_dict["detalles"] = lineas
        return pedido_dict
