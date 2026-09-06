"""
Capa de Servicio Transaccional para la Emisión de Comandas, Checkout y Tickets.

Implementa la regla de negocio crítica: verificación y descuento atómico de stock (ACID).
Si un solo producto del pedido no cuenta con existencias suficientes, la operación completa
se aborta con ROLLBACK garantizado a nivel de base de datos.
"""

import sqlite3
import datetime
from typing import Dict, Any, Optional
from app.models.schemas import PedidoCreate


class StockInsuficienteError(Exception):
    """Excepción de regla de negocio lanzada cuando no hay existencias para cubrir la comanda."""

    def __init__(self, producto_id: int, producto_nombre: str, solicitado: int, disponible: int):
        self.producto_id = producto_id
        self.producto_nombre = producto_nombre
        self.solicitado = solicitado
        self.disponible = disponible
        super().__init__(
            f"Stock insuficiente para '{producto_nombre}' (ID: {producto_id}). "
            f"Solicitado: {solicitado}, Disponible: {disponible}."
        )


class OrderService:
    """Servicio para procesar pedidos de forma atómica y consultar comprobantes."""

    @staticmethod
    def generar_numero_ticket(conn: sqlite3.Connection) -> str:
        """
        Genera un número de ticket correlativo diario en formato TCK-YYYYMMDD-XXXX.

        Parámetros:
            conn (sqlite3.Connection): Conexión activa.

        Retorna:
            str: Número de ticket único.
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
        2. Si falla algún ítem, lanza StockInsuficienteError para abortar la transacción.
        3. Obtiene el precio oficial de la base de datos (seguridad financiera anti-tampering).
        4. Descuenta el stock de cada producto.
        5. Inserta la cabecera en `pedidos` y cada línea en `pedido_detalles`.

        Parámetros:
            conn (sqlite3.Connection): Conexión envuelta en una transacción atómica activa.
            pedido_data (PedidoCreate): Datos validados del pedido.

        Retorna:
            Dict[str, Any]: Diccionario con la información completa del pedido emitido.

        Lanza:
            StockInsuficienteError: Si las existencias no cubren el pedido.
            ValueError: Si un producto no existe o está inactivo.
        """
        cursor = conn.cursor()

        # Agrupar cantidades si el mismo producto fue enviado repetido en el carrito
        cantidades_solicitadas: Dict[int, int] = {}
        for item in pedido_data.items:
            cantidades_solicitadas[item.producto_id] = (
                cantidades_solicitadas.get(item.producto_id, 0) + item.cantidad
            )

        items_procesados = []
        total_calculado = 0.0

        # Paso 1: Validación estricta previa de existencias
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

            stock_disponible = prod_row["stock_actual"]
            if stock_disponible < cant_requerida:
                # Regla de negocio: Abortar inmediatamente
                raise StockInsuficienteError(
                    producto_id=prod_id,
                    producto_nombre=prod_row["nombre"],
                    solicitado=cant_requerida,
                    disponible=stock_disponible
                )

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

        # Paso 2: Descuento atómico de existencias
        for item in items_procesados:
            cursor.execute(
                """
                UPDATE productos
                SET stock_actual = stock_actual - ?,
                    actualizado_en = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (item["cantidad"], item["producto_id"])
            )

        # Paso 3: Inserción de cabecera del pedido con hora local explícita
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

        # Paso 4: Inserción de líneas de ticket
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

        # Paso 5: Consultar fecha_hora registrada por SQLite
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
    def obtener_pedido_por_id(conn: sqlite3.Connection, pedido_id: int) -> Optional[Dict[str, Any]]:
        """
        Recupera el pedido completo con sus líneas de detalle para visualización o reimpresión de ticket.

        Parámetros:
            conn (sqlite3.Connection): Conexión activa.
            pedido_id (int): ID del pedido.

        Retorna:
            Optional[Dict[str, Any]]: Pedido con líneas de detalle o None si no existe.
        """
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
