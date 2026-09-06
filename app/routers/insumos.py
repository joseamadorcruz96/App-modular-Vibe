"""
Router de la API REST para Insumos / Materias Primas y Recetas (Escandallos).
"""

from typing import List
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException, Query, status

from app.database import get_db, atomic_transaction
from app.services.insumo_service import InsumoService
from app.models.schemas import (
    InsumoCreate,
    InsumoUpdate,
    InsumoReabastecer,
    InsumoResponse,
    RecetaConfig,
    RecetaDetalleResponse,
)

router = APIRouter(tags=["Insumos y Recetas"])


# ==============================================================================
# Endpoints de Insumos (CRUD y Reabastecimiento)
# ==============================================================================

@router.get("/api/insumos", response_model=List[InsumoResponse])
def listar_insumos(solo_activos: bool = Query(True, description="Filtrar solo insumos activos")):
    """Obtiene el listado de materias primas con alertas de stock mínimo."""
    with get_db() as conn:
        return InsumoService.listar_insumos(conn, solo_activos=solo_activos)


@router.post("/api/insumos", response_model=InsumoResponse, status_code=status.HTTP_201_CREATED)
def crear_insumo(data: InsumoCreate):
    """Registra una nueva materia prima / insumo."""
    with get_db() as conn:
        try:
            return InsumoService.crear_insumo(conn, data)
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe un insumo con el código '{data.codigo}'."
                )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/api/insumos/{insumo_id}", response_model=InsumoResponse)
def obtener_insumo(insumo_id: int):
    """Consulta un insumo por su identificador único."""
    with get_db() as conn:
        insumo = InsumoService.obtener_por_id(conn, insumo_id)
        if not insumo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Insumo con ID {insumo_id} no encontrado."
            )
        return insumo


@router.put("/api/insumos/{insumo_id}", response_model=InsumoResponse)
def actualizar_insumo(insumo_id: int, data: InsumoUpdate):
    """Actualiza propiedades o costos de un insumo existente."""
    with get_db() as conn:
        try:
            actualizado = InsumoService.actualizar_insumo(conn, insumo_id, data)
            if not actualizado:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Insumo con ID {insumo_id} no encontrado."
                )
            return actualizado
        except HTTPException:
            raise
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"El código '{data.codigo}' ya pertenece a otro insumo."
                )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/api/insumos/{insumo_id}/reabastecer", response_model=InsumoResponse)
def reabastecer_insumo(insumo_id: int, data: InsumoReabastecer):
    """Incrementa las existencias físicas de un insumo."""
    with get_db() as conn:
        insumo = InsumoService.reabastecer_insumo(conn, insumo_id, data.cantidad)
        if not insumo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Insumo con ID {insumo_id} no encontrado."
            )
        return insumo


@router.delete("/api/insumos/{insumo_id}")
def eliminar_insumo(insumo_id: int, forzar: bool = Query(False, description="Forzar eliminación física desvinculando de recetas existentes")):
    """Elimina físicamente el insumo o lo desactiva lógicamente si está asignado a recetas (a menos que forzar sea True)."""
    with get_db() as conn:
        insumo = InsumoService.obtener_por_id(conn, insumo_id)
        if not insumo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Insumo con ID {insumo_id} no encontrado."
            )
        return InsumoService.eliminar_insumo(conn, insumo_id, forzar=forzar)


# ==============================================================================
# Endpoints de Recetas (Escandallo de Producto)
# ==============================================================================

@router.get("/api/productos/{producto_id}/receta", response_model=RecetaDetalleResponse)
def obtener_receta_producto(producto_id: int):
    """Recupera la receta de un producto con desglose de insumos, costo total y márgenes."""
    with get_db() as conn:
        receta = InsumoService.obtener_receta_producto(conn, producto_id)
        if not receta:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Producto con ID {producto_id} no encontrado."
            )
        return receta


@router.post("/api/productos/{producto_id}/receta", response_model=RecetaDetalleResponse)
def guardar_receta_producto(producto_id: int, data: RecetaConfig):
    """Configura o reemplaza la lista de insumos y proporciones para la receta del producto."""
    try:
        with atomic_transaction() as conn:
            return InsumoService.guardar_receta_producto(conn, producto_id, data.ingredientes)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/api/productos/{producto_id}/receta")
def eliminar_receta_producto(producto_id: int):
    """Elimina la receta del producto, regresándolo a control de stock unitario simple."""
    with get_db() as conn:
        InsumoService.eliminar_receta_producto(conn, producto_id)
        return {"producto_id": producto_id, "mensaje": "Receta eliminada. El producto ahora es simple."}
