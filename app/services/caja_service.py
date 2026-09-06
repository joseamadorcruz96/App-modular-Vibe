"""
Capa de Servicio para Resumen Diario de Caja, Cierre, Auditoría y Respaldos.

Gestiona el cálculo de métricas financieras del día, desglose por medio de pago,
ranking de productos más vendidos y la generación de respaldos automáticos en caliente.
"""

import sqlite3
import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import app.config as config
from app.database import backup_database, init_db


class CajaService:
    """Servicio de control de caja, arqueos y copias de seguridad de base de datos."""

    @staticmethod
    def obtener_resumen_diario(
        conn: sqlite3.Connection,
        fecha_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calcula el total recaudado, el desglose por medio de pago y el top de productos vendidos para una fecha.

        Parámetros:
            conn (sqlite3.Connection): Conexión activa.
            fecha_str (Optional[str]): Fecha en formato 'YYYY-MM-DD'. Si es None, toma la fecha actual.

        Retorna:
            Dict[str, Any]: Estructura con fecha, total_recaudado, cantidad_tickets, desglose_medios_pago y productos_top.
        """
        if not fecha_str:
            fecha_str = datetime.date.today().isoformat()

        cursor = conn.cursor()

        # Total general y cantidad de pedidos del día
        cursor.execute(
            """
            SELECT COALESCE(SUM(total), 0.0) as total_recaudado,
                   COUNT(id) as cantidad_tickets
            FROM pedidos
            WHERE DATE(fecha_hora) = DATE(?) AND estado = 'Completado';
            """,
            (fecha_str,)
        )
        row_totales = cursor.fetchone()
        total_recaudado = float(row_totales["total_recaudado"])
        cantidad_tickets = int(row_totales["cantidad_tickets"])

        # Desglose por medio de pago
        medios_default = {"Efectivo": 0.0, "Débito": 0.0, "Crédito": 0.0, "Transferencia": 0.0}
        cursor.execute(
            """
            SELECT medio_pago, COALESCE(SUM(total), 0.0) as total_medio
            FROM pedidos
            WHERE DATE(fecha_hora) = DATE(?) AND estado = 'Completado'
            GROUP BY medio_pago;
            """,
            (fecha_str,)
        )
        for row in cursor.fetchall():
            medios_default[row["medio_pago"]] = float(row["total_medio"])

        # Top 5 productos más vendidos del día
        cursor.execute(
            """
            SELECT p.nombre,
                   SUM(d.cantidad) as unidades_vendidas,
                   SUM(d.subtotal) as total_recaudado
            FROM pedido_detalles d
            JOIN pedidos ped ON d.pedido_id = ped.id
            JOIN productos p ON d.producto_id = p.id
            WHERE DATE(ped.fecha_hora) = DATE(?) AND ped.estado = 'Completado'
            GROUP BY d.producto_id, p.nombre
            ORDER BY unidades_vendidas DESC, total_recaudado DESC
            LIMIT 5;
            """,
            (fecha_str,)
        )
        productos_top = [
            {
                "nombre": row["nombre"],
                "unidades_vendidas": int(row["unidades_vendidas"]),
                "total_recaudado": float(row["total_recaudado"])
            }
            for row in cursor.fetchall()
        ]

        return {
            "fecha": fecha_str,
            "total_recaudado": total_recaudado,
            "cantidad_tickets": cantidad_tickets,
            "desglose_medios_pago": medios_default,
            "productos_top": productos_top
        }

    @staticmethod
    def ejecutar_cierre_caja(
        conn: sqlite3.Connection,
        fecha_str: Optional[str] = None,
        database_path: Optional[Path] = None,
        backup_folder: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta el cierre formal de caja:
        1. Obtiene el resumen del día.
        2. Genera una copia snapshot de la base de datos en `/backups`.
        3. Registra la auditoría en la tabla `cierres_caja`.

        Parámetros:
            conn (sqlite3.Connection): Conexión activa.
            fecha_str (Optional[str]): Fecha a cerrar.
            database_path (Optional[Path]): Ruta física de la base de datos origen.
            backup_folder (Optional[Path]): Carpeta de destino de respaldos.

        Retorna:
            Dict[str, Any]: Información de confirmación, ruta del backup y resumen consolidado.
        """
        if not fecha_str:
            fecha_str = datetime.date.today().isoformat()
        if database_path is None:
            database_path = config.DB_PATH
        if backup_folder is None:
            backup_folder = config.BACKUP_DIR

        resumen = CajaService.obtener_resumen_diario(conn, fecha_str)

        # Generar snapshot en caliente
        backup_path = backup_database(database_path, backup_folder)

        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO cierres_caja (
                fecha_cierre, total_recaudado, total_efectivo, total_debito,
                total_credito, total_transferencia, cantidad_pedidos, archivo_backup
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                fecha_str,
                resumen["total_recaudado"],
                resumen["desglose_medios_pago"].get("Efectivo", 0.0),
                resumen["desglose_medios_pago"].get("Débito", 0.0),
                resumen["desglose_medios_pago"].get("Crédito", 0.0),
                resumen["desglose_medios_pago"].get("Transferencia", 0.0),
                resumen["cantidad_tickets"],
                str(backup_path.name)
            )
        )

        return {
            "status": "success",
            "mensaje": "Cierre de caja registrado exitosamente y copia de respaldo generada.",
            "backup_generado": str(backup_path),
            "resumen": resumen
        }

    @staticmethod
    def limpiar_base_datos_total(
        database_path: Optional[Path] = None,
        schema_file: Optional[Path] = None
    ) -> None:
        """
        Restaura la base de datos al estado de fábrica ejecutando nuevamente el esquema DDL y semillas.

        Parámetros:
            database_path (Optional[Path]): Ruta de la base de datos.
            schema_file (Optional[Path]): Archivo DDL.
        """
        if database_path is None:
            database_path = config.DB_PATH
        if schema_file is None:
            schema_file = config.SCHEMA_PATH

        # Antes de purgar, genera un backup de salvaguarda
        backup_database(database_path, config.BACKUP_DIR)

        # Eliminar tablas y recrear
        conn = sqlite3.connect(database_path)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF;")
            tablas = [
                "receta_detalles",
                "comanda_detalles",
                "comandas",
                "pedido_detalles",
                "pedidos",
                "productos",
                "insumos",
                "configuracion",
                "cierres_caja"
            ]
            for tabla in tablas:
                cursor.execute(f"DROP TABLE IF EXISTS {tabla};")
            conn.commit()
        finally:
            conn.close()

        # Re-ejecutar schema
        init_db(database_path, schema_file)
        return {
            "status": "success",
            "mensaje": "Base de datos recreada e inicializada desde cero."
        }

    @staticmethod
    def cargar_semillas_demo(
        database_path: Optional[Path] = None,
        seeds_file: Optional[Path] = None
    ) -> Dict[str, int]:
        """
        Carga las semillas de productos, insumos y recetas de demostración desde seeds.sql.

        Parámetros:
            database_path (Optional[Path]): Ruta de la base de datos.
            seeds_file (Optional[Path]): Archivo SQL de semillas.

        Retorna:
            Dict[str, int]: Conteo de productos, insumos y recetas cargadas.
        """
        if database_path is None:
            database_path = config.DB_PATH
        if seeds_file is None:
            seeds_file = config.SEEDS_PATH

        if not seeds_file.exists():
            raise FileNotFoundError(f"No se encontró el archivo de semillas en {seeds_file}")

        with seeds_file.open("r", encoding="utf-8") as f:
            seeds_sql = f.read()

        conn = sqlite3.connect(database_path, timeout=config.SQLITE_TIMEOUT_SECONDS)
        try:
            conn.executescript(seeds_sql)
            conn.commit()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM productos;")
            total_prods = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM insumos;")
            total_insumos = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(DISTINCT producto_id) FROM receta_detalles;")
            total_recetas = cursor.fetchone()[0]
            return {
                "productos": total_prods,
                "insumos": total_insumos,
                "recetas": total_recetas
            }
        finally:
            conn.close()
