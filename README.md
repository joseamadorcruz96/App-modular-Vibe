# CoffeePOS - Sistema Local de Punto de Venta & Gestión para Cafeterías

CoffeePOS es una solución local, liviana y portable de Punto de Venta (TPV), gestión de comandas por mesas, control de inventario y cierre de caja desarrollada con rigor de ingeniería en Python y SQLite.

---

## Características Principales

1. **Transaccionalidad ACID y Resistencia a Fallos:**
   - Base de datos SQLite3 en modo **WAL** (`PRAGMA journal_mode=WAL;`), timeout de 10s y llaves foráneas activas.
   - Cobro atómico bajo transacción exclusiva `BEGIN IMMEDIATE`. Si algún producto del ticket carece de stock, se produce un `ROLLBACK` total, impidiendo stock negativo a nivel de motor (`CHECK (stock_actual >= 0)`).
   - Cálculos financieros estrictos en el backend: el cliente solo envía IDs y cantidades; los precios se consultan directamente en base de datos.
   - Consultas 100% parametrizadas con placeholders `?` para inmunidad contra inyecciones SQL.

2. **TPV y Comandera Táctil:**
   - Selector dinámico de mesas (1 a $N$) configurable para la jornada, más la opción "Barra / Para Llevar".
   - Buscador en tiempo real de productos por nombre y código.
   - Carrito temporal reactivo con modificación de cantidades y validación de existencias.
   - Cobro rápido con selección de medio de pago (Efectivo, Débito, Crédito, Transferencia).
   - Comprobante imprimible adaptado para tickets térmicos (58mm / 80mm) y estándar vía `@media print`.

3. **Control de Inventario & Alertas Críticas:**
   - Semáforo de stock con alertas visuales destacadas para productos con existencias $\le 5$ (Crítico).
   - Registro de nuevos productos con código único obligatorio (`UNIQUE COLLATE NOCASE`).
   - Modal de reabastecimiento rápido para sumar unidades a productos existentes.

4. **Cierre de Caja, Reportes y Respaldos:**
   - Resumen del día con total recaudado, desglose por medio de pago y ranking de productos más vendidos.
   - Generación automática de copias de seguridad `.db` timestamped en `/backups` con la API en caliente de SQLite.
   - Impresión directa del informe diario de caja.

5. **Acciones de Mantenimiento:**
   - Reinicio de stock actual a stock inicial para calibraciones periódicas.
   - Restauración de fábrica protegida mediante la palabra clave `"borrar"`.

---

## Estructura del Proyecto

```
Caffe-SoKa/
├── app/
│   ├── __init__.py
│   ├── config.py              # Rutas, timeouts y constantes operativas
│   ├── database.py            # Conexión SQLite, modo WAL, transacciones ACID y backups
│   ├── main.py                # Servidor FastAPI, lifespan y montaje de rutas
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py         # Modelos Pydantic v2 documentados
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── configuracion.py   # API de mesas y ajustes
│   │   ├── productos.py       # API de inventario y reabastecimiento
│   │   ├── pedidos.py         # API de checkout atómico
│   │   ├── caja.py            # API de arqueo, cierre y respaldos
│   │   └── sistema.py         # API de mantenimiento y formateo
│   ├── services/
│   │   ├── __init__.py
│   │   ├── product_service.py # Consultas parametrizadas de inventario
│   │   ├── order_service.py   # Lógica transaccional de checkout y tickets
│   │   └── caja_service.py    # Auditoría, balances diarios y copias .db
│   └── static/
│       ├── css/
│       │   └── styles.css     # Estilos táctiles responsivos y @media print
│       ├── js/
│       │   ├── api.js         # Cliente REST
│       │   ├── tpv.js         # Lógica de venta y comandas
│       │   ├── inventario.js  # Lógica de catálogo y stock
│       │   ├── caja.js        # Lógica de cuadre diario
│       │   ├── configuracion.js # Lógica de mesas y mantenimiento
│       │   └── app.js         # Orquestador SPA y toasts
│       └── index.html         # Interfaz web SPA completa
├── data/
│   ├── schema.sql             # DDL formal, índices, checks y semillas
│   └── cafeteria.db           # Archivo de base de datos de producción
├── backups/                   # Copias de seguridad automáticas timestamped
├── tests/
│   ├── __init__.py
│   ├── test_transacciones.py  # Pruebas ACID, rollback, checks, inyecciones
│   ├── test_concurrencia.py   # Pruebas multi-hilo de compra simultánea
│   └── test_api.py            # Pruebas de integración E2E de la API REST
├── requirements.txt
├── pytest.ini
├── run.bat                    # Lanzador automático de Windows
└── README.md
```

---

## Puesta en Marcha

### En Windows (Doble Clic):
Simplemente haga doble clic sobre **`run.bat`**.
El script creará el entorno virtual `.venv`, instalará dependencias y abrirá automáticamente la aplicación en `http://127.0.0.1:8000`.

### Vía Terminal:
```bash
# 1. Crear y activar entorno virtual
python -m venv .venv
.\.venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Iniciar el servidor
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## Ejecución de Pruebas Automatizadas

La suite de pruebas evalúa transacciones ACID, concurrencia multi-hilo, bloqueo de stock negativo y todos los endpoints de la API:

```bash
.\.venv\Scripts\pytest.exe -v
```
