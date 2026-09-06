"""
Pruebas unitarias y de integración para la funcionalidad de Carga Automática / Masiva con IA.
"""

import pytest
from pathlib import Path
from starlette.testclient import TestClient

from app.main import app
from app.database import init_db, get_db
from app.services.caja_service import CajaService


@pytest.fixture(autouse=True)
def setup_test_environment(tmp_path: Path, monkeypatch):
    """Configura base de datos temporal para pruebas de carga masiva."""
    db_file = tmp_path / "bulk_test.db"
    backup_dir = tmp_path / "backups_test"
    schema_file = Path(__file__).resolve().parent.parent / "data" / "schema.sql"
    seeds_file = Path(__file__).resolve().parent.parent / "data" / "seeds.sql"

    monkeypatch.setattr("app.config.DB_PATH", db_file)
    monkeypatch.setattr("app.config.BACKUP_DIR", backup_dir)

    init_db(db_file, schema_file)
    CajaService.cargar_semillas_demo(db_file, seeds_file)


def test_carga_bulk_creacion_productos_con_y_sin_codigo():
    """Valida la creación masiva de productos nuevos, autogenerando código cuando no se indica."""
    client = TestClient(app)

    payload = {
        "modo": "sumar_stock",
        "productos": [
            {
                "codigo": "CRO01",
                "nombre": "Croissant de Almendras",
                "stock": 15,
                "costo_unitario": 800.0,
                "precio_venta": 2200.0
            },
            {
                # Sin código: la app debe autogenerar uno (ej: TAR01 o similar)
                "nombre": "Tarta de Limón y Merengue",
                "stock": 8,
                "costo_unitario": 1200.0,
                "precio_venta": 3500.0
            }
        ]
    }

    res = client.post("/api/productos/bulk", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["total_recibidos"] == 2
    assert data["total_creados"] == 2
    assert data["total_actualizados"] == 0

    # Verificar que el producto sin código recibió un código generado
    detalles = data["detalles"]
    prod_croissant = next(d for d in detalles if d["nombre"] == "Croissant de Almendras")
    prod_tarta = next(d for d in detalles if d["nombre"] == "Tarta de Limón y Merengue")

    assert prod_croissant["codigo"] == "CRO01"
    assert prod_tarta["codigo"] is not None
    assert len(prod_tarta["codigo"]) >= 3

    # Verificar persistencia en base de datos
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT stock_actual, precio_venta FROM productos WHERE codigo = 'CRO01';")
        row = cursor.fetchone()
        assert row is not None
        assert row["stock_actual"] == 15
        assert row["precio_venta"] == 2200.0


def test_carga_bulk_reabastecer_stock_producto_existente():
    """Valida que un producto existente incremente su stock si modo es 'sumar_stock'."""
    client = TestClient(app)

    # Obtenemos un producto existente de las semillas (ej: CAF01 - Café Espresso)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, codigo, nombre, stock_actual, stock_inicial FROM productos WHERE codigo = 'CAF01';")
        espresso = cursor.fetchone()
        stock_previo = espresso["stock_actual"]

    payload = {
        "modo": "sumar_stock",
        "productos": [
            {
                "codigo": "CAF01",
                "nombre": "Café Espresso Doble",
                "stock": 20,
                "costo_unitario": 400.0,
                "precio_venta": 1800.0
            }
        ]
    }

    res = client.post("/api/productos/bulk", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["total_actualizados"] == 1
    assert data["detalles"][0]["stock_previo"] == stock_previo
    assert data["detalles"][0]["stock_final"] == stock_previo + 20

    # Verificar en DB
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT stock_actual, precio_venta FROM productos WHERE codigo = 'CAF01';")
        row = cursor.fetchone()
        assert row["stock_actual"] == stock_previo + 20
        assert row["precio_venta"] == 1800.0


def test_carga_bulk_modo_solo_nuevos_ignora_existentes():
    """Valida que en modo 'solo_nuevos' no se modifique el stock de un producto ya registrado."""
    client = TestClient(app)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT stock_actual FROM productos WHERE codigo = 'CAF01';")
        stock_original = cursor.fetchone()["stock_actual"]

    payload = {
        "modo": "solo_nuevos",
        "productos": [
            {
                "codigo": "CAF01",
                "nombre": "Café Espresso",
                "stock": 50,
                "costo_unitario": 300.0,
                "precio_venta": 2500.0
            }
        ]
    }

    res = client.post("/api/productos/bulk", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["total_ignorados"] == 1
    assert data["total_actualizados"] == 0

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT stock_actual FROM productos WHERE codigo = 'CAF01';")
        assert cursor.fetchone()["stock_actual"] == stock_original


def test_carga_bulk_coincidencia_por_nombre():
    """Valida que coincida con un producto existente por nombre exacto aunque el código no venga."""
    client = TestClient(app)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, codigo, nombre, stock_actual FROM productos LIMIT 1;")
        prod = cursor.fetchone()
        nombre_prod = prod["nombre"]
        stock_previo = prod["stock_actual"]

    payload = {
        "modo": "sumar_stock",
        "productos": [
            {
                "nombre": f"  {nombre_prod.lower()}  ",  # Espacios y minúsculas
                "stock": 10,
                "costo_unitario": 0.0,
                "precio_venta": 0.0
            }
        ]
    }

    res = client.post("/api/productos/bulk", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["total_actualizados"] == 1
    assert data["detalles"][0]["stock_final"] == stock_previo + 10
