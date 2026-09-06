"""
Suite de Pruebas Automatizadas para Hito 1: Core de Datos y Transacciones ACID.

Evalúa:
1. Inicialización y esquema DDL con modo WAL.
2. Transaccionalidad atómica y ROLLBACK garantizado ante falta de stock.
3. Bloqueo de stock negativo a nivel de motor (CHECK constraint).
4. Prevención de inyección SQL mediante consultas parametrizadas.
5. Protección contra códigos de productos duplicados (UNIQUE constraint).
6. Generación de respaldos en caliente (.db snapshot).
"""

import sqlite3
# pyrefly: ignore [missing-import]
import pytest
from pathlib import Path

from app.database import init_db, get_db_connection, atomic_transaction, backup_database
from app.services.product_service import ProductoService
from app.services.order_service import OrderService, StockInsuficienteError
from app.services.caja_service import CajaService
from app.models.schemas import ProductoCreate, PedidoCreate, ItemPedidoCreate


@pytest.fixture
def test_db(tmp_path: Path):
    """Fixture que crea una base de datos aislada temporal para cada prueba."""
    db_file = tmp_path / "test_cafeteria.db"
    schema_file = Path(__file__).resolve().parent.parent / "data" / "schema.sql"
    seeds_file = Path(__file__).resolve().parent.parent / "data" / "seeds.sql"
    init_db(db_file, schema_file)
    CajaService.cargar_semillas_demo(db_file, seeds_file)
    return db_file


def test_inicializacion_y_wal_mode(test_db: Path):
    """Verifica que la base de datos se inicialice en modo WAL y con llaves foráneas activas."""
    conn = get_db_connection(test_db)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0]
        assert journal_mode.lower() == "wal", f"Se esperaba 'wal', se obtuvo '{journal_mode}'"

        cursor.execute("PRAGMA foreign_keys;")
        foreign_keys = cursor.fetchone()[0]
        assert foreign_keys == 1, "Las llaves foráneas deben estar habilitadas (1)"

        # Verificar semillas
        cursor.execute("SELECT COUNT(*) FROM productos;")
        total_prods = cursor.fetchone()[0]
        assert total_prods >= 10, "Deben haberse insertado las semillas iniciales de productos"
    finally:
        conn.close()


def test_cobro_exitoso_y_descuento_exacto_stock(test_db: Path):
    """Comprueba que un pedido válido descuente el stock exactamente y genere el ticket."""
    conn = get_db_connection(test_db)
    try:
        # Consultar stock inicial de producto 1
        p1 = ProductoService.obtener_por_id(conn, 1)
        stock_previo = p1["stock_actual"]
        assert stock_previo >= 2

        pedido_data = PedidoCreate(
            mesa="Mesa 1",
            cliente="Juan Pérez",
            medio_pago="Efectivo",
            items=[ItemPedidoCreate(producto_id=1, cantidad=2)]
        )

        with atomic_transaction(test_db) as tx_conn:
            resultado = OrderService.procesar_checkout(tx_conn, pedido_data)

        assert resultado["id"] > 0
        assert resultado["numero_ticket"].startswith("TCK-")
        assert resultado["total"] == p1["precio_venta"] * 2

        # Verificar stock descontado
        p1_post = ProductoService.obtener_por_id(conn, 1)
        assert p1_post["stock_actual"] == stock_previo - 2
    finally:
        conn.close()


def test_rollback_atomico_por_stock_insuficiente(test_db: Path):
    """
    REGLA CRÍTICA ACID:
    Si un pedido contiene 2 productos y el segundo no tiene stock suficiente,
    la transacción DEBE fallar por completo y NINGÚN producto debe ser descontado.
    """
    conn = get_db_connection(test_db)
    try:
        # Producto 1 tiene stock; ajustamos producto 2 a solo 1 unidad
        conn.execute("UPDATE productos SET stock_actual = 1 WHERE id = 2;")
        p1_prev = ProductoService.obtener_por_id(conn, 1)["stock_actual"]
        p2_prev = ProductoService.obtener_por_id(conn, 2)["stock_actual"]

        # Solicitamos 2 unidades de producto 1 y 5 unidades de producto 2 (exceso)
        pedido_data = PedidoCreate(
            mesa="Mesa 4",
            cliente="Cliente Test",
            medio_pago="Débito",
            items=[
                ItemPedidoCreate(producto_id=1, cantidad=2),
                ItemPedidoCreate(producto_id=2, cantidad=5)  # Excede stock (1 disponible)
            ]
        )

        with pytest.raises(StockInsuficienteError) as exc_info:
            with atomic_transaction(test_db) as tx_conn:
                OrderService.procesar_checkout(tx_conn, pedido_data)

        assert exc_info.value.producto_id == 2
        assert exc_info.value.solicitado == 5
        assert exc_info.value.disponible == 1

        # Verificar ROLLBACK: Ningún stock debe haber cambiado
        p1_post = ProductoService.obtener_por_id(conn, 1)["stock_actual"]
        p2_post = ProductoService.obtener_por_id(conn, 2)["stock_actual"]
        assert p1_post == p1_prev, "El producto 1 NO debe haberse descontado (Rollback fallido)"
        assert p2_post == p2_prev, "El producto 2 NO debe haberse descontado"

        # Verificar que no se creó ningún pedido huérfano
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM pedidos WHERE mesa = 'Mesa 4';")
        assert cursor.fetchone()[0] == 0, "No debe haberse registrado la cabecera del pedido"
    finally:
        conn.close()


