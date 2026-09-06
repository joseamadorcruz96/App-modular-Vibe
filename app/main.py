"""
Punto de Entrada Principal de la Aplicación CoffeePOS.

Configura la instancia de FastAPI, monta routers REST, sirve archivos estáticos
e inicializa la base de datos de forma automática en el arranque del servidor.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import APP_TITLE, APP_VERSION, DB_PATH, SCHEMA_PATH
from app.database import init_db
from app.routers import configuracion, productos, pedidos, caja, sistema, insumos, comandas


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manejador del ciclo de vida de la aplicación.
    Verifica e inicializa el esquema y las semillas de SQLite en el inicio.
    """
    # Inicializar base de datos si no existe o faltan tablas
    init_db(DB_PATH, SCHEMA_PATH)
    yield


app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description="Sistema TPV local, liviano y portable con transacciones ACID para cafeterías.",
    lifespan=lifespan
)

# Permitir solicitudes locales sin restricciones de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar Routers de la API REST
app.include_router(configuracion.router)
app.include_router(productos.router)
app.include_router(pedidos.router)
app.include_router(caja.router)
app.include_router(sistema.router)
app.include_router(insumos.router)
app.include_router(comandas.router)

# Montar directorio de recursos estáticos del Frontend
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def index():
    """Sirve la interfaz principal de la aplicación TPV (SPA)."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"mensaje": "CoffeePOS API activa. Visite /docs para la documentación interactiva Swagger."}


@app.get("/ticket-preview", include_in_schema=False)
def ticket_preview():
    """Sirve la plantilla imprimible de comprobante térmico."""
    ticket_file = STATIC_DIR / "ticket.html"
    if ticket_file.exists():
        return FileResponse(str(ticket_file))
    return {"mensaje": "Plantilla de ticket no encontrada."}
