"""
Pruebas de Concurrencia y Resiliencia para CoffeePOS.

Verifica la integridad de datos bajo peticiones simultáneas:
Dos hilos concurrentes intentan comprar la última unidad de un producto al mismo tiempo.
Resultado esperado: Uno de los pedidos se completa con éxito, el otro es rechazado,
y el stock final resultante es exactamente 0 (sin sobreventa ni stock negativo).
"""

import concurrent.futures
from pathlib import Path
# pyrefly: ignore [missing-import]
import pytest

from app.database import init_db, get_db_connection, atomic_transaction
from app.services.product_service import ProductoService
from app.services.order_service import OrderService, StockInsuficienteError
from app.models.schemas import PedidoCreate, ItemPedidoCreate


@pytest.fixture
def db_concurrente(tmp_path: Path):
    db_file = tmp_path / "concurrencia.db"
    schema_file = Path(__file__).resolve().parent.parent / "data" / "schema.sql"
    seeds_file = Path(__file__).resolve().parent.parent / "data" / "seeds.sql"
    init_db(db_file, schema_file)
    from app.services.caja_service import CajaService
    CajaService.cargar_semillas_demo(db_file, seeds_file)
    return db_file


def test_concurrencia_compra_simultanea_ultimo_stock(db_concurrente: Path):
    """
    Prueba de colisión concurrente:
    Producto con exactamente 1 unidad en stock.
    Dos clientes intentan comprar simultáneamente 1 unidad.
    """
    # Ajustar stock del producto 1 a exactamente 1 unidad
    conn = get_db_connection(db_concurrente)
    try:
        conn.execute("UPDATE productos SET stock_actual = 1 WHERE id = 1;")
    finally:
        conn.close()

    def intentar_cobro(nombre_cliente: str, mesa: str):
        pedido = PedidoCreate(
            mesa=mesa,
            cliente=nombre_cliente,
            medio_pago="Efectivo",
            items=[ItemPedidoCreate(producto_id=1, cantidad=1)]
        )
        try:
            with atomic_transaction(db_concurrente) as tx_conn:
                res = OrderService.procesar_checkout(tx_conn, pedido)
                return ("OK", res)
        except StockInsuficienteError as e:
            return ("STOCK_ERROR", str(e))
        except Exception as e:
            return ("OTHER_ERROR", str(e))

    # Lanzar 2 peticiones concurrentes mediante ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(intentar_cobro, "Cliente A", "Mesa 1")
        f2 = executor.submit(intentar_cobro, "Cliente B", "Mesa 2")

        r1 = f1.result()
        r2 = f2.result()

    resultados = [r1[0], r2[0]]

    # Exactamente una debe ser exitosa y la otra debe haber sido rechazada por falta de stock
    assert "OK" in resultados, "Al menos una compra debió tener éxito"
    assert "STOCK_ERROR" in resultados, "La segunda compra debió ser rechazada por stock insuficiente"

    # Verificar stock final en base de datos: debe ser exactamente 0
    conn_final = get_db_connection(db_concurrente)
    try:
        prod = ProductoService.obtener_por_id(conn_final, 1)
        assert prod["stock_actual"] == 0, f"El stock final debe ser 0, pero es {prod['stock_actual']}"

        # Verificar que solo se emitió 1 ticket
        cursor = conn_final.cursor()
        cursor.execute("SELECT COUNT(*) FROM pedidos;")
        assert cursor.fetchone()[0] == 1, "Solo debió registrarse 1 pedido en la base de datos"
    finally:
        conn_final.close()
