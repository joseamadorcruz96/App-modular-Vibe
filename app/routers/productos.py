"""
Router de Catálogo de Productos e Inventario para CoffeePOS.

Expone endpoints para listar con búsqueda en tiempo real, crear nuevos productos,
actualizar fichas y ejecutar el reabastecimiento rápido de stock.
"""

import sqlite3
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.database import get_db, atomic_transaction
from app.models.schemas import (
    ProductoResponse, ProductoCreate, ProductoUpdate, ProductoReabastecer,
    ProductoBulkRequest, ProductoBulkResponse
)
from app.services.product_service import ProductoService

router = APIRouter(prefix="/api/productos", tags=["Productos"])


@router.get("", response_model=List[ProductoResponse], summary="Listar catálogo de productos")
def listar_productos(
    solo_activos: bool = Query(True, description="Filtrar únicamente productos activos"),
    busqueda: Optional[str] = Query(None, description="Término para filtrar por código o nombre")
) -> List[dict]:
    """
    Retorna la lista de productos disponibles con el flag alerta_stock (<= 5).
    """
    with get_db() as conn:
        return ProductoService.listar_productos(conn, solo_activos=solo_activos, busqueda=busqueda)


@router.get("/{producto_id}", response_model=ProductoResponse, summary="Obtener producto por ID")
def obtener_producto(producto_id: int) -> dict:
    """
    Recupera el detalle de un producto específico.
    """
    with get_db() as conn:
        prod = ProductoService.obtener_por_id(conn, producto_id)
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Producto con ID {producto_id} no encontrado."
            )
        return prod


@router.post("/bulk", response_model=ProductoBulkResponse, status_code=status.HTTP_200_OK, summary="Importar o reabastecer productos masivamente con IA")
def importar_productos_bulk(datos: ProductoBulkRequest) -> dict:
    """
    Importa un lote de productos procesados mediante IA o archivo.
    Si un producto ya existe, suma las existencias al stock actual o lo omite según el modo configurado.
    La operación se ejecuta en una transacción atómica protegida con rollback.
    """
    try:
        with atomic_transaction() as conn:
            return ProductoService.importar_lote_productos(conn, datos)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Error durante el procesamiento masivo del lote: {str(e)}"
        )


@router.post("", response_model=ProductoResponse, status_code=status.HTTP_201_CREATED, summary="Registrar nuevo producto")
def crear_producto(datos: ProductoCreate) -> dict:
    """
    Crea un nuevo producto validando la unicidad del código.
    """
    with get_db() as conn:
        try:
            return ProductoService.crear_producto(conn, datos)
        except sqlite3.IntegrityError as e:
            error_str = str(e).lower()
            if "unique" in error_str:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe un producto con el código '{datos.codigo}'."
                )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Error de restricción de datos: {e}"
            )


@router.put("/{producto_id}", response_model=ProductoResponse, summary="Modificar producto existente")
def actualizar_producto(producto_id: int, datos: ProductoUpdate) -> dict:
    """
    Actualiza campos de un producto validando unicidad de código y límites de stock.
    """
    with get_db() as conn:
        try:
            prod = ProductoService.actualizar_producto(conn, producto_id, datos)
            if not prod:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Producto con ID {producto_id} no encontrado."
                )
            return prod
        except sqlite3.IntegrityError as e:
            error_str = str(e).lower()
            if "unique" in error_str:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe otro producto con el código especificado."
                )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Error de restricción o integridad: {e}"
            )


@router.delete("/{producto_id}", summary="Eliminar producto del inventario")
def eliminar_producto(producto_id: int) -> dict:
    """
    Elimina un producto del catálogo respetando la integridad referencial:
    - Si tiene ventas históricas asociadas, se desactiva (borrado lógico).
    - Si no tiene ventas, se elimina físicamente.
    """
    with get_db() as conn:
        try:
            return ProductoService.eliminar_producto(conn, producto_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al eliminar producto: {e}"
            )


@router.post("/{producto_id}/reabastecer", response_model=ProductoResponse, summary="Reabastecimiento rápido de stock")
def reabastecer_producto(producto_id: int, datos: ProductoReabastecer) -> dict:
    """
    Suma unidades al stock actual y stock inicial de forma coherente.
    """
    with get_db() as conn:
        prod = ProductoService.reabastecer_producto(conn, producto_id, datos.cantidad)
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Producto con ID {producto_id} no encontrado."
            )
        return prod
