"""
Router de Pedidos, Checkout Atómico y Comandas para CoffeePOS.

Expone los endpoints para registrar ventas con validación de existencias ACID y consultar tickets.
"""

from fastapi import APIRouter, HTTPException, status

from app.config import DB_PATH
from app.database import get_db, atomic_transaction
from app.models.schemas import PedidoCreate, PedidoResponse
from app.services.order_service import OrderService, StockInsuficienteError

router = APIRouter(prefix="/api/pedidos", tags=["Pedidos & TPV"])


@router.post("", response_model=PedidoResponse, status_code=status.HTTP_201_CREATED, summary="Checkout Atómico de Comanda")
def crear_pedido(pedido_data: PedidoCreate) -> dict:
    """
    Procesa el cobro de una comanda en una sola transacción atómica ACID:
    - Valida que todos los productos existan y tengan stock suficiente.
    - Si algún producto no tiene existencias, aborta la operación completa (ROLLBACK).
    - Descuenta las existencias, registra el pedido y emite el número de ticket.
    """
    try:
        with atomic_transaction() as tx_conn:
            return OrderService.procesar_checkout(tx_conn, pedido_data)
    except StockInsuficienteError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "STOCK_INSUFICIENTE",
                "mensaje": str(e),
                "producto_id": e.producto_id,
                "solicitado": e.solicitado,
                "disponible": e.disponible
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado al procesar el pedido: {e}"
        )


@router.get("/{pedido_id}", response_model=PedidoResponse, summary="Obtener ticket de pedido por ID")
def obtener_pedido(pedido_id: int) -> dict:
    """
    Consulta un pedido emitido junto a sus líneas de detalle para reimpresión o consulta.
    """
    with get_db() as conn:
        pedido = OrderService.obtener_pedido_por_id(conn, pedido_id)
        if not pedido:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El pedido con ID {pedido_id} no fue encontrado."
            )
        return pedido
