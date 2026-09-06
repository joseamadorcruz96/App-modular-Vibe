"""
Capa de Servicio y Acceso a Datos para el Catálogo de Productos e Inventario.

Encapsula todas las operaciones SQL sobre la tabla `productos`, garantizando consultas
100% parametrizadas con placeholders `?`, prevención de inyección SQL y manejo de integridad.
"""

import sqlite3
from typing import List, Optional, Dict, Any
from app.models.schemas import ProductoCreate, ProductoUpdate


class ProductoService:
    """Servicio de gestión de catálogo, inventario y existencias de productos."""

    @staticmethod
    def listar_productos(
        conn: sqlite3.Connection,
        solo_activos: bool = True,
        busqueda: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Lista los productos aplicando filtros de activación y término de búsqueda por código o nombre.

        Parámetros:
            conn (sqlite3.Connection): Conexión activa a la base de datos.
            solo_activos (bool): Si es True, filtra únicamente registros con activo = 1.
            busqueda (Optional[str]): Texto para buscar coincidencias en código o nombre.

        Retorna:
            List[Dict[str, Any]]: Lista de productos con el indicador booleano alerta_stock (<= 5).
        """
        query = """
            SELECT id, codigo, nombre, stock_inicial, stock_actual, costo_unitario,
                   precio_venta, activo, creado_en, actualizado_en
            FROM productos
            WHERE 1=1
        """
        params: List[Any] = []

        if solo_activos:
            query += " AND activo = 1"

        if busqueda and busqueda.strip():
            filtro = f"%{busqueda.strip()}%"
            query += " AND (codigo LIKE ? OR nombre LIKE ?)"
            params.extend([filtro, filtro])

        query += " ORDER BY activo DESC, nombre ASC;"

        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        resultado = []
        for row in rows:
            prod_dict = dict(row)
            prod_dict["alerta_stock"] = (prod_dict["stock_actual"] <= 5 and prod_dict["activo"] == 1)
            resultado.append(prod_dict)

        return resultado

    @staticmethod
    def obtener_por_id(conn: sqlite3.Connection, producto_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene un producto específico por su clave primaria.

        Parámetros:
            conn (sqlite3.Connection): Conexión activa a la base de datos.
            producto_id (int): Identificador numérico del producto.

        Retorna:
            Optional[Dict[str, Any]]: Diccionario del producto o None si no existe.
        """
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, codigo, nombre, stock_inicial, stock_actual, costo_unitario,
                   precio_venta, activo, creado_en, actualizado_en
            FROM productos
            WHERE id = ?;
            """,
            (producto_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        prod_dict = dict(row)
        prod_dict["alerta_stock"] = (prod_dict["stock_actual"] <= 5 and prod_dict["activo"] == 1)
        return prod_dict

    @staticmethod
    def crear_producto(conn: sqlite3.Connection, data: ProductoCreate) -> Dict[str, Any]:
        """
        Inserta un nuevo producto en el catálogo.

        Parámetros:
            conn (sqlite3.Connection): Conexión activa a la base de datos.
            data (ProductoCreate): Datos validados del producto a crear.

        Retorna:
            Dict[str, Any]: Registro recién insertado con su ID generado.

        Lanza:
            sqlite3.IntegrityError: Si el código ya existe o se vulnera un CHECK constraint.
        """
        cursor = conn.cursor()
        # En la creación, stock_actual inicia con el valor de stock_inicial
        cursor.execute(
            """
            INSERT INTO productos (codigo, nombre, stock_inicial, stock_actual, costo_unitario, precio_venta, activo)
            VALUES (?, ?, ?, ?, ?, ?, 1);
            """,
            (
                data.codigo,
                data.nombre,
                data.stock_inicial,
                data.stock_inicial,
                data.costo_unitario,
                data.precio_venta
            )
        )
        nuevo_id = cursor.lastrowid
        return ProductoService.obtener_por_id(conn, nuevo_id)  # type: ignore

    @staticmethod
    def actualizar_producto(
        conn: sqlite3.Connection,
        producto_id: int,
        data: ProductoUpdate
    ) -> Optional[Dict[str, Any]]:
        """
        Actualiza los campos modificables de un producto existente.

        Parámetros:
            conn (sqlite3.Connection): Conexión activa a la base de datos.
            producto_id (int): ID del producto.
            data (ProductoUpdate): Campos a actualizar.

        Retorna:
            Optional[Dict[str, Any]]: Producto actualizado o None si no existe.
        """
        campos = []
        params: List[Any] = []

        if data.codigo is not None:
            campos.append("codigo = ?")
            params.append(data.codigo)
        if data.nombre is not None:
            campos.append("nombre = ?")
            params.append(data.nombre)
        if data.stock_inicial is not None:
            campos.append("stock_inicial = ?")
            params.append(data.stock_inicial)
        if data.stock_actual is not None:
            campos.append("stock_actual = ?")
            params.append(data.stock_actual)
        if data.costo_unitario is not None:
            campos.append("costo_unitario = ?")
            params.append(data.costo_unitario)
        if data.precio_venta is not None:
            campos.append("precio_venta = ?")
            params.append(data.precio_venta)
        if data.activo is not None:
            campos.append("activo = ?")
            params.append(data.activo)

        if not campos:
            return ProductoService.obtener_por_id(conn, producto_id)

        campos.append("actualizado_en = CURRENT_TIMESTAMP")
        params.append(producto_id)

        query = f"UPDATE productos SET {', '.join(campos)} WHERE id = ?;"
        cursor = conn.cursor()
        cursor.execute(query, params)

        if cursor.rowcount == 0:
            return None

        return ProductoService.obtener_por_id(conn, producto_id)

    @staticmethod
    def eliminar_producto(conn: sqlite3.Connection, producto_id: int) -> Dict[str, Any]:
        """
        Elimina un producto del catálogo respetando la integridad referencial:
        - Si el producto tiene ventas en pedido_detalles: aplica borrado lógico (activo = 0) para no quebrar comprobantes pasados.
        - Si el producto NO tiene ventas: aplica borrado físico (DELETE).

        Parámetros:
            conn (sqlite3.Connection): Conexión activa.
            producto_id (int): ID del producto.

        Retorna:
            Dict[str, Any]: Resultado con status, tipo_eliminacion ('fisica' | 'logica') y mensaje.

        Lanza:
            ValueError: Si el producto no existe.
        """
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre FROM productos WHERE id = ?;", (producto_id,))
        prod = cursor.fetchone()
        if not prod:
            raise ValueError(f"El producto con ID {producto_id} no existe.")

        nombre_prod = prod["nombre"]

        # Verificar si tiene ventas registradas en pedidos
        cursor.execute("SELECT COUNT(*) FROM pedido_detalles WHERE producto_id = ?;", (producto_id,))
        total_ventas = cursor.fetchone()[0]

        if total_ventas > 0:
            # Borrado lógico para proteger histórico contable
            cursor.execute("UPDATE productos SET activo = 0, actualizado_en = CURRENT_TIMESTAMP WHERE id = ?;", (producto_id,))
            return {
                "id": producto_id,
                "nombre": nombre_prod,
                "tipo_eliminacion": "logica",
                "mensaje": f"El producto '{nombre_prod}' tiene ventas históricas asociadas. Se ha desactivado del catálogo para preservar los comprobantes."
            }
        else:
            # Borrado físico completo
            cursor.execute("DELETE FROM productos WHERE id = ?;", (producto_id,))
            return {
                "id": producto_id,
                "nombre": nombre_prod,
                "tipo_eliminacion": "fisica",
                "mensaje": f"El producto '{nombre_prod}' ha sido eliminado definitivamente del catálogo."
            }

    @staticmethod
    def reabastecer_producto(
        conn: sqlite3.Connection,
        producto_id: int,
        cantidad: int
    ) -> Optional[Dict[str, Any]]:
        """
        Añade unidades al stock actual y al stock inicial del producto de forma coherente.

        Parámetros:
            conn (sqlite3.Connection): Conexión a la base de datos.
            producto_id (int): ID del producto a reponer.
            cantidad (int): Unidades a sumar (debe ser > 0).

        Retorna:
            Optional[Dict[str, Any]]: Producto con stock actualizado o None si no existe.
        """
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE productos
            SET stock_actual = stock_actual + ?,
                stock_inicial = stock_inicial + ?,
                actualizado_en = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (cantidad, cantidad, producto_id)
        )
        if cursor.rowcount == 0:
            return None

        return ProductoService.obtener_por_id(conn, producto_id)

    @staticmethod
    def reiniciar_stock_a_inicial(conn: sqlite3.Connection) -> int:
        """
        Restablece el stock_actual al valor del stock_inicial para todos los productos.

        Parámetros:
            conn (sqlite3.Connection): Conexión a la base de datos.

        Retorna:
            int: Cantidad de filas afectadas.
        """
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE productos
            SET stock_actual = stock_inicial,
                actualizado_en = CURRENT_TIMESTAMP;
            """
        )
        return cursor.rowcount
