"""
Capa de Servicio y Acceso a Datos para el Catálogo de Productos e Inventario.

Encapsula todas las operaciones SQL sobre la tabla `productos`, garantizando consultas
100% parametrizadas con placeholders `?`, prevención de inyección SQL y manejo de integridad.
"""

import sqlite3
import unicodedata
import re
from typing import List, Optional, Dict, Any, Set
from app.models.schemas import (
    ProductoCreate, ProductoUpdate,
    ProductoBulkRequest, ProductoBulkResponse, ProductoBulkDetalle
)


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
            SELECT p.id, p.codigo, p.nombre, p.stock_inicial, p.stock_actual, p.costo_unitario,
                   p.precio_venta, p.activo, p.creado_en, p.actualizado_en,
                   COUNT(rd.insumo_id) AS total_insumos_receta
            FROM productos p
            LEFT JOIN receta_detalles rd ON rd.producto_id = p.id
            WHERE 1=1
        """
        params: List[Any] = []

        if solo_activos:
            query += " AND p.activo = 1"

        if busqueda and busqueda.strip():
            filtro = f"%{busqueda.strip()}%"
            query += " AND (p.codigo LIKE ? OR p.nombre LIKE ?)"
            params.extend([filtro, filtro])

        query += " GROUP BY p.id ORDER BY p.activo DESC, p.nombre ASC;"

        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        resultado = []
        for row in rows:
            prod_dict = dict(row)
            prod_dict["alerta_stock"] = (prod_dict["stock_actual"] <= 5 and prod_dict["activo"] == 1)
            total_ins = prod_dict.get("total_insumos_receta", 0)
            prod_dict["tiene_receta"] = (total_ins > 0)
            prod_dict["total_insumos_receta"] = total_ins
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
            SELECT p.id, p.codigo, p.nombre, p.stock_inicial, p.stock_actual, p.costo_unitario,
                   p.precio_venta, p.activo, p.creado_en, p.actualizado_en,
                   COUNT(rd.insumo_id) AS total_insumos_receta
            FROM productos p
            LEFT JOIN receta_detalles rd ON rd.producto_id = p.id
            WHERE p.id = ?
            GROUP BY p.id;
            """,
            (producto_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        prod_dict = dict(row)
        prod_dict["alerta_stock"] = (prod_dict["stock_actual"] <= 5 and prod_dict["activo"] == 1)
        total_ins = prod_dict.get("total_insumos_receta", 0)
        prod_dict["tiene_receta"] = (total_ins > 0)
        prod_dict["total_insumos_receta"] = total_ins
        return prod_dict

    @staticmethod
    def crear_producto(conn: sqlite3.Connection, data: ProductoCreate) -> Dict[str, Any]:
        """
        Inserta un nuevo producto en el catálogo con soporte opcional de receta de insumos.

        Parámetros:
            conn (sqlite3.Connection): Conexión activa a la base de datos.
            data (ProductoCreate): Datos validados del producto a crear.

        Retorna:
            Dict[str, Any]: Registro recién insertado con su ID generado y receta vinculada.

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
        cursor.close()

        # Si se incluyó receta en la solicitud, guardarla atómicamente
        if data.receta and len(data.receta) > 0:
            from app.services.insumo_service import InsumoService
            InsumoService.guardar_receta_producto(conn, nuevo_id, data.receta)

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

    @staticmethod
    def _generar_codigo_disponible(conn: sqlite3.Connection, nombre: str, usados: Set[str]) -> str:
        """
        Genera un código corto único para un producto a partir de su nombre (ej: MED01, CAF02).
        """
        nombre_limpio = unicodedata.normalize('NFKD', nombre).encode('ASCII', 'ignore').decode('utf-8')
        letras = re.sub(r'[^A-Za-z0-9]', '', nombre_limpio).upper()
        prefijo = letras[:3] if len(letras) >= 3 else (letras + "PRD")[:3]
        if not prefijo:
            prefijo = "PRD"

        cursor = conn.cursor()
        cursor.execute("SELECT codigo FROM productos WHERE codigo LIKE ?;", (f"{prefijo}%",))
        existentes = {row[0].upper() for row in cursor.fetchall()}
        existentes.update(usados)

        num = 1
        while True:
            candidato = f"{prefijo}{num:02d}"
            if candidato not in existentes:
                usados.add(candidato)
                return candidato
            num += 1

    @staticmethod
    def importar_lote_productos(
        conn: sqlite3.Connection,
        datos: ProductoBulkRequest
    ) -> Dict[str, Any]:
        """
        Procesa una carga masiva de productos (creación / reabastecimiento inteligente)
        provenientes del módulo de IA o importación en lote.

        Parámetros:
            conn (sqlite3.Connection): Conexión activa.
            datos (ProductoBulkRequest): Lote de productos e indicación de modo.

        Retorna:
            Dict[str, Any]: Resumen y detalle consolidado de la importación.
        """
        cursor = conn.cursor()
        codigos_usados: Set[str] = set()
        detalles = []
        total_creados = 0
        total_actualizados = 0
        total_ignorados = 0

        for item in datos.productos:
            # 1. Buscar si ya existe por código (si vino informado) o por coincidencia exacta de nombre
            prod_existente = None

            if item.codigo and item.codigo.strip():
                cursor.execute(
                    "SELECT id, codigo, nombre, stock_inicial, stock_actual, costo_unitario, precio_venta, activo FROM productos WHERE UPPER(codigo) = ?;",
                    (item.codigo.strip().upper(),)
                )
                prod_existente = cursor.fetchone()

            if not prod_existente:
                cursor.execute(
                    "SELECT id, codigo, nombre, stock_inicial, stock_actual, costo_unitario, precio_venta, activo FROM productos WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(?));",
                    (item.nombre.strip(),)
                )
                prod_existente = cursor.fetchone()

            if prod_existente:
                p_id = prod_existente["id"]
                p_codigo = prod_existente["codigo"]
                p_nombre = prod_existente["nombre"]
                p_stock_actual = prod_existente["stock_actual"]
                p_stock_inicial = prod_existente["stock_inicial"]
                p_costo = prod_existente["costo_unitario"]
                p_precio = prod_existente["precio_venta"]

                codigos_usados.add(p_codigo.upper())

                if datos.modo == "sumar_stock":
                    nuevo_stock_actual = p_stock_actual + item.stock
                    nuevo_stock_inicial = p_stock_inicial + item.stock
                    nuevo_costo = item.costo_unitario if item.costo_unitario > 0 else p_costo
                    nuevo_precio = item.precio_venta if item.precio_venta > 0 else p_precio

                    cursor.execute(
                        """
                        UPDATE productos
                        SET stock_actual = ?,
                            stock_inicial = ?,
                            costo_unitario = ?,
                            precio_venta = ?,
                            activo = 1,
                            actualizado_en = CURRENT_TIMESTAMP
                        WHERE id = ?;
                        """,
                        (nuevo_stock_actual, nuevo_stock_inicial, nuevo_costo, nuevo_precio, p_id)
                    )
                    total_actualizados += 1
                    detalles.append({
                        "codigo": p_codigo,
                        "nombre": p_nombre,
                        "accion": "actualizado",
                        "stock_previo": p_stock_actual,
                        "stock_final": nuevo_stock_actual,
                        "costo_unitario": nuevo_costo,
                        "precio_venta": nuevo_precio,
                        "mensaje": f"Stock sumado (+{item.stock}). Stock actual: {nuevo_stock_actual}."
                    })
                else:
                    total_ignorados += 1
                    detalles.append({
                        "codigo": p_codigo,
                        "nombre": p_nombre,
                        "accion": "ignorado",
                        "stock_previo": p_stock_actual,
                        "stock_final": p_stock_actual,
                        "costo_unitario": p_costo,
                        "precio_venta": p_precio,
                        "mensaje": "Producto existente omitido según la directiva configurada."
                    })
            else:
                # Producto nuevo
                codigo_asignado = item.codigo.strip().upper() if (item.codigo and item.codigo.strip()) else None
                if not codigo_asignado or codigo_asignado in codigos_usados:
                    codigo_asignado = ProductoService._generar_codigo_disponible(conn, item.nombre, codigos_usados)
                else:
                    # Verificar si existe en DB
                    cursor.execute("SELECT id FROM productos WHERE UPPER(codigo) = ?;", (codigo_asignado,))
                    if cursor.fetchone():
                        codigo_asignado = ProductoService._generar_codigo_disponible(conn, item.nombre, codigos_usados)

                codigos_usados.add(codigo_asignado.upper())

                cursor.execute(
                    """
                    INSERT INTO productos (codigo, nombre, stock_inicial, stock_actual, costo_unitario, precio_venta, activo)
                    VALUES (?, ?, ?, ?, ?, ?, 1);
                    """,
                    (
                        codigo_asignado,
                        item.nombre.strip(),
                        item.stock,
                        item.stock,
                        item.costo_unitario,
                        item.precio_venta
                    )
                )
                total_creados += 1
                detalles.append({
                    "codigo": codigo_asignado,
                    "nombre": item.nombre.strip(),
                    "accion": "creado",
                    "stock_previo": 0,
                    "stock_final": item.stock,
                    "costo_unitario": item.costo_unitario,
                    "precio_venta": item.precio_venta,
                    "mensaje": f"Nuevo producto creado con código {codigo_asignado} y {item.stock} unidades."
                })

        return {
            "total_recibidos": len(datos.productos),
            "total_creados": total_creados,
            "total_actualizados": total_actualizados,
            "total_ignorados": total_ignorados,
            "detalles": detalles
        }

