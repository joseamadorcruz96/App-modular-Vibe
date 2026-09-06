"""
Módulo de Gestión y Conexión de Base de Datos SQLite para CoffeePOS.

Este módulo encapsula la inicialización del motor, configuración de pragmas de
alta concurrencia (WAL mode, timeout de 10s, foreign keys y synchronous NORMAL),
gestores de contexto para transacciones atómicas seguras y el motor de respaldos en caliente.
"""

import sqlite3
import datetime
from pathlib import Path
from typing import Generator, Optional
from contextlib import contextmanager

import app.config as config
from app.config import SCHEMA_PATH, BACKUP_DIR, SQLITE_TIMEOUT_SECONDS


def get_db_connection(database_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Crea y configura una nueva conexión SQLite aplicando pragmas mandatorios de rendimiento y seguridad.

    Parámetros:
        database_path (Optional[Path]): Ruta al archivo de base de datos SQLite. Si es None, usa config.DB_PATH.

    Retorna:
        sqlite3.Connection: Conexión configurada con row_factory como Row y timeout de 10 segundos.

    Lanza:
        sqlite3.OperationalError: Si el archivo está bloqueado o inaccesible.
    """
    if database_path is None:
        database_path = config.DB_PATH

    conn = sqlite3.connect(
        database_path,
        timeout=SQLITE_TIMEOUT_SECONDS,
        isolation_level=None  # Modo autocommit manual; el control de transacciones se gestiona explícitamente
    )
    conn.row_factory = sqlite3.Row

    # Pragmas mandatorios para robustez y concurrencia
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute(f"PRAGMA busy_timeout = {int(SQLITE_TIMEOUT_SECONDS * 1000)};")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA encoding = 'UTF-8';")
    cursor.close()

    return conn


@contextmanager
def get_db(database_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Generador de contexto para uso estándar de lectura o inyección de dependencias en FastAPI.
    Garantiza el cierre automático de la conexión tras su uso.

    Parámetros:
        database_path (Optional[Path]): Ruta a la base de datos.
    """
    conn = get_db_connection(database_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def atomic_transaction(database_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Gestor de contexto para transacciones atómicas con bloqueo inmediato (BEGIN IMMEDIATE).

    Garantiza que la transacción adquiera el cerrojo de escritura de inmediato,
    evitando bloqueos intermedios y deadlocks durante validaciones de stock.
    Si ocurre cualquier excepción, ejecuta automáticamente un ROLLBACK completo.
    Al finalizar con éxito, ejecuta un COMMIT explícito.

    Parámetros:
        database_path (Optional[Path]): Ruta a la base de datos.

    Lanza:
        Exception: Re-lanza cualquier excepción producida dentro del bloque tras realizar ROLLBACK.
    """
    conn = get_db_connection(database_path)
    try:
        conn.execute("BEGIN IMMEDIATE;")
        yield conn
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise
    finally:
        conn.close()


def init_db(database_path: Optional[Path] = None, schema_file: Optional[Path] = None) -> None:
    """
    Inicializa la base de datos ejecutando el esquema DDL y semillas si las tablas no existen.

    Parámetros:
        database_path (Optional[Path]): Destino del archivo de base de datos.
        schema_file (Optional[Path]): Archivo que contiene el script DDL SQLite.

    Lanza:
        FileNotFoundError: Si no se encuentra el archivo schema.sql.
        sqlite3.Error: Si ocurre un error de sintaxis o ejecución DDL.
    """
    if database_path is None:
        database_path = config.DB_PATH
    if schema_file is None:
        schema_file = config.SCHEMA_PATH

    if not schema_file.exists():
        raise FileNotFoundError(f"No se encontró el archivo de esquema en {schema_file}")

    with schema_file.open("r", encoding="utf-8") as f:
        schema_sql = f.read()

    # Ejecutar en conexión directa con commits manuales
    conn = sqlite3.connect(database_path, timeout=SQLITE_TIMEOUT_SECONDS)
    try:
        # Migración previa defensiva e idempotente:
        # Si comanda_detalles ya existía sin las nuevas columnas, debemos incorporarlas
        # ANTES de ejecutar el script DDL que crea índices dependientes como idx_comanda_detalles_estado.
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comanda_detalles';")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(comanda_detalles);")
            columnas_existentes = [row[1] for row in cursor.fetchall()]

            if "estado" not in columnas_existentes:
                cursor.execute("ALTER TABLE comanda_detalles ADD COLUMN estado TEXT NOT NULL DEFAULT 'En preparación';")
            if "descontado_stock" not in columnas_existentes:
                cursor.execute("ALTER TABLE comanda_detalles ADD COLUMN descontado_stock INTEGER NOT NULL DEFAULT 0;")
            if "servido_en" not in columnas_existentes:
                cursor.execute("ALTER TABLE comanda_detalles ADD COLUMN servido_en TIMESTAMP;")

            conn.commit()

        # Ejecutar script DDL del esquema
        conn.executescript(schema_sql)
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def backup_database(database_path: Optional[Path] = None, backup_folder: Optional[Path] = None) -> Path:
    """
    Realiza una copia de seguridad en caliente (online snapshot) de la base de datos usando la API nativa de SQLite.

    Esta operación es atómica y no interrumpe a los lectores ni escritores concurrentes.

    Parámetros:
        database_path (Optional[Path]): Ruta del archivo origen `.db`.
        backup_folder (Optional[Path]): Carpeta donde se almacenará la copia timestamped.

    Retorna:
        Path: Ruta completa del archivo de respaldo generado.

    Lanza:
        sqlite3.Error: Si falla la operación de respaldo.
    """
    if database_path is None:
        database_path = config.DB_PATH
    if backup_folder is None:
        backup_folder = config.BACKUP_DIR
    backup_folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"cafeteria_backup_{timestamp}.db"
    backup_target = backup_folder / backup_filename

    # Conectar origen y destino para ejecutar backup nativo
    source_conn = get_db_connection(database_path)
    dest_conn = sqlite3.connect(backup_target)
    try:
        # sqlite3 backup API nativa
        source_conn.backup(dest_conn, pages=100, sleep=0.01)
    finally:
        dest_conn.close()
        source_conn.close()

    return backup_target
