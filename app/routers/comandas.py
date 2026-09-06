"""
Router de la API REST para Comandas de Salón (Mesas Abiertas).
"""

from typing import List, Optional
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException, Query, status

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
    ComandaCancelRequest,
)

router = APIRouter(prefix="/api/comandas", tags=["Comandas y Mesas"])


@router.get("/mesas-estado", response_model=List[MesaEstadoResponse])
def listar_estado_mesas():
    """Retorna el mapa del salón con el estado de cada mesa (Libre u Ocupada con subtotal y estado de comanda)."""
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
    """Agrega una ronda de consumos a una comanda activa en preparación."""
    with get_db() as conn:
        try:
            return ComandaService.agregar_items_comanda(conn, comanda_id, data.items)
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{comanda_id}/servir", response_model=ComandaResponse)
def marcar_comanda_servida(comanda_id: int):
    """
    Marca todos los productos pendientes de la comanda como Servidos,
    descontando atómicamente el stock físico y de insumos en cocina/barra.
    """
    try:
        with atomic_transaction() as conn:
            return ComandaService.marcar_comanda_servida(conn, comanda_id)
    except StockInsuficienteError as sie:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(sie))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{comanda_id}/items/{detalle_id}/servir", response_model=ComandaResponse)
def marcar_item_servido(comanda_id: int, detalle_id: int):
    """
    Marca un ítem individual de la comanda como Servido,
    descontando su stock de inmediato.
    """
    try:
        with atomic_transaction() as conn:
            return ComandaService.marcar_item_servido(conn, comanda_id, detalle_id)
    except StockInsuficienteError as sie:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(sie))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{comanda_id}/items/{detalle_id}", response_model=ComandaResponse)
def eliminar_item_comanda(
    comanda_id: int,
    detalle_id: int,
    restaurar_stock: bool = Query(False, description="Si es True y el ítem ya estaba servido, reintegra el stock; si es False, se asume merma/desperdicio.")
):
    """Elimina una línea específica de una comanda activa."""
    with atomic_transaction() as conn:
        try:
            return ComandaService.eliminar_item_comanda(conn, comanda_id, detalle_id, restaurar_stock=restaurar_stock)
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post("/{comanda_id}/checkout", response_model=PedidoResponse)
def cobrar_comanda(comanda_id: int, checkout_data: ComandaCheckout):
    """
    Liquida la comanda de la mesa:
    Descuenta inventario pendiente (sin duplicar los ítems ya servidos),
    registra el ticket de cobro y libera la mesa para nuevos clientes.
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
def cancelar_comanda(
    comanda_id: int,
    restaurar_stock: bool = Query(False, description="Si es True reintegra inventario servido; si es False (default), se asume merma/desperdicio de alimentos.")
):
    """
    Anula la comanda y libera la mesa.
    Permite decidir si el stock ya servido se reintegra al inventario o se computa como merma sin recuperar.
    """
    with atomic_transaction() as conn:
        try:
            return ComandaService.cancelar_comanda(conn, comanda_id, restaurar_stock=restaurar_stock)
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
