"""
Módulo de Configuración Central de CoffeePOS.
Define rutas del sistema, constantes de conexión a SQLite y parámetros operativos.
"""

from pathlib import Path

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Directorio de persistencia de datos
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Ruta del archivo de base de datos SQLite
DB_PATH = DATA_DIR / "cafeteria.db"

# Ruta del esquema SQL DDL
SCHEMA_PATH = DATA_DIR / "schema.sql"

# Ruta de las semillas opcionales de demostración
SEEDS_PATH = DATA_DIR / "seeds.sql"

# Directorio de copias de seguridad automáticas
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# Parámetros de resiliencia y concurrencia para SQLite
SQLITE_TIMEOUT_SECONDS = 10.0

# Configuración del servidor
APP_TITLE = "CoffeePOS - Sistema TPV & Gestión"
APP_VERSION = "1.0.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
