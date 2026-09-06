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


def test_eliminar_insumo_fisico_vs_logico(test_db: Path):
    """Verifica que un insumo sin recetas se elimine físicamente, y uno asignado se desactive lógicamente."""
    conn = get_db_connection(test_db)
    try:
        # 1. Insumo independiente sin recetas
        ins_libre = InsumoService.crear_insumo(conn, InsumoCreate(
            codigo="INS-STEVIA",
            nombre="Sobres de Stevia",
            unidad_medida="unidad",
            stock_actual=100.0,
            stock_minimo=10.0,
            costo_unitario=50.0
        ))
        res_del_libre = InsumoService.eliminar_insumo(conn, ins_libre["id"])
        assert res_del_libre["tipo_eliminacion"] == "fisica"
        assert InsumoService.obtener_por_id(conn, ins_libre["id"]) is None

        # 2. Insumo asignado a receta (Café Grano asignado a Espresso y Capuccino)
        insumos = InsumoService.listar_insumos(conn)
        ins_cafe = next(i for i in insumos if i["codigo"] == "INS-CAFE")
        res_del_usado = InsumoService.eliminar_insumo(conn, ins_cafe["id"])
        assert res_del_usado["tipo_eliminacion"] == "logica"

        # Debe seguir existiendo pero inactivo
        cafe_db = InsumoService.obtener_por_id(conn, ins_cafe["id"])
        assert cafe_db is not None
        assert cafe_db["activo"] == 0
    finally:
        conn.close()


def test_receta_actualizacion_y_margen_negativo(test_db: Path):
    """Verifica actualización completa de ingredientes y cálculo correcto con margen negativo."""
    conn = get_db_connection(test_db)
    try:
        # Producto con precio menor al costo
        nuevo_prod = ProductoService.crear_producto(conn, ProductoCreate(
            codigo="PROMO-PERDIDA",
            nombre="Café Promo Bajo Costo",
            stock_inicial=20,
            costo_unitario=0.0,
            precio_venta=300.0
        ))
        p_id = nuevo_prod["id"]

        insumos = InsumoService.listar_insumos(conn)
        ins_cafe = next(i for i in insumos if i["codigo"] == "INS-CAFE")  # $25/g

        # Receta inicial: 20g Café = $500 costo (Precio $300 -> Pérdida de $200)
        receta1 = InsumoService.guardar_receta_producto(conn, p_id, [
            RecetaItemCreate(insumo_id=ins_cafe["id"], cantidad=20.0)
        ])
        assert receta1["costo_receta"] == 500.0
        assert receta1["margen_bruto"] == -200.0
        assert round(receta1["margen_porcentaje"], 1) == -66.7

        # Actualizar receta: ahora lleva 10g Café = $250 costo (Precio $300 -> Ganancia $50)
        receta2 = InsumoService.guardar_receta_producto(conn, p_id, [
            RecetaItemCreate(insumo_id=ins_cafe["id"], cantidad=10.0)
        ])
        assert receta2["costo_receta"] == 250.0
        assert receta2["margen_bruto"] == 50.0
        assert len(receta2["ingredientes"]) == 1
        assert receta2["ingredientes"][0]["cantidad"] == 10.0

        # Reabastecer insumo inexistente debe retornar None
        assert InsumoService.reabastecer_insumo(conn, 99999, 50.0) is None
    finally:
        conn.close()


