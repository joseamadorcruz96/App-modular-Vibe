"""
Router de Cierre de Caja y Reportes Financieros para CoffeePOS.

Proporciona el resumen del día, arqueo por medio de pago y ejecución del cierre
con respaldo automático timestamped en la carpeta /backups.
"""

from typing import Optional
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException, Query, Response, status

from app.database import get_db
from app.models.schemas import ResumenDiarioResponse, CierreCajaResponse, AuditoriaJornadaResponse
from app.services.caja_service import CajaService

router = APIRouter(prefix="/api/caja", tags=["Cierre de Caja & Reportes"])


@router.get("/resumen-diario", response_model=ResumenDiarioResponse, summary="Resumen de ventas del día")
def obtener_resumen_diario(
    fecha: Optional[str] = Query(None, description="Fecha de consulta (YYYY-MM-DD). Por defecto hoy.")
) -> dict:
    """
    Retorna los totales recaudados, conteo de pedidos, desglose por medio de pago
    y el ranking de productos más vendidos.
    """
    with get_db() as conn:
        return CajaService.obtener_resumen_diario(conn, fecha_str=fecha)


@router.get("/auditoria-jornada", response_model=AuditoriaJornadaResponse, summary="Auditoría detallada de comandas y ventas")
def obtener_auditoria_jornada(
    fecha: Optional[str] = Query(None, description="Fecha de consulta (YYYY-MM-DD). Por defecto hoy.")
) -> dict:
    """
    Retorna la auditoría completa con todas las comandas, pedidos cobrados, ítems servidos,
    precios y medios de pago para control financiero y arqueo.
    """
    with get_db() as conn:
        return CajaService.obtener_auditoria_detallada(conn, fecha_str=fecha)


@router.get("/descargar-informe-md", summary="Descargar informe de cierre en formato Markdown")
def descargar_informe_markdown(
    fecha: Optional[str] = Query(None, description="Fecha de consulta (YYYY-MM-DD). Por defecto hoy.")
):
    """
    Genera y descarga el archivo Markdown (.md) con las tablas consolidadas de la jornada.
    """
    with get_db() as conn:
        auditoria = CajaService.obtener_auditoria_detallada(conn, fecha_str=fecha)
        md_content = CajaService.generar_markdown_informe_cierre(auditoria)
        filename = f"cierre_caja_{auditoria['fecha']}.md"
        return Response(
            content=md_content,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


@router.post("/cerrar", response_model=CierreCajaResponse, summary="Ejecutar cierre formal de caja y backup")
def cerrar_caja(
    fecha: Optional[str] = Query(None, description="Fecha a cerrar (YYYY-MM-DD)")
) -> dict:
    """
    Consolida la jornada, genera un backup en caliente (.db) en la subcarpeta /backups
    y registra la auditoría de cierre.
    """
    try:
        with get_db() as conn:
            return CajaService.ejecutar_cierre_caja(conn, fecha_str=fecha)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al ejecutar el cierre de caja: {e}"
        )