def test_restriccion_check_stock_negativo(test_db: Path):
    """Valida que el motor SQLite impida stock negativo mediante restricción CHECK."""
    conn = get_db_connection(test_db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE productos SET stock_actual = -5 WHERE id = 1;")
    finally:
        conn.close()


def test_proteccion_inyeccion_sql(test_db: Path):
    """Comprueba que entradas maliciosas no alteren las consultas parametrizadas."""
    conn = get_db_connection(test_db)
    try:
        # Inyección típica en buscador
        payload_malicioso = "' OR '1'='1"
        resultados = ProductoService.listar_productos(conn, solo_activos=True, busqueda=payload_malicioso)
        # Debe buscar literalmente esa cadena y retornar lista vacía, no todos los productos
        assert len(resultados) == 0

        # Inyección con comillas simples y comentarios SQL
        payload_sql = "CAF'; DROP TABLE productos; --"
        resultados2 = ProductoService.listar_productos(conn, solo_activos=True, busqueda=payload_sql)
        assert len(resultados2) == 0

        # La tabla productos debe seguir intacta
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM productos;")
        assert cursor.fetchone()[0] > 0
    finally:
        conn.close()


def test_unicidad_codigo_producto(test_db: Path):
    """Verifica que no se permita insertar dos productos con el mismo código."""
    conn = get_db_connection(test_db)
    try:
        nuevo_prod = ProductoCreate(
            codigo="CAF01",  # Ya existe en las semillas
            nombre="Café Duplicado",
            stock_inicial=10,
            costo_unitario=500.0,
            precio_venta=1500.0
        )
        with pytest.raises(sqlite3.IntegrityError):
            ProductoService.crear_producto(conn, nuevo_prod)
    finally:
        conn.close()


def test_backup_automatico(test_db: Path, tmp_path: Path):
    """Verifica que el generador de respaldos cree un archivo .db válido y recuperable."""
    backup_dir = tmp_path / "backups_test"
    backup_file = backup_database(test_db, backup_dir)

    assert backup_file.exists(), "El archivo de respaldo debe existir"
    assert backup_file.stat().st_size > 0, "El archivo de respaldo no debe estar vacío"

    # Conectar al archivo de respaldo y verificar integridad
    backup_conn = get_db_connection(backup_file)
    try:
        cursor = backup_conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        res = cursor.fetchone()[0]
        assert res == "ok", "La base de datos de respaldo debe pasar el chequeo de integridad"
    finally:
        backup_conn.close()


def test_actualizar_producto_completo(test_db: Path):
    """Verifica que se puedan modificar todos los campos de un producto en catálogo."""
    from app.models.schemas import ProductoUpdate
    conn = get_db_connection(test_db)
    try:
        update_data = ProductoUpdate(
            codigo="CAF01-MOD",
            nombre="Espresso Especial Modificado",
            stock_inicial=60,
            stock_actual=55,
            costo_unitario=750.0,
            precio_venta=2100.0,
            activo=1
        )
        prod_mod = ProductoService.actualizar_producto(conn, 1, update_data)
        assert prod_mod is not None
        assert prod_mod["codigo"] == "CAF01-MOD"
        assert prod_mod["nombre"] == "Espresso Especial Modificado"
        assert prod_mod["stock_actual"] == 55
        assert prod_mod["precio_venta"] == 2100.0
    finally:
        conn.close()


def test_eliminar_producto_sin_ventas_fisica(test_db: Path):
    """Verifica que un producto sin ventas asociadas se elimine físicamente del catálogo."""
    conn = get_db_connection(test_db)
    try:
        # Crear un producto temporal sin ventas
        nuevo_prod = ProductoCreate(
            codigo="TEMP99",
            nombre="Producto Temporal",
            stock_inicial=10,
            costo_unitario=500.0,
            precio_venta=1500.0
        )
        prod = ProductoService.crear_producto(conn, nuevo_prod)
        prod_id = prod["id"]

        # Eliminar
        res = ProductoService.eliminar_producto(conn, prod_id)
        assert res["tipo_eliminacion"] == "fisica"
        assert "eliminado definitivamente" in res["mensaje"]

        # Comprobar que no existe en base de datos
        prod_db = ProductoService.obtener_por_id(conn, prod_id)
        assert prod_db is None
    finally:
        conn.close()


def test_eliminar_producto_con_ventas_logica(test_db: Path):
    """
    Verifica que un producto con ventas previas aplique borrado lógico (activo = 0)
    para no corromper el historial de comprobantes pasados.
    """
    conn = get_db_connection(test_db)
    try:
        # Generar una venta para el producto 2
        pedido_data = PedidoCreate(
            mesa="Mesa 1",
            cliente="Cliente Test",
            medio_pago="Efectivo",
            items=[ItemPedidoCreate(producto_id=2, cantidad=1)]
        )
        with atomic_transaction(test_db) as tx_conn:
            OrderService.procesar_checkout(tx_conn, pedido_data)

        # Intentar eliminar producto 2
        res = ProductoService.eliminar_producto(conn, 2)
        assert res["tipo_eliminacion"] == "logica"
        assert "desactivado del catálogo" in res["mensaje"]

        # El producto debe seguir existiendo pero con activo = 0
        prod_db = ProductoService.obtener_por_id(conn, 2)
        assert prod_db is not None
        assert prod_db["activo"] == 0

        # Al listar solo activos, no debe figurar
        activos = ProductoService.listar_productos(conn, solo_activos=True)
        assert not any(p["id"] == 2 for p in activos)
    finally:
        conn.close()