def test_eliminar_insumo_forzado_con_recetas(test_db: Path):
    """Verifica que eliminar un insumo con forzar=True limpie las recetas asociadas y borre el insumo físicamente."""
    conn = get_db_connection(test_db)
    try:
        # INS-CHOCO está asignado a CAF06 (Mocaccino)
        insumos = InsumoService.listar_insumos(conn)
        ins_choco = next(i for i in insumos if i["codigo"] == "INS-CHOCO")
        choco_id = ins_choco["id"]

        # 1. Eliminación estándar: debe ser lógica porque está en receta
        res_logica = InsumoService.eliminar_insumo(conn, choco_id, forzar=False)
        assert res_logica["tipo_eliminacion"] == "logica"
        choco_db = InsumoService.obtener_por_id(conn, choco_id)
        assert choco_db is not None
        assert choco_db["activo"] == 0

        # Reactivamos para probar la eliminación forzada
        InsumoService.actualizar_insumo(conn, choco_id, InsumoUpdate(activo=1))

        # 2. Eliminación forzada: debe eliminar registros en receta_detalles y borrar físicamente el insumo
        res_forzada = InsumoService.eliminar_insumo(conn, choco_id, forzar=True)
        assert res_forzada["tipo_eliminacion"] == "fisica"
        assert res_forzada["recetas_desvinculadas"] >= 1

        # Verificar que el insumo ya no existe en la base de datos
        assert InsumoService.obtener_por_id(conn, choco_id) is None

        # Verificar que la receta de CAF06 ya no contiene INS-CHOCO
        prod_mocaccino = next(p for p in ProductoService.listar_productos(conn) if p["codigo"] == "CAF06")
        receta_moca = InsumoService.obtener_receta_producto(conn, prod_mocaccino["id"])
        assert all(ing["insumo_id"] != choco_id for ing in receta_moca["ingredientes"])
    finally:
        conn.close()


def test_crear_producto_con_receta_embebida(test_db: Path):
    """Verifica la creación atómica de un nuevo producto con receta opcional en un solo paso."""
    conn = get_db_connection(test_db)
    try:
        insumos = InsumoService.listar_insumos(conn)
        ins_harina = next(i for i in insumos if i["codigo"] == "INS-HARINA")  # $1.2/g
        ins_leche = next(i for i in insumos if i["codigo"] == "INS-LECHE")    # $1.5/ml
        ins_huevo = next(i for i in insumos if i["codigo"] == "INS-HUEVO")    # $250/u

        # Costo esperado: (100g * 1.2 = 120) + (150ml * 1.5 = 225) + (1 * 250 = 250) = $595
        producto_con_receta = ProductoCreate(
            codigo="PANQ01",
            nombre="Panqueques Caseros con Dulce",
            stock_inicial=15,
            costo_unitario=0.0,  # Se debe calcular automáticamente de la receta
            precio_venta=2800.0,
            receta=[
                RecetaItemCreate(insumo_id=ins_harina["id"], cantidad=100.0),
                RecetaItemCreate(insumo_id=ins_leche["id"], cantidad=150.0),
                RecetaItemCreate(insumo_id=ins_huevo["id"], cantidad=1.0),
            ]
        )

        prod_creado = ProductoService.crear_producto(conn, producto_con_receta)
        assert prod_creado["id"] > 0
        assert prod_creado["codigo"] == "PANQ01"
        assert prod_creado["tiene_receta"] is True
        assert prod_creado["total_insumos_receta"] == 3
        assert prod_creado["costo_unitario"] == 595.0

        # Verificar receta persistida en la tabla receta_detalles
        receta_db = InsumoService.obtener_receta_producto(conn, prod_creado["id"])
        assert receta_db["tiene_receta"] is True
        assert len(receta_db["ingredientes"]) == 3
        assert receta_db["costo_receta"] == 595.0
        assert receta_db["margen_bruto"] == 2205.0  # 2800 - 595
    finally:
        conn.close()


def test_descuento_atomico_recetas_comestibles(test_db: Path):
    """Verifica que productos comestibles (sándwiches y tostadas) descuenten sus insumos correspondientes."""
    conn = get_db_connection(test_db)
    try:
        # SAN01: Sandwich Jamón Pierna y Queso Gouda
        # Receta: 1 INS-PAN, 60g INS-JAMON, 60g INS-QUESO
        prods = ProductoService.listar_productos(conn)
        prod_san = next(p for p in prods if p["codigo"] == "SAN01")

        insumos_pre = {i["codigo"]: i["stock_actual"] for i in InsumoService.listar_insumos(conn)}
        pan_pre = insumos_pre["INS-PAN"]
        jamon_pre = insumos_pre["INS-JAMON"]
        queso_pre = insumos_pre["INS-QUESO"]
        san_stock_pre = prod_san["stock_actual"]

        # Comprar 2 sándwiches
        pedido_data = PedidoCreate(
            mesa="Mesa 5",
            cliente="Cliente Desayuno",
            medio_pago="Efectivo",
            items=[ItemPedidoCreate(producto_id=prod_san["id"], cantidad=2)]
        )

        with atomic_transaction(test_db) as tx_conn:
            ticket = OrderService.procesar_checkout(tx_conn, pedido_data)

        assert ticket["id"] > 0

        # Validar descuento de producto
        prod_san_post = ProductoService.obtener_por_id(conn, prod_san["id"])
        assert prod_san_post["stock_actual"] == san_stock_pre - 2

        # Validar descuento de insumos:
        # Pan: -2 unidades
        # Jamón: -120 g
        # Queso: -120 g
        insumos_post = {i["codigo"]: i["stock_actual"] for i in InsumoService.listar_insumos(conn)}
        assert insumos_post["INS-PAN"] == pan_pre - 2.0
        assert insumos_post["INS-JAMON"] == jamon_pre - 120.0
        assert insumos_post["INS-QUESO"] == queso_pre - 120.0
    finally:
        conn.close()


