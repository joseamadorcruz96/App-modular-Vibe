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


def test_api_insumos_y_recetas():
    """Valida los endpoints REST para insumos y recetas."""
    client = TestClient(app)

    # 1. Listar insumos demo
    res = client.get("/api/insumos")
    assert res.status_code == 200
    insumos = res.json()
    assert len(insumos) >= 5

    # 2. Crear nuevo insumo
    nuevo_insumo = {
        "codigo": "INS-CANELA",
        "nombre": "Canela de Ceilán en Polvo",
        "unidad_medida": "g",
        "stock_actual": 800.0,
        "stock_minimo": 100.0,
        "costo_unitario": 35.0
    }
    res_crear = client.post("/api/insumos", json=nuevo_insumo)
    assert res_crear.status_code == 201
    ins_id = res_crear.json()["id"]

    # 3. Reabastecer insumo (+200 g)
    res_reab = client.post(f"/api/insumos/{ins_id}/reabastecer", json={"cantidad": 200.0})
    assert res_reab.status_code == 200
    assert res_reab.json()["stock_actual"] == 1000.0

    # 4. Consultar receta existente de producto 4 (Capuccino)
    res_receta = client.get("/api/productos/4/receta")
    assert res_receta.status_code == 200
    receta_data = res_receta.json()
    assert receta_data["tiene_receta"] is True
    assert receta_data["costo_receta"] > 0
    assert receta_data["margen_bruto"] > 0
    assert receta_data["margen_porcentaje"] > 0

    # 5. Modificar insumo (PUT)
    res_put = client.put(f"/api/insumos/{ins_id}", json={"costo_unitario": 42.0, "stock_minimo": 150.0})
    assert res_put.status_code == 200
    assert res_put.json()["costo_unitario"] == 42.0
    assert res_put.json()["stock_minimo"] == 150.0

    # 6. Guardar receta vía API (POST /api/productos/{id}/receta)
    res_set_receta = client.post("/api/productos/2/receta", json={
        "ingredientes": [{"insumo_id": ins_id, "cantidad": 10.0}]
    })
    assert res_set_receta.status_code == 200
    receta_p2 = res_set_receta.json()
    assert receta_p2["tiene_receta"] is True
    assert len(receta_p2["ingredientes"]) == 1
    assert receta_p2["costo_receta"] == 420.0  # 10 * 42

    # 7. Eliminar receta vía API (DELETE /api/productos/{id}/receta)
    res_del_receta = client.delete("/api/productos/2/receta")
    assert res_del_receta.status_code == 200
    assert "Receta eliminada" in res_del_receta.json()["mensaje"]

    # 8. Eliminar insumo libre físicamente vía API (DELETE /api/insumos/{id})
    res_del_ins = client.delete(f"/api/insumos/{ins_id}")
    assert res_del_ins.status_code == 200
    assert res_del_ins.json()["tipo_eliminacion"] == "fisica"

    # 9. Consultar insumo inexistente debe arrojar 404
    assert client.get(f"/api/insumos/{ins_id}").status_code == 404



def test_api_comandas_ciclo_completo():
    """Valida el ciclo de vida de comandas por API: estado mesas, abrir, agregar ítems y checkout."""
    client = TestClient(app)

    # 1. Consultar estado inicial del salón
    res_mesas = client.get("/api/comandas/mesas-estado")
    assert res_mesas.status_code == 200
    mesas = res_mesas.json()
    assert len(mesas) >= 1
    assert all(not m["ocupada"] for m in mesas)

    # 2. Abrir Mesa 1
    res_abrir = client.post("/api/comandas/abrir", json={"mesa": "Mesa 1", "cliente": "Sra. Carmen"})
    assert res_abrir.status_code == 201
    cmd = res_abrir.json()
    cmd_id = cmd["id"]
    assert cmd["mesa"] == "Mesa 1"
    assert cmd["estado"] == "Abierta"

    # 3. Agregar ítems a la comanda
    res_items = client.post(f"/api/comandas/{cmd_id}/items", json={
        "items": [
            {"producto_id": 1, "cantidad": 1, "notas": "descafeinado"},
            {"producto_id": 7, "cantidad": 1}
        ]
    })
    assert res_items.status_code == 200
    cmd_upd = res_items.json()
    assert cmd_upd["total_items"] == 2
    assert cmd_upd["subtotal"] > 0

    # 4. Verificar que el estado del salón muestra Mesa 1 como ocupada
    res_mesas_post = client.get("/api/comandas/mesas-estado")
    m1 = next(m for m in res_mesas_post.json() if m["mesa"] == "Mesa 1")
    assert m1["ocupada"] is True
    assert m1["subtotal"] == cmd_upd["subtotal"]

    # 5. Liquidar comanda con checkout
    res_chk = client.post(f"/api/comandas/{cmd_id}/checkout", json={"medio_pago": "Efectivo", "descuento": 0.0})
    assert res_chk.status_code == 200
    ticket = res_chk.json()
    assert ticket["numero_ticket"].startswith("TCK-")

    # 6. Mesa 1 debe volver a figurar como libre
    res_mesas_final = client.get("/api/comandas/mesas-estado")
    m1_final = next(m for m in res_mesas_final.json() if m["mesa"] == "Mesa 1")
    assert m1_final["ocupada"] is False


