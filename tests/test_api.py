"""
Pruebas de Integración End-to-End para la API REST de CoffeePOS.

Verifica el comportamiento de todos los endpoints, códigos de estado HTTP,
validación de payloads JSON y manejo de errores 404, 409 y 422.
"""

# pyrefly: ignore [missing-import]
import pytest
from pathlib import Path
# pyrefly: ignore [missing-import]
from starlette.testclient import TestClient

from app.main import app
from app.database import init_db


@pytest.fixture(autouse=True)
def setup_test_environment(tmp_path: Path, monkeypatch):
    """Configura una base de datos temporal limpia para cada test de API."""
    db_file = tmp_path / "api_test.db"
    backup_dir = tmp_path / "backups_test"
    schema_file = Path(__file__).resolve().parent.parent / "data" / "schema.sql"

    monkeypatch.setattr("app.config.DB_PATH", db_file)
    monkeypatch.setattr("app.config.BACKUP_DIR", backup_dir)

    init_db(db_file, schema_file)
    from app.services.caja_service import CajaService
    seeds_file = Path(__file__).resolve().parent.parent / "data" / "seeds.sql"
    CajaService.cargar_semillas_demo(db_file, seeds_file)


def test_api_configuracion():
    """Valida lectura y actualización de configuración."""
    client = TestClient(app)

    res = client.get("/api/configuracion")
    assert res.status_code == 200
    data = res.json()
    assert "mesas_activas" in data
    assert data["mesas_activas"] >= 1

    # Actualizar a 12 mesas
    res_put = client.put("/api/configuracion", json={"mesas_activas": 12, "nombre_local": "Café Central"})
    assert res_put.status_code == 200
    assert res_put.json()["mesas_activas"] == 12
    assert res_put.json()["nombre_local"] == "Café Central"


def test_api_productos_crud_y_reabastecimiento():
    """Valida CRUD de productos y endpoint de reabastecimiento rápido."""
    client = TestClient(app)

    # 1. Listar productos iniciales
    res = client.get("/api/productos")
    assert res.status_code == 200
    prods = res.json()
    assert len(prods) >= 10

    # 2. Crear nuevo producto
    nuevo = {
        "codigo": "MOC99",
        "nombre": "Moca Caramelo",
        "stock_inicial": 15,
        "costo_unitario": 950.0,
        "precio_venta": 2600.0
    }
    res_create = client.post("/api/productos", json=nuevo)
    assert res_create.status_code == 201
    prod_creado = res_create.json()
    assert prod_creado["codigo"] == "MOC99"
    assert prod_creado["stock_actual"] == 15

    # 3. Intentar duplicar código (debe arrojar 409 Conflict)
    res_dup = client.post("/api/productos", json=nuevo)
    assert res_dup.status_code == 409

    # 4. Reabastecer +10 unidades
    prod_id = prod_creado["id"]
    res_reab = client.post(f"/api/productos/{prod_id}/reabastecer", json={"cantidad": 10})
    assert res_reab.status_code == 200
    assert res_reab.json()["stock_actual"] == 25
    assert res_reab.json()["stock_inicial"] == 25


def test_api_checkout_exitoso_y_fallo_stock():
    """Valida checkout atómico por API y rechazo con 409 ante stock insuficiente."""
    client = TestClient(app)

    # Venta exitosa
    pedido_ok = {
        "mesa": "Mesa 2",
        "cliente": "Consumidor Final",
        "medio_pago": "Efectivo",
        "items": [{"producto_id": 1, "cantidad": 2}]
    }
    res_ok = client.post("/api/pedidos", json=pedido_ok)
    assert res_ok.status_code == 201
    ticket = res_ok.json()
    assert "TCK-" in ticket["numero_ticket"]
    assert ticket["total"] > 0
    assert len(ticket["detalles"]) == 1

    # Venta que excede el stock disponible (ej. 99999 unidades)
    pedido_exceso = {
        "mesa": "Mesa 3",
        "cliente": "Cliente Test",
        "medio_pago": "Débito",
        "items": [{"producto_id": 1, "cantidad": 99999}]
    }
    res_fail = client.post("/api/pedidos", json=pedido_exceso)
    assert res_fail.status_code == 409
    error_data = res_fail.json()["detail"]
    assert error_data["error"] == "STOCK_INSUFICIENTE"
    assert error_data["producto_id"] == 1


