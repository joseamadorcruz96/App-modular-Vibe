"""
Pruebas Automatizadas para Gestión de Insumos, Recetas (Escandallos) y Márgenes.

Valida:
1. CRUD y reabastecimiento de materias primas (insumos).
2. Formulación de recetas por producto con cálculo dinámico de costo y margen ($ y %).
3. Descuento atómico de insumos al procesar ventas de productos con receta.
4. Rollback transaccional ante existencias insuficientes de insumos.
5. Eliminación de recetas y compatibilidad con productos unitarios simples.
"""

# pyrefly: ignore [missing-import]
import pytest
from pathlib import Path

from app.database import init_db, get_db_connection, atomic_transaction
from app.services.insumo_service import InsumoService
from app.services.product_service import ProductoService
from app.services.order_service import OrderService, StockInsuficienteError
from app.models.schemas import (
    InsumoCreate,
    InsumoUpdate,
    RecetaItemCreate,
    ProductoCreate,
    PedidoCreate,
    ItemPedidoCreate,
)


@pytest.fixture
def test_db(tmp_path: Path):
    """Crea una base de datos aislada para cada prueba."""
    db_file = tmp_path / "test_insumos.db"
    schema_file = Path(__file__).resolve().parent.parent / "data" / "schema.sql"
    seeds_file = Path(__file__).resolve().parent.parent / "data" / "seeds.sql"
    init_db(db_file, schema_file)
    from app.services.caja_service import CajaService
    CajaService.cargar_semillas_demo(db_file, seeds_file)
    return db_file


def test_crud_insumos_y_reabastecimiento(test_db: Path):
    """Verifica creación, edición y reabastecimiento de materias primas."""
    conn = get_db_connection(test_db)
    try:
        # Crear insumo
        nuevo_insumo = InsumoCreate(
            codigo="INS-AZUCAR",
            nombre="Azúcar Morena de Caña",
            unidad_medida="g",
            stock_actual=3000.0,
            stock_minimo=500.0,
            costo_unitario=2.5
        )
        ins = InsumoService.crear_insumo(conn, nuevo_insumo)
        assert ins["id"] > 0
        assert ins["codigo"] == "INS-AZUCAR"
        assert ins["stock_actual"] == 3000.0
        assert ins["alerta_stock"] is False

        # Reabastecer (+1500 g)
        ins_reab = InsumoService.reabastecer_insumo(conn, ins["id"], 1500.0)
        assert ins_reab["stock_actual"] == 4500.0

        # Actualizar costo unitario
        ins_upd = InsumoService.actualizar_insumo(conn, ins["id"], InsumoUpdate(costo_unitario=2.8))
        assert ins_upd["costo_unitario"] == 2.8

        # Listar insumos
        todos = InsumoService.listar_insumos(conn)
        assert any(i["codigo"] == "INS-AZUCAR" for i in todos)
    finally:
        conn.close()


def test_formulacion_receta_y_calculo_margen(test_db: Path):
    """Verifica que la receta calcule dinámicamente el costo total por porción y los márgenes de ganancia."""
    conn = get_db_connection(test_db)
    try:
        # Creamos un producto nuevo para configurar su receta
        nuevo_prod = ProductoService.crear_producto(conn, ProductoCreate(
            codigo="CAF-TEST",
            nombre="Café Caramelo Gourmet",
            stock_inicial=50,
            costo_unitario=0.0,
            precio_venta=3500.0
        ))
        prod_id = nuevo_prod["id"]

        # Obtener IDs de insumos existentes (Café y Leche)
        insumos = InsumoService.listar_insumos(conn)
        ins_cafe = next(i for i in insumos if i["codigo"] == "INS-CAFE")
        ins_leche = next(i for i in insumos if i["codigo"] == "INS-LECHE")

        # Configurar receta: 20g Café ($25/g = $500) + 200ml Leche ($1.5/ml = $300) = $800 costo
        receta_config = [
            RecetaItemCreate(insumo_id=ins_cafe["id"], cantidad=20.0),
            RecetaItemCreate(insumo_id=ins_leche["id"], cantidad=200.0),
        ]
        receta = InsumoService.guardar_receta_producto(conn, prod_id, receta_config)

        assert receta["tiene_receta"] is True
        assert receta["costo_receta"] == 800.0
        assert receta["precio_venta"] == 3500.0
        assert receta["margen_bruto"] == 2700.0  # 3500 - 800
        # Margen %: (2700 / 3500) * 100 = 77.14%
        assert round(receta["margen_porcentaje"], 1) == 77.1

        # Comprobar que en la tabla productos se actualizó el costo_unitario
        prod_db = ProductoService.obtener_por_id(conn, prod_id)
        assert prod_db["costo_unitario"] == 800.0
    finally:
        conn.close()


