"""
Router de Acciones Críticas y Mantenimiento del Sistema para CoffeePOS.

Controla el reinicio global de stock a valores iniciales y la restauración
de fábrica de la base de datos protegida mediante palabra de seguridad.
"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any

import app.config as config
from app.database import get_db
from app.models.schemas import ReiniciarStockRequest, LimpiezaTotalRequest
from app.services.product_service import ProductoService
from app.services.caja_service import CajaService

router = APIRouter(prefix="/api/sistema", tags=["Mantenimiento"])


@router.post("/reiniciar-stock", summary="Restablecer stock actual a stock inicial")
def reiniciar_stock(datos: ReiniciarStockRequest) -> Dict[str, Any]:
    """
    Restaura el valor de `stock_actual` al `stock_inicial` en todos los productos del catálogo.
    """
    if not datos.confirmar:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe confirmar explícitamente la acción con confirmar: true."
        )

    with get_db() as conn:
        afectados = ProductoService.reiniciar_stock_a_inicial(conn)

    return {
        "status": "success",
        "mensaje": f"Stock restablecido al valor inicial para {afectados} productos.",
        "productos_afectados": afectados
    }


@router.post("/limpieza-total", summary="Restauración de fábrica total")
def limpieza_total(datos: LimpiezaTotalRequest) -> Dict[str, Any]:
    """
    Purga todos los pedidos, detalles y datos operativos, restaurando la base de datos
    a su estado original inicial. Exige la palabra clave 'borrar'.
    """
    if datos.palabra_clave.strip().lower() != "borrar":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Palabra clave incorrecta. Escriba exactamente 'borrar' para proceder."
        )

    try:
        CajaService.limpiar_base_datos_total(config.DB_PATH, config.SCHEMA_PATH)
        return {
            "status": "success",
            "mensaje": "Base de datos restaurada al estado original de fábrica exitosamente."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante la restauración de fábrica: {e}"
        )


@router.post("/cargar-demo", summary="Cargar catálogo de productos de demostración")
def cargar_demo() -> Dict[str, Any]:
    """
    Inserta las semillas de prueba opcionales de cafetería desde seeds.sql.
    """
    try:
        total_prods = CajaService.cargar_semillas_demo(config.DB_PATH, config.SEEDS_PATH)
        return {
            "status": "success",
            "mensaje": f"Catálogo de demostración cargado exitosamente ({total_prods} productos disponibles).",
            "total_productos": total_prods
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al cargar catálogo demo: {e}"
        )
