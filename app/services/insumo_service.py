"""
Módulo de Servicios para Gestión de Insumos y Recetas (Escandallos).

Proporciona operaciones parametrizadas para administración de materias primas,
control de existencias, formulación de recetas y cálculo dinámico de costos y márgenes.
"""

import sqlite3
from typing import List, Optional, Dict, Any

from app.models.schemas import (
    InsumoCreate,
    InsumoUpdate,
    RecetaItemCreate,
)


class InsumoService:
    """Servicio con lógica de negocio para materias primas y recetas."""

    @staticmethod
    def listar_insumos(conn: sqlite3.Connection, solo_activos: bool = True) -> List[Dict[str, Any]]:
        """Devuelve el inventario de insumos ordenado alfabéticamente."""
        sql = """
            SELECT id, codigo, nombre, unidad_medida, stock_actual, stock_minimo,
                   costo_unitario, activo, creado_en, actualizado_en
            FROM insumos
        """
        params = []
        if solo_activos:
            sql += " WHERE activo = 1"
        sql += " ORDER BY nombre ASC;"

        cursor = conn.cursor()
        cursor.execute(sql, params)
        filas = cursor.fetchall()
        cursor.close()

        resultado = []
        for fila in filas:
            item = dict(fila)
            item["alerta_stock"] = (item["stock_actual"] <= item["stock_minimo"])
            resultado.append(item)
        return resultado

    @staticmethod
    def obtener_por_id(conn: sqlite3.Connection, insumo_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene un insumo por su ID."""
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, codigo, nombre, unidad_medida, stock_actual, stock_minimo,
                   costo_unitario, activo, creado_en, actualizado_en
            FROM insumos
            WHERE id = ?;
            """,
            (insumo_id,)
        )
        fila = cursor.fetchone()
        cursor.close()
        if not fila:
            return None
        res = dict(fila)
        res["alerta_stock"] = (res["stock_actual"] <= res["stock_minimo"])
        return res

    @staticmethod
    def crear_insumo(conn: sqlite3.Connection, data: InsumoCreate) -> Dict[str, Any]:
        """Da de alta un nuevo insumo con código único."""
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO insumos (codigo, nombre, unidad_medida, stock_actual, stock_minimo, costo_unitario, activo)
            VALUES (?, ?, ?, ?, ?, ?, 1);
            """,
            (
                data.codigo,
                data.nombre,
                data.unidad_medida,
                data.stock_actual,
                data.stock_minimo,
                data.costo_unitario
            )
        )
        nuevo_id = cursor.lastrowid
        cursor.close()
        return InsumoService.obtener_por_id(conn, nuevo_id)  # type: ignore

    @staticmethod
    def actualizar_insumo(conn: sqlite3.Connection, insumo_id: int, data: InsumoUpdate) -> Optional[Dict[str, Any]]:
        """Actualiza atributos de un insumo existente."""
        actual = InsumoService.obtener_por_id(conn, insumo_id)
        if not actual:
            return None

        campos = []
        valores = []
        data_dict = data.model_dump(exclude_unset=True)

        for campo, valor in data_dict.items():
            campos.append(f"{campo} = ?")
            valores.append(valor)

        if not campos:
            return actual

        campos.append("actualizado_en = CURRENT_TIMESTAMP")
        valores.append(insumo_id)

        sql = f"UPDATE insumos SET {', '.join(campos)} WHERE id = ?;"
        cursor = conn.cursor()
        cursor.execute(sql, valores)
        cursor.close()

        return InsumoService.obtener_por_id(conn, insumo_id)

    @staticmethod
    def reabastecer_insumo(conn: sqlite3.Connection, insumo_id: int, cantidad: float) -> Optional[Dict[str, Any]]:
        """Suma unidades al stock físico del insumo."""
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE insumos
            SET stock_actual = stock_actual + ?,
                actualizado_en = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (cantidad, insumo_id)
        )
        filas_afectadas = cursor.rowcount
        cursor.close()
        if filas_afectadas == 0:
            return None
        return InsumoService.obtener_por_id(conn, insumo_id)

    @staticmethod
    def eliminar_insumo(conn: sqlite3.Connection, insumo_id: int, forzar: bool = False) -> Dict[str, Any]:
        """
        Elimina el insumo.
        - Si forzar es True: elimina las referencias en receta_detalles y elimina físicamente el insumo.
        - Si forzar es False: si está en recetas, lo desactiva lógicamente (activo = 0); si no está en recetas, lo elimina físicamente.
        """
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM receta_detalles WHERE insumo_id = ?;", (insumo_id,))
        en_recetas = cursor.fetchone()[0]

        if en_recetas > 0:
            if forzar:
                cursor.execute("DELETE FROM receta_detalles WHERE insumo_id = ?;", (insumo_id,))
                cursor.execute("DELETE FROM insumos WHERE id = ?;", (insumo_id,))
                cursor.close()
                return {
                    "id": insumo_id,
                    "tipo_eliminacion": "fisica",
                    "recetas_desvinculadas": en_recetas,
                    "mensaje": f"Insumo y sus {en_recetas} referencias en recetas han sido eliminados definitivamente."
                }
            else:
                cursor.execute("UPDATE insumos SET activo = 0 WHERE id = ?;", (insumo_id,))
                cursor.close()
                return {
                    "id": insumo_id,
                    "tipo_eliminacion": "logica",
                    "recetas_desvinculadas": en_recetas,
                    "mensaje": f"El insumo está asignado a {en_recetas} receta(s). Se ha desactivado del catálogo."
                }

        cursor.execute("DELETE FROM insumos WHERE id = ?;", (insumo_id,))
        cursor.close()
        return {
            "id": insumo_id,
            "tipo_eliminacion": "fisica",
            "mensaje": "Insumo eliminado definitivamente del inventario."
        }

    # ==========================================================================
    # Gestión de Recetas y Costos por Producto
    # ==========================================================================

    @staticmethod
    def obtener_receta_producto(conn: sqlite3.Connection, producto_id: int) -> Optional[Dict[str, Any]]:
        """
        Recupera la receta de un producto con desglose de insumos,
        calculando en tiempo real el costo de la receta, el margen bruto ($) y el margen comercial (%).
        """
        # 1. Obtener producto
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, codigo, nombre, precio_venta, costo_unitario FROM productos WHERE id = ?;",
            (producto_id,)
        )
        prod = cursor.fetchone()
        if not prod:
            cursor.close()
            return None

        # 2. Obtener ingredientes de la receta
        cursor.execute(
            """
            SELECT rd.insumo_id, i.codigo as insumo_codigo, i.nombre as insumo_nombre,
                   i.unidad_medida, rd.cantidad, i.costo_unitario as costo_unitario_insumo
            FROM receta_detalles rd
            JOIN insumos i ON rd.insumo_id = i.id
            WHERE rd.producto_id = ?
            ORDER BY i.nombre ASC;
            """,
            (producto_id,)
        )
        filas = cursor.fetchall()
        cursor.close()

        ingredientes = []
        costo_total_receta = 0.0

        for f in filas:
            costo_porcion = round(f["cantidad"] * f["costo_unitario_insumo"], 2)
            costo_total_receta += costo_porcion
            ingredientes.append({
                "insumo_id": f["insumo_id"],
                "insumo_codigo": f["insumo_codigo"],
                "insumo_nombre": f["insumo_nombre"],
                "unidad_medida": f["unidad_medida"],
                "cantidad": f["cantidad"],
                "costo_unitario_insumo": f["costo_unitario_insumo"],
                "costo_por_porcion": costo_porcion
            })

        tiene_receta = len(ingredientes) > 0
        costo_aplicable = costo_total_receta if tiene_receta else prod["costo_unitario"]
        precio_venta = prod["precio_venta"]
        margen_bruto = round(precio_venta - costo_aplicable, 2)
        margen_porcentaje = round((margen_bruto / precio_venta * 100), 2) if precio_venta > 0 else 0.0

        return {
            "producto_id": prod["id"],
            "producto_codigo": prod["codigo"],
            "producto_nombre": prod["nombre"],
            "precio_venta": precio_venta,
            "tiene_receta": tiene_receta,
            "costo_receta": round(costo_aplicable, 2),
            "margen_bruto": margen_bruto,
            "margen_porcentaje": margen_porcentaje,
            "ingredientes": ingredientes
        }

    @staticmethod
    def guardar_receta_producto(
        conn: sqlite3.Connection,
        producto_id: int,
        ingredientes: List[RecetaItemCreate]
    ) -> Dict[str, Any]:
        """
        Reemplaza o define la receta de un producto de forma atómica.
        Actualiza el costo_unitario del producto para reflejar la suma de insumos.
        """
        cursor = conn.cursor()

        # Verificar que el producto exista
        cursor.execute("SELECT id FROM productos WHERE id = ?;", (producto_id,))
        if not cursor.fetchone():
            cursor.close()
            raise ValueError(f"El producto con ID {producto_id} no existe.")

        # Limpiar receta previa
        cursor.execute("DELETE FROM receta_detalles WHERE producto_id = ?;", (producto_id,))

        # Insertar nuevos ingredientes
        for item in ingredientes:
            # Validar que el insumo exista y esté activo
            cursor.execute("SELECT id FROM insumos WHERE id = ? AND activo = 1;", (item.insumo_id,))
            if not cursor.fetchone():
                cursor.close()
                raise ValueError(f"El insumo ID {item.insumo_id} no existe o está inactivo.")

            cursor.execute(
                """
                INSERT INTO receta_detalles (producto_id, insumo_id, cantidad)
                VALUES (?, ?, ?);
                """,
                (producto_id, item.insumo_id, item.cantidad)
            )

        cursor.close()

        # Obtener receta resultante para actualizar costo_unitario en productos
        receta_res = InsumoService.obtener_receta_producto(conn, producto_id)
        if receta_res and receta_res["tiene_receta"]:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE productos SET costo_unitario = ? WHERE id = ?;",
                (receta_res["costo_receta"], producto_id)
            )
            cursor.close()

        return receta_res  # type: ignore

    @staticmethod
    def eliminar_receta_producto(conn: sqlite3.Connection, producto_id: int) -> bool:
        """Elimina todos los ingredientes de la receta, regresando el producto a modo simple."""
        cursor = conn.cursor()
        cursor.execute("DELETE FROM receta_detalles WHERE producto_id = ?;", (producto_id,))
        filas = cursor.rowcount
        cursor.close()
        return filas > 0
