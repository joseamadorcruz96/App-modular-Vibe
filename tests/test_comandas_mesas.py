"""
Pruebas Automatizadas para el Flujo de Mesas Abiertas y Comandas de Salón.

Valida:
1. Apertura de comanda en mesa libre.
2. Restricción de concurrencia: bloqueo de segunda comanda en mesa ocupada.
3. Adición de múltiples rondas de pedidos acumulados.
4. Consulta del estado en tiempo real del salón (mesas libres vs ocupadas).
5. Liquidación y cobro de comanda: emisión de ticket, descuento de stock y liberación de mesa.
6. Cancelación de comanda sin cobro ni alteración de existencias.
"""

# pyrefly: ignore [missing-import]
import pytest
from pathlib import Path

from app.database import init_db, get_db_connection, atomic_transaction
from app.services.comanda_service import ComandaService
from app.services.product_service import ProductoService
from app.services.order_service import OrderService
from app.models.schemas import (
    ComandaCreate,
    ComandaItemAdd,
    ComandaCheckout,
)


@pytest.fixture
def test_db(tmp_path: Path):
    """Crea una base de datos aislada para cada prueba."""
    db_file = tmp_path / "test_comandas.db"
    schema_file = Path(__file__).resolve().parent.parent / "data" / "schema.sql"
    seeds_file = Path(__file__).resolve().parent.parent / "data" / "seeds.sql"
    init_db(db_file, schema_file)
    from app.services.caja_service import CajaService
    CajaService.cargar_semillas_demo(db_file, seeds_file)
    return db_file


def test_abrir_comanda_y_restriccion_duplicada(test_db: Path):
    """Verifica la apertura de comanda y el bloqueo para no abrir dos comandas en la misma mesa."""
    conn = get_db_connection(test_db)
    try:
        # 1. Abrir comanda en Mesa 1
        cmd = ComandaService.abrir_comanda(conn, ComandaCreate(
            mesa="Mesa 1",
            cliente="Familia González"
        ))
        assert cmd["id"] > 0
        assert cmd["mesa"] == "Mesa 1"
        assert cmd["estado"] == "Abierta"
        assert cmd["numero_comanda"].startswith("CMD-")

        # 2. Intentar abrir otra comanda en la misma Mesa 1 (debe fallar)
        with pytest.raises(ValueError) as exc_info:
            ComandaService.abrir_comanda(conn, ComandaCreate(
                mesa="Mesa 1",
                cliente="Otro Cliente"
            ))
        assert "ya tiene una comanda abierta" in str(exc_info.value)
    finally:
        conn.close()


def test_agregar_rondas_y_estado_salon(test_db: Path):
    """Verifica acumular pedidos en una mesa y consultar el mapa de ocupación del salón."""
    conn = get_db_connection(test_db)
    try:
        # Abrir Mesa 3
        cmd = ComandaService.abrir_comanda(conn, ComandaCreate(mesa="Mesa 3", cliente="Carlos"))
        cmd_id = cmd["id"]

        # Ronda 1: 2 Espressos ($1800 c/u) = $3600
        ComandaService.agregar_items_comanda(conn, cmd_id, [
            ComandaItemAdd(producto_id=1, cantidad=2, notas="un café bien caliente")
        ])

        # Ronda 2: 1 Croissant ($2200)
        cmd_actualizada = ComandaService.agregar_items_comanda(conn, cmd_id, [
            ComandaItemAdd(producto_id=7, cantidad=1)
        ])

        assert cmd_actualizada["subtotal"] == 5800.0
        assert cmd_actualizada["total_items"] == 3
        assert len(cmd_actualizada["detalles"]) == 2

        # Consultar mapa de estado de mesas (suponiendo 8 mesas)
        estados = ComandaService.listar_estado_mesas(conn, total_mesas=8)
        assert len(estados) == 8

        m3 = next(m for m in estados if m["mesa"] == "Mesa 3")
        assert m3["ocupada"] is True
        assert m3["subtotal"] == 5800.0
        assert m3["comanda_id"] == cmd_id

        m1 = next(m for m in estados if m["mesa"] == "Mesa 1")
        assert m1["ocupada"] is False
        assert m1["subtotal"] == 0.0
    finally:
        conn.close()


def test_cobro_comanda_y_liberacion_mesa(test_db: Path):
    """Verifica que al liquidar la comanda se emita el ticket, se descuente stock y se libere la mesa."""
    conn = get_db_connection(test_db)
    try:
        # Abrir Mesa 2 y agregar 1 Croissant (prod_id=7, stock inicial 12)
        p7_pre = ProductoService.obtener_por_id(conn, 7)["stock_actual"]
        cmd = ComandaService.abrir_comanda(conn, ComandaCreate(mesa="Mesa 2", cliente="Ana"))
        ComandaService.agregar_items_comanda(conn, cmd["id"], [
            ComandaItemAdd(producto_id=7, cantidad=2)
        ])

        # Cobrar la comanda
        checkout_data = ComandaCheckout(medio_pago="Tarjeta de Débito", descuento=0.0)
        with atomic_transaction(test_db) as tx_conn:
            pedido_res = OrderService.procesar_checkout_comanda(tx_conn, cmd["id"], checkout_data)

        assert pedido_res["id"] > 0
        assert pedido_res["numero_ticket"].startswith("TCK-")
        assert pedido_res["total"] == 4400.0

        # Verificar que el stock de Croissant disminuyó en 2
        p7_post = ProductoService.obtener_por_id(conn, 7)["stock_actual"]
        assert p7_post == p7_pre - 2

        # Verificar que la comanda cambió a estado 'Cobrada'
        cmd_final = ComandaService.obtener_comanda_por_id(conn, cmd["id"])
        assert cmd_final["estado"] == "Cobrada"

        # Verificar que Mesa 2 ahora figura como LIBRE
        estados = ComandaService.listar_estado_mesas(conn, total_mesas=8)
        m2 = next(m for m in estados if m["mesa"] == "Mesa 2")
        assert m2["ocupada"] is False
    finally:
        conn.close()


def test_cancelar_comanda_sin_cobro(test_db: Path):
    """Verifica que una comanda cancelada libere la mesa sin generar tickets ni descontar stock."""
    conn = get_db_connection(test_db)
    try:
        cmd = ComandaService.abrir_comanda(conn, ComandaCreate(mesa="Mesa 5", cliente="Pedro"))
        ComandaService.agregar_items_comanda(conn, cmd["id"], [
            ComandaItemAdd(producto_id=1, cantidad=1)
        ])

        p1_pre = ProductoService.obtener_por_id(conn, 1)["stock_actual"]

        # Cancelar comanda
        res_canc = ComandaService.cancelar_comanda(conn, cmd["id"])
        assert res_canc["estado"] == "Cancelada"

        # Comprobar que no se descontó stock
        p1_post = ProductoService.obtener_por_id(conn, 1)["stock_actual"]
        assert p1_post == p1_pre

        # Comprobar que Mesa 5 quedó libre
        estados = ComandaService.listar_estado_mesas(conn, total_mesas=8)
        m5 = next(m for m in estados if m["mesa"] == "Mesa 5")
        assert m5["ocupada"] is False
    finally:
        conn.close()
