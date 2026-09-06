"""
Router de Configuración Operativa para CoffeePOS.

Permite consultar y ajustar parámetros globales como el número de mesas activas,
nombre comercial y formato de impresión de comprobantes.
"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any

from app.database import get_db, get_db_connection
from app.models.schemas import ConfiguracionResponse, ConfiguracionUpdate

router = APIRouter(prefix="/api/configuracion", tags=["Configuración"])


@router.get("", response_model=ConfiguracionResponse, summary="Obtener configuración activa")
def obtener_configuracion() -> Dict[str, Any]:
    """
    Recupera los parámetros de configuración vigentes de la tabla `configuracion`.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT clave, valor FROM configuracion;")
        rows = cursor.fetchall()
        config_dict = {row["clave"]: row["valor"] for row in rows}

    return {
        "mesas_activas": int(config_dict.get("mesas_activas", 8)),
        "nombre_local": config_dict.get("nombre_local", "CoffeePOS Stand"),
        "moneda_simbolo": config_dict.get("moneda_simbolo", "$"),
        "formato_ticket": config_dict.get("formato_ticket", "80mm")
    }


@router.put("", response_model=ConfiguracionResponse, summary="Actualizar configuración")
def actualizar_configuracion(datos: ConfiguracionUpdate) -> Dict[str, Any]:
    """
    Actualiza la cantidad de mesas activas o el nombre comercial de la tienda.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        if datos.mesas_activas is not None:
            cursor.execute(
                """
                INSERT INTO configuracion (clave, valor, actualizado_en)
                VALUES ('mesas_activas', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor, actualizado_en = CURRENT_TIMESTAMP;
                """,
                (str(datos.mesas_activas),)
            )

        if datos.nombre_local is not None:
            cursor.execute(
                """
                INSERT INTO configuracion (clave, valor, actualizado_en)
                VALUES ('nombre_local', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor, actualizado_en = CURRENT_TIMESTAMP;
                """,
                (datos.nombre_local,)
            )

        if datos.formato_ticket is not None:
            cursor.execute(
                """
                INSERT INTO configuracion (clave, valor, actualizado_en)
                VALUES ('formato_ticket', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor, actualizado_en = CURRENT_TIMESTAMP;
                """,
                (datos.formato_ticket,)
            )

    return obtener_configuracion()
