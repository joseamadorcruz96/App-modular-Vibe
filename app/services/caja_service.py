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
    def obtener_auditoria_detallada(
        conn: sqlite3.Connection,
        fecha_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Genera el informe exhaustivo para auditoría de cierre de caja:
        Recupera cada comanda y pedido cobrado en la fecha indicada, con desglose de ítems,
        precios, cantidades, medios de pago y mesa.
        """
        if not fecha_str:
            fecha_str = datetime.date.today().isoformat()

        resumen_base = CajaService.obtener_resumen_diario(conn, fecha_str)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT p.id as ticket_id, p.numero_ticket, p.fecha_hora, p.mesa, p.cliente,
                   p.medio_pago, p.total, c.id as comanda_id, c.numero_comanda
            FROM pedidos p
            LEFT JOIN comandas c ON c.pedido_id = p.id
            WHERE DATE(p.fecha_hora) = DATE(?) AND p.estado = 'Completado'
            ORDER BY p.id ASC;
            """,
            (fecha_str,)
        )
        pedidos_rows = cursor.fetchall()

        pedidos_detallados = []
        for p in pedidos_rows:
            t_id = p["ticket_id"]
            cursor.execute(
                """
                SELECT pd.producto_id, pr.codigo, pr.nombre, pd.cantidad, pd.precio_unitario, pd.subtotal
                FROM pedido_detalles pd
                JOIN productos pr ON pd.producto_id = pr.id
                WHERE pd.pedido_id = ?
                ORDER BY pd.id ASC;
                """,
                (t_id,)
            )
            items_rows = cursor.fetchall()
            items_list = [
                {
                    "producto_id": r["producto_id"],
                    "codigo": r["codigo"],
                    "nombre": r["nombre"],
                    "cantidad": int(r["cantidad"]),
                    "precio_unitario": float(r["precio_unitario"]),
                    "subtotal": float(r["subtotal"])
                }
                for r in items_rows
            ]

            pedidos_detallados.append({
                "ticket_id": p["ticket_id"],
                "numero_ticket": p["numero_ticket"],
                "comanda_id": p["comanda_id"],
                "numero_comanda": p["numero_comanda"],
                "mesa": p["mesa"],
                "cliente": p["cliente"],
                "medio_pago": p["medio_pago"],
                "fecha_hora": str(p["fecha_hora"]),
                "total": float(p["total"]),
                "items": items_list
            })

        cursor.close()

        return {
            "fecha": fecha_str,
            "total_recaudado": resumen_base["total_recaudado"],
            "cantidad_tickets": resumen_base["cantidad_tickets"],
            "desglose_medios_pago": resumen_base["desglose_medios_pago"],
            "pedidos": pedidos_detallados
        }

    @staticmethod
    def generar_markdown_informe_cierre(auditoria: Dict[str, Any]) -> str:
        """
        Compila los datos de auditoría en un documento Markdown estructurado con tablas limpias,
        ideal para exportar o archivar.
        """
        fecha = auditoria["fecha"]
        total = auditoria["total_recaudado"]
        cant_tickets = auditoria["cantidad_tickets"]
        medios = auditoria["desglose_medios_pago"]
        pedidos = auditoria["pedidos"]

        lineas = [
            f"# Informe de Cierre de Caja y Auditoría de Ventas",
            f"**Fecha de Operación:** {fecha}  ",
            f"**Generado:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
            f"",
            f"## 1. Resumen Consolidado de Jornada",
            f"",
            f"| Métrica | Valor |",
            f"| :--- | :--- |",
            f"| **Total Recaudado** | **${total:,.2f}** |",
            f"| **Cantidad de Tickets / Ventas** | **{cant_tickets}** |",
            f"",
            f"### Desglose por Medio de Pago",
            f"",
            f"| Medio de Pago | Importe Total |",
            f"| :--- | :--- |",
        ]

        for medio, monto in medios.items():
            lineas.append(f"| {medio} | ${monto:,.2f} |")

        lineas.extend([
            f"",
            f"## 2. Registro Detallado de Comandas y Tickets Cobrados",
            f"",
            f"| Hora | Ticket | Comanda | Mesa | Cliente | Medio Pago | Total ($) |",
            f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        if not pedidos:
            lineas.append(f"| - | *Sin ventas registradas en esta jornada* | - | - | - | - | $0.00 |")
        else:
            for p in pedidos:
                comanda_lbl = p["numero_comanda"] or "Venta Directa"
                lineas.append(
                    f"| {p['fecha_hora']} | `{p['numero_ticket']}` | `{comanda_lbl}` | {p['mesa']} | {p['cliente']} | {p['medio_pago']} | ${p['total']:,.2f} |"
                )

        lineas.extend([
            f"",
            f"## 3. Desglose de Productos Servidos por Ticket",
            f"",
            f"| Ticket | Producto | Código | Cantidad | P. Unitario ($) | Subtotal ($) |",
            f"| :--- | :--- | :--- | :---: | :---: | :---: |",
        ])

        if not pedidos:
            lineas.append(f"| - | *Sin productos consumidos* | - | 0 | $0.00 | $0.00 |")
        else:
            for p in pedidos:
                for it in p["items"]:
                    lineas.append(
                        f"| `{p['numero_ticket']}` | {it['nombre']} | `{it['codigo']}` | {it['cantidad']} | ${it['precio_unitario']:,.2f} | ${it['subtotal']:,.2f} |"
                    )

        lineas.extend([
            f"",
            f"---",
            f"*Informe emitido automáticamente por CoffeePOS - Caffe-SoKa.*"
        ])

        return "\n".join(lineas)

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
