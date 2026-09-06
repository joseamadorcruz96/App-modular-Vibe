"""
Router de la API REST para Comandas de Salón (Mesas Abiertas).
"""

from typing import List
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException, status

from app.database import get_db, atomic_transaction
from app.services.comanda_service import ComandaService
from app.services.order_service import OrderService, StockInsuficienteError
from app.models.schemas import (
    ComandaCreate,
    ComandaItemBatchAdd,
    ComandaResponse,
    MesaEstadoResponse,
    ComandaCheckout,
    PedidoResponse,
)

router = APIRouter(prefix="/api/comandas", tags=["Comandas y Mesas"])


@router.get("/mesas-estado", response_model=List[MesaEstadoResponse])
def listar_estado_mesas():
    """Retorna el mapa del salón con el estado de cada mesa (Libre u Ocupada con subtotal)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT valor FROM configuracion WHERE clave = 'mesas_activas';")
        row = cursor.fetchone()
        total_mesas = int(row["valor"]) if row else 8
        cursor.close()
        return ComandaService.listar_estado_mesas(conn, total_mesas)


@router.get("/mesa/{mesa}", response_model=ComandaResponse)
def obtener_comanda_por_mesa(mesa: str):
    """Consulta la comanda activa asignada a una mesa específica."""
    with get_db() as conn:
        comanda = ComandaService.obtener_comanda_activa_mesa(conn, mesa)
        if not comanda:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No hay comanda abierta en '{mesa}'."
            )
        return comanda


@router.get("/{comanda_id}", response_model=ComandaResponse)
def obtener_comanda(comanda_id: int):
    """Obtiene los detalles completos de una comanda por su ID."""
    with get_db() as conn:
        comanda = ComandaService.obtener_comanda_por_id(conn, comanda_id)
        if not comanda:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Comanda ID {comanda_id} no encontrada."
            )
        return comanda


@router.post("/abrir", response_model=ComandaResponse, status_code=status.HTTP_201_CREATED)
def abrir_comanda(data: ComandaCreate):
    """Abre una nueva mesa en el salón."""
    with get_db() as conn:
        try:
            return ComandaService.abrir_comanda(conn, data)
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{comanda_id}/items", response_model=ComandaResponse)
def agregar_items_comanda(comanda_id: int, data: ComandaItemBatchAdd):
    """Agrega una ronda de consumos a una comanda abierta."""
    with get_db() as conn:
        try:
            return ComandaService.agregar_items_comanda(conn, comanda_id, data.items)
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{comanda_id}/items/{detalle_id}", response_model=ComandaResponse)
def eliminar_item_comanda(comanda_id: int, detalle_id: int):
    """Elimina una línea específica de una comanda abierta."""
    with get_db() as conn:
        try:
            return ComandaService.eliminar_item_comanda(conn, comanda_id, detalle_id)
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post("/{comanda_id}/checkout", response_model=PedidoResponse)
def cobrar_comanda(comanda_id: int, checkout_data: ComandaCheckout):
    """
    Liquida la comanda de la mesa:
    Descuenta inventario (recetas o stock simple), registra el ticket de cobro
    y libera la mesa para nuevos clientes.
    """
    try:
        with atomic_transaction() as conn:
            return OrderService.procesar_checkout_comanda(conn, comanda_id, checkout_data)
    except StockInsuficienteError as sie:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(sie))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{comanda_id}/cancelar")
def cancelar_comanda(comanda_id: int):
    """Anula la comanda y libera la mesa sin generar cobro."""
    with get_db() as conn:
        try:
            return ComandaService.cancelar_comanda(conn, comanda_id)
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