def test_api_cierre_caja_y_backup():
    """Valida resumen diario y ejecución de cierre de caja con backup."""
    client = TestClient(app)

    # Registrar una venta para tener saldo
    client.post("/api/pedidos", json={
        "mesa": "Barra / Para Llevar",
        "cliente": "Cliente Barra",
        "medio_pago": "Transferencia",
        "items": [{"producto_id": 2, "cantidad": 1}]
    })

    # Consultar resumen diario
    res_resumen = client.get("/api/caja/resumen-diario")
    assert res_resumen.status_code == 200
    data_resumen = res_resumen.json()
    assert data_resumen["total_recaudado"] > 0
    assert data_resumen["desglose_medios_pago"]["Transferencia"] > 0

    # Ejecutar cierre de caja
    res_cierre = client.post("/api/caja/cerrar")
    assert res_cierre.status_code == 200
    data_cierre = res_cierre.json()
    assert data_cierre["status"] == "success"
    assert "backup_generado" in data_cierre


def test_api_sistema_seguridad():
    """Valida las acciones críticas del sistema y la protección por palabra clave."""
    client = TestClient(app)

    # Reinicio de stock
    res_reset = client.post("/api/sistema/reiniciar-stock", json={"confirmar": True})
    assert res_reset.status_code == 200
    assert "productos_afectados" in res_reset.json()

    # Intento de formateo con palabra clave incorrecta
    res_fail_purge = client.post("/api/sistema/limpieza-total", json={"palabra_clave": "eliminar"})
    assert res_fail_purge.status_code == 400

    # Formateo con palabra clave correcta (debe dejar catálogo con CERO productos)
    res_ok_purge = client.post("/api/sistema/limpieza-total", json={"palabra_clave": "borrar"})
    assert res_ok_purge.status_code == 200
    assert "restaurada" in res_ok_purge.json()["mensaje"]

    # Comprobar que tras la purga el catálogo está en 0
    res_vacio = client.get("/api/productos")
    assert len(res_vacio.json()) == 0

    # Probar endpoint de recarga de semillas demo
    res_demo = client.post("/api/sistema/cargar-demo")
    assert res_demo.status_code == 200
    assert res_demo.json()["total_productos"] >= 10
    assert len(client.get("/api/productos").json()) >= 10


def test_api_productos_eliminar_y_modificar():
    """Valida los endpoints PUT y DELETE de productos."""
    client = TestClient(app)

    # 1. Crear producto de prueba
    crear_res = client.post("/api/productos", json={
        "codigo": "TEST-DEL",
        "nombre": "Café para Eliminar",
        "stock_inicial": 20,
        "costo_unitario": 500.0,
        "precio_venta": 1500.0
    })
    assert crear_res.status_code == 201
    prod_id = crear_res.json()["id"]

    # 2. Modificar producto (PUT)
    put_res = client.put(f"/api/productos/{prod_id}", json={
        "codigo": "TEST-DEL-MOD",
        "nombre": "Café Modificado",
        "stock_actual": 35,
        "precio_venta": 1900.0
    })
    assert put_res.status_code == 200
    data_mod = put_res.json()
    assert data_mod["codigo"] == "TEST-DEL-MOD"
    assert data_mod["nombre"] == "Café Modificado"
    assert data_mod["stock_actual"] == 35
    assert data_mod["precio_venta"] == 1900.0

    # 3. Eliminar producto sin ventas (DELETE - física)
    del_res = client.delete(f"/api/productos/{prod_id}")
    assert del_res.status_code == 200
    assert del_res.json()["tipo_eliminacion"] == "fisica"

    # Verificar que ya no existe (404 al consultar)
    assert client.get(f"/api/productos/{prod_id}").status_code == 404