def test_descuento_atomico_insumos_en_checkout(test_db: Path):
    """Verifica que al vender un producto con receta se descuenten exactamente los insumos requeridos."""
    conn = get_db_connection(test_db)
    try:
        # Usamos producto 4 (Capuccino Italiano) que tiene receta: 18g Café + 150ml Leche
        insumos_pre = {i["codigo"]: i["stock_actual"] for i in InsumoService.listar_insumos(conn)}
        cafe_pre = insumos_pre["INS-CAFE"]
        leche_pre = insumos_pre["INS-LECHE"]

        p4_pre = ProductoService.obtener_por_id(conn, 4)["stock_actual"]

        # Pedir 3 Capuccinos
        pedido_data = PedidoCreate(
            mesa="Mesa 1",
            cliente="Cliente Gourmet",
            medio_pago="Efectivo",
            items=[ItemPedidoCreate(producto_id=4, cantidad=3)]
        )

        with atomic_transaction(test_db) as tx_conn:
            res = OrderService.procesar_checkout(tx_conn, pedido_data)

        assert res["id"] > 0

        # Verificar stock de insumos post-venta:
        # Café: - (3 * 18g) = - 54g
        # Leche: - (3 * 150ml) = - 450ml
        insumos_post = {i["codigo"]: i["stock_actual"] for i in InsumoService.listar_insumos(conn)}
        assert insumos_post["INS-CAFE"] == cafe_pre - 54.0
        assert insumos_post["INS-LECHE"] == leche_pre - 450.0

        # Verificar que el producto también descontó sus 3 unidades
        p4_post = ProductoService.obtener_por_id(conn, 4)["stock_actual"]
        assert p4_post == p4_pre - 3
    finally:
        conn.close()


def test_rollback_por_insumo_insuficiente(test_db: Path):
    """Verifica que si un insumo de la receta no alcanza, la transacción entera se anula con rollback."""
    conn = get_db_connection(test_db)
    try:
        # Reducir stock de Leche a solo 100 ml
        insumos = InsumoService.listar_insumos(conn)
        ins_leche = next(i for i in insumos if i["codigo"] == "INS-LECHE")
        conn.execute("UPDATE insumos SET stock_actual = 100.0 WHERE id = ?;", (ins_leche["id"],))

        insumos_pre = {i["codigo"]: i["stock_actual"] for i in InsumoService.listar_insumos(conn)}
        cafe_pre = insumos_pre["INS-CAFE"]
        p4_pre = ProductoService.obtener_por_id(conn, 4)["stock_actual"]

        # Capuccino requiere 150ml de leche por unidad. Pedimos 1 unidad (faltan 50ml).
        pedido_data = PedidoCreate(
            mesa="Mesa 2",
            cliente="Cliente Test",
            medio_pago="Débito",
            items=[ItemPedidoCreate(producto_id=4, cantidad=1)]
        )

        with pytest.raises(StockInsuficienteError) as exc_info:
            with atomic_transaction(test_db) as tx_conn:
                OrderService.procesar_checkout(tx_conn, pedido_data)

        assert "Stock insuficiente" in str(exc_info.value)

        # Comprobar que NINGÚN insumo ni producto fue descontado (Rollback garantizado)
        insumos_post = {i["codigo"]: i["stock_actual"] for i in InsumoService.listar_insumos(conn)}
        assert insumos_post["INS-CAFE"] == cafe_pre
        assert insumos_post["INS-LECHE"] == 100.0

        p4_post = ProductoService.obtener_por_id(conn, 4)["stock_actual"]
        assert p4_post == p4_pre
    finally:
        conn.close()


def test_eliminar_receta_retorno_a_producto_simple(test_db: Path):
    """Verifica que al eliminar la receta el producto vuelve a comportamiento simple."""
    conn = get_db_connection(test_db)
    try:
        # Producto 1 (Espresso) tiene receta
        receta_pre = InsumoService.obtener_receta_producto(conn, 1)
        assert receta_pre["tiene_receta"] is True

        # Eliminar receta
        borrado = InsumoService.eliminar_receta_producto(conn, 1)
        assert borrado is True

        # Ahora el producto no tiene receta
        receta_post = InsumoService.obtener_receta_producto(conn, 1)
        assert receta_post["tiene_receta"] is False
        assert len(receta_post["ingredientes"]) == 0
    finally:
        conn.close()