def test_api_comandas_casos_borde():
    """Valida colisión de mesa ocupada, eliminación de ítems y cancelación por API."""
    client = TestClient(app)

    # 1. Abrir comanda en Mesa 3
    res1 = client.post("/api/comandas/abrir", json={"mesa": "Mesa 3", "cliente": "Cliente A"})
    assert res1.status_code == 201
    cmd_id = res1.json()["id"]

    # 2. Intentar abrir en Mesa 3 ocupada -> 409 Conflict
    res_dupe = client.post("/api/comandas/abrir", json={"mesa": "Mesa 3", "cliente": "Cliente B"})
    assert res_dupe.status_code == 409
    assert "ya tiene una comanda abierta" in res_dupe.json()["detail"]

    # 3. Agregar 2 ítems
    res_add = client.post(f"/api/comandas/{cmd_id}/items", json={
        "items": [
            {"producto_id": 1, "cantidad": 2},
            {"producto_id": 7, "cantidad": 1}
        ]
    })
    assert res_add.status_code == 200
    cmd_data = res_add.json()
    assert len(cmd_data["detalles"]) == 2
    detalle_id = cmd_data["detalles"][0]["id"]

    # 4. Eliminar un ítem individual de la comanda (DELETE)
    res_del_item = client.delete(f"/api/comandas/{cmd_id}/items/{detalle_id}")
    assert res_del_item.status_code == 200
    cmd_post_del = res_del_item.json()
    assert len(cmd_post_del["detalles"]) == 1

    # 5. Cancelar comanda
    res_cancel = client.post(f"/api/comandas/{cmd_id}/cancelar")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["estado"] == "Cancelada"

    # Mesa 3 debe estar libre
    res_mesas = client.get("/api/comandas/mesas-estado")
    m3 = next(m for m in res_mesas.json() if m["mesa"] == "Mesa 3")
    assert m3["ocupada"] is False


def test_api_insumo_eliminacion_forzada_y_producto_con_receta():
    """Valida eliminación forzada de insumos y creación directa de productos con receta vía API."""
    client = TestClient(app)

    # 1. Obtener insumo INS-CHOCO (usado en CAF06)
    res_ins = client.get("/api/insumos")
    ins_choco = next(i for i in res_ins.json() if i["codigo"] == "INS-CHOCO")
    choco_id = ins_choco["id"]

    # 2. Eliminación normal (forzar=false) debe ser lógica
    res_del_logica = client.delete(f"/api/insumos/{choco_id}")
    assert res_del_logica.status_code == 200
    assert res_del_logica.json()["tipo_eliminacion"] == "logica"

    # Reactivar insumo
    res_reactivar = client.put(f"/api/insumos/{choco_id}", json={"activo": 1})
    assert res_reactivar.status_code == 200
    assert res_reactivar.json()["activo"] == 1

    # 3. Eliminación forzada (forzar=true) debe ser física y limpiar recetas
    res_del_forzada = client.delete(f"/api/insumos/{choco_id}?forzar=true")
    assert res_del_forzada.status_code == 200
    assert res_del_forzada.json()["tipo_eliminacion"] == "fisica"
    assert res_del_forzada.json()["recetas_desvinculadas"] >= 1

    # Insumo ya no existe
    assert client.get(f"/api/insumos/{choco_id}").status_code == 404

    # 4. Crear producto nuevo con receta embebida
    ins_leche = next(i for i in res_ins.json() if i["codigo"] == "INS-LECHE")
    ins_cafe = next(i for i in res_ins.json() if i["codigo"] == "INS-CAFE")

    nuevo_prod_receta = {
        "codigo": "FLAT01",
        "nombre": "Flat White Especial",
        "stock_inicial": 25,
        "costo_unitario": 0.0,
        "precio_venta": 3100.0,
        "receta": [
            {"insumo_id": ins_cafe["id"], "cantidad": 20.0},
            {"insumo_id": ins_leche["id"], "cantidad": 120.0}
        ]
    }
    res_crear = client.post("/api/productos", json=nuevo_prod_receta)
    assert res_crear.status_code == 201
    prod_data = res_crear.json()
    assert prod_data["tiene_receta"] is True
    assert prod_data["total_insumos_receta"] == 2
    assert prod_data["costo_unitario"] == 680.0  # (20 * 25 = 500) + (120 * 1.5 = 180)


def test_api_sistema_limpieza_total_y_cargar_demo():
    """Valida los endpoints de purga total del sistema y recarga de catálogo demo."""
    client = TestClient(app)

    # 1. Purgar base de datos completamente (requiere palabra_clave='borrar')
    res_purga = client.post("/api/sistema/limpieza-total", json={"palabra_clave": "borrar"})
    assert res_purga.status_code == 200
    assert "restaurada al estado original" in res_purga.json()["mensaje"]

    # Verificar que el catálogo de productos y de insumos está vacío
    assert len(client.get("/api/productos").json()) == 0
    assert len(client.get("/api/insumos").json()) == 0

    # 2. Cargar semillas demo
    res_demo = client.post("/api/sistema/cargar-demo")
    assert res_demo.status_code == 200
    data_demo = res_demo.json()
    assert data_demo["productos_cargados"] >= 10
    assert data_demo["insumos_cargados"] >= 10
    assert data_demo["recetas_vinculadas"] >= 10

    # Verificar que existen productos y están categorizados
    prods = client.get("/api/productos").json()
    assert len(prods) == data_demo["productos_cargados"]
    assert any(p["codigo"] == "SAN01" for p in prods)
    assert any(p["codigo"] == "CAF01" for p in prods)