def test_limpieza_total_purga_insumos_recetas_comandas(test_db: Path):
    """Verifica que la purga total limpie completamente todas las tablas incluyendo insumos, recetas y comandas."""
    from app.services.caja_service import CajaService
    from app.services.comanda_service import ComandaService
    from app.models.schemas import ComandaCreate

    schema_file = Path(__file__).resolve().parent.parent / "data" / "schema.sql"
    conn = get_db_connection(test_db)
    try:
        # Crear una comanda de prueba para asegurar que haya datos en comandas
        ComandaService.abrir_comanda(conn, ComandaCreate(mesa="Mesa 1", cliente="Test Purga"))
    finally:
        conn.close()

    # Ejecutar limpieza total
    res_limpieza = CajaService.limpiar_base_datos_total(test_db, schema_file)
    assert res_limpieza["status"] == "success"

    # Verificar que TODAS las tablas están vacías
    conn = get_db_connection(test_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM productos;").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM insumos;").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM receta_detalles;").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM comandas;").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM comanda_detalles;").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM pedidos;").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM pedido_detalles;").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM cierres_caja;").fetchone()[0] == 0
    finally:
        conn.close()


def test_cargar_semillas_demo_comestibles_y_bebibles(test_db: Path):
    """Verifica que la carga de datos demo pueble productos, insumos y recetas tanto para bebibles como comestibles."""
    from app.services.caja_service import CajaService

    schema_file = Path(__file__).resolve().parent.parent / "data" / "schema.sql"
    # Limpiar primero
    CajaService.limpiar_base_datos_total(test_db, schema_file)

    # Cargar demo
    seeds_file = Path(__file__).resolve().parent.parent / "data" / "seeds.sql"
    res_demo = CajaService.cargar_semillas_demo(test_db, seeds_file)

    assert res_demo["productos"] >= 10
    assert res_demo["insumos"] >= 10
    assert res_demo["recetas"] >= 10

    conn = get_db_connection(test_db)
    try:
        # Verificar presencia de bebibles
        cafes = conn.execute("SELECT COUNT(*) FROM productos WHERE codigo LIKE 'CAF%';").fetchone()[0]
        assert cafes >= 6

        # Verificar presencia de comestibles
        comestibles = conn.execute("SELECT COUNT(*) FROM productos WHERE codigo LIKE 'PAN%' OR codigo LIKE 'SAN%';").fetchone()[0]
        assert comestibles >= 3

        # Verificar insumos de panadería/cocina
        ins_pan = conn.execute("SELECT * FROM insumos WHERE codigo = 'INS-PAN';").fetchone()
        assert ins_pan is not None
        assert ins_pan["unidad_medida"] == "unidad"

        ins_palta = conn.execute("SELECT * FROM insumos WHERE codigo = 'INS-PALTA';").fetchone()
        assert ins_palta is not None
        assert ins_palta["unidad_medida"] == "g"

        # Verificar que Tostón Palta y Huevo (PAN02) tiene sus ingredientes
        prod_toston = conn.execute("SELECT id FROM productos WHERE codigo = 'PAN02';").fetchone()
        receta_toston = InsumoService.obtener_receta_producto(conn, prod_toston["id"])
        assert receta_toston["tiene_receta"] is True
        assert len(receta_toston["ingredientes"]) == 3  # Pan, Palta, Huevo
    finally:
        conn.close()


