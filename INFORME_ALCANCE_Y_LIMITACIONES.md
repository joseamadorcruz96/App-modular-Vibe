# Informe Técnico de Alcance y Limitaciones del Sistema
## Proyecto: CoffeePOS — Sistema de Punto de Venta (TPV) y Gestión para Cafeterías

---

### Resumen Ejecutivo

**CoffeePOS** es una solución local, portable y de alta resiliencia diseñada para puntos de venta gastronómicos (cafeterías, bistrós, pastelerías y stands). La aplicación implementa una arquitectura monolítica modular en tres capas:
1. **Presentación:** Single Page Application (SPA) responsiva con HTML5 semántico, CSS adaptado a pantallas táctiles e impresoras térmicas, y JavaScript Vanilla sin sobrecarga de frameworks.
2. **Lógica de Negocio y API:** Microframework FastAPI con validaciones estrictas vía esquemas Pydantic v2.
3. **Persistencia Transaccional:** Motor SQLite3 configurado en modo WAL (*Write-Ahead Logging*) con garantías ACID completas y transacciones inmediatas exclusivas.

El presente informe detalla el **alcance operativo cubierto**, las **capacidades técnicas implementadas**, las **limitaciones estructurales del sistema** y las **recomendaciones para su evolución**.

---

### 1. Alcance Funcional (Lo que la aplicación CUBRE)

#### 1.1. Módulo TPV y Comandera Táctil
- **Venta reactiva multiproducto:** Registro ágil de ventas mediante un carrito temporal interactivo con ajuste de cantidades, eliminación de ítems y cálculo automático de subtotales.
- **Asignación de mesas y comandas:** Selector dinámico de mesas activas configurables para la jornada diaria, incorporando además la modalidad *"Barra / Para Llevar"*.
- **Búsqueda instantánea:** Filtrado en tiempo real de catálogo por coincidencia de nombre o código de producto.
- **Multimedios de pago:** Soporte de cobro mediante Efectivo (con cálculo automático de vuelto o cambio), Tarjeta de Débito, Tarjeta de Crédito y Transferencia Bancaria.
- **Emisión e Impresión de Tickets:** Plantilla térmica formateada vía `@media print` compatible con impresoras de punto de venta estándar de 58 mm y 80 mm, detallando número de ticket, mesa, cliente, desglose de ítems, totales e impuestos.

#### 1.2. Módulo de Inventario y Catálogo
- **Gestión integral de productos:** Alta, edición y parametrización de código único (`UNIQUE COLLATE NOCASE`), nombre descriptivo, stock inicial, stock actual, costo unitario y precio de venta.
- **Semáforo de inventario crítico:** Monitoreo visual preventivo con badges de advertencia cuando las existencias son iguales o inferiores a 5 unidades ($\le 5$).
- **Reabastecimiento rápido:** Modal administrativo para incorporar stock entrante de forma directa sin alterar historiales previos.
- **Eliminación inteligente con protección histórica:**
  - *Eliminación física (`DELETE`)*: Si el producto nunca tuvo ventas registradas, se elimina definitivamente del catálogo.
  - *Eliminación lógica (`activo = 0`)*: Si el producto tiene comprobantes de venta asociados, el sistema bloquea su borrado físico para no corromper la integridad referencial de los tickets pasados y lo desactiva del catálogo de ventas.
- **Calibración de stock:** Opción para restablecer el stock actual al valor inicial al comenzar turnos o tras conteos físicos.

#### 1.3. Módulo de Cuadre de Caja y Auditoría
- **Arqueo y balance en tiempo real:** Resumen instantáneo de recaudación diaria, volumen de tickets emitidos y desglose financiero exacto por medio de pago.
- **Ranking de productos:** Cálculo del Top de productos más vendidos por volumen e ingresos generados.
- **Cierre de jornada imprimible:** Generación de reporte consolidado de cierre de caja listo para imprimir o archivar.
- **Copias de seguridad en caliente (*Hot Backups*):** Ejecución automática de snapshots físicos de la base de datos (`.db`) en el directorio `/backups` mediante la API de respaldo en línea de SQLite al realizar el cierre de caja o limpiezas.
- **Mantenimiento y formateo seguro:** Opción de restauración de fábrica protegida que exige la confirmación explícita de la palabra clave `"borrar"`, además de una función para recargar el catálogo demo de prueba.

#### 1.4. Módulo de Configuración Operativa
- **Dimensionamiento de salón:** Ajuste dinámico del número de mesas disponibles según la capacidad operativa del día (de 1 a $N$ mesas).

---

### 2. Alcance Técnico y Arquitectura de Resiliencia

| Dimensión | Especificación Implementada | Beneficio Operativo |
| :--- | :--- | :--- |
| **Transaccionalidad** | Modo `BEGIN IMMEDIATE` con SQLite | Previene condiciones de carrera (*Race Conditions*) en ventas concurrentes. |
| **Garantía ACID** | `CHECK (stock_actual >= 0)` | Falla y revierte (`ROLLBACK`) cualquier intento de venta si algún producto del ticket carece de stock. |
| **Seguridad de Datos** | Consultas 100% parametrizadas (`?`) | Inmunidad total contra ataques de Inyección SQL. |
| **Concurrencia** | Modo WAL (`Write-Ahead Logging`) | Permite múltiples lecturas simultáneas mientras se ejecuta una escritura, reduciendo contención. |
| **Validación de Capas** | Modelos Pydantic v2 | Sanitización, tipado estricto y normalización de textos antes de llegar a la base de datos. |
| **Agnosticismo de SO** | Python 3 + `pathlib` + SQLite nativo | Funciona en Windows, Linux y macOS sin alterar una sola línea de código. |
| **Red Local (LAN)** | Servidor ASGI Uvicorn | Permite que tablets, iPads o celulares conectados a la Wi-Fi del local usen el sistema simultáneamente. |
| **Aseguramiento de Calidad** | Pytest (17 pruebas automatizadas) | Cobertura total de transacciones ACID, concurrencia multi-hilo y endpoints de la API. |

---

### 3. Limitaciones del Sistema (Lo que la aplicación NO cubre)

#### 3.1. Limitaciones Funcionales y de Negocio
1. **Sin Facturación Electrónica Oficial:**
   - El sistema emite comprobantes de venta internos (tickets de comanda / consumo).
   - No está integrado con servicios tributarios oficiales de facturación electrónica (como el SII en Chile, SAT en México, AFIP en Argentina o DIAN en Colombia) ni genera archivos XML/CAF firmados digitalmente.
2. **Inventario Unitario (Sin Escandallos / Recetas / BOM):**
   - El control de existencias descuenta productos terminados (ej. 1 *Café Mocha* descuenta 1 unidad de *Café Mocha*).
   - No cuenta con desglose por receta/insumo (no descuenta 18 g de café en grano, 200 ml de leche y 1 vaso de polipapel de forma desagregada).
3. **Flujo de Pago Inmediato (Sin Mesas Abiertas Persistentes):**
   - Los pedidos se cobran y descuentan stock en el mismo acto de creación del ticket.
   - No incluye flujo de "cuenta abierta" donde una mesa permanezca en estado *Ocupada* acumulando pedidos durante horas antes de solicitar la cuenta final.
4. **Ausencia de Control de Usuarios y Roles (RBAC):**
   - La aplicación no posee inicio de sesión ni roles diferenciados (Cajero vs. Administrador vs. Camarero).
   - Cualquier usuario con acceso a la URL puede visualizar informes financieros, modificar inventario o ejecutar limpiezas.
5. **Comercio Local Único (Single-Store):**
   - Diseñado para funcionar en un único local físico con base de datos local.
   - No dispone de sincronización en la nube multi-sucursal ni consolidación de inventarios entre distintas tiendas.
6. **Sin Pasarela de Pagos Electrónicos Integrada:**
   - La selección de "Tarjeta" o "Transferencia" registra la intención contable, pero no dispara comunicación automática con lectores POS físicos (ej. Transbank, SumUp, Clover, Mercado Pago Point).

#### 3.2. Limitaciones Técnicas y de Infraestructura
1. **Serialización de Escrituras en SQLite:**
   - Aunque SQLite en modo WAL ofrece un rendimiento excepcional para pequeñas y medianas empresas (decenas de transacciones por segundo), el motor permite **un solo escritor simultáneo a la vez**.
   - No está previsto para escenarios de alta concurrencia masiva (ej. decenas de cajas cobrando concurrentemente en centros comerciales).
2. **Cifrado en Reposo de Base de Datos:**
   - El archivo `data/cafeteria.db` no utiliza SQLCipher; cualquier usuario con acceso al sistema de archivos del equipo puede abrir y leer su contenido directamente.
3. **Impresión dependiente del navegador:**
   - La emisión física de tickets utiliza la API estándar `window.print()` del navegador web.
   - No dispone de comunicación directa por socket a puertos COM, USB o red para enviar comandos RAW ESC/POS silenciosos sin abrir el cuadro de diálogo de impresión.

---

### 4. Matriz Comparativa de Capacidades

| Característica | Estado Actual | Observación |
| :--- | :---: | :--- |
| Venta TPV Táctil | **Incluido** | Interfaz optimizada con buscador y carrito. |
| Gestión de Mesas | **Incluido** | Dinámico (1 a N) + Barra / Para Llevar. |
| Integridad ACID y Control de Stock | **Incluido** | Transacciones atómicas, sin stock negativo. |
| Arqueo diario y Reportes de Caja | **Incluido** | Resumen financiero y ranking de ventas. |
| Copias de Seguridad Automáticas | **Incluido** | Snapshots SQLite timestamped en `/backups`. |
| Pruebas Automatizadas | **Incluido** | Suite completa con Pytest (17 pruebas aprobadas). |
| Multiplataforma (Win / Linux / Mac) | **Incluido** | Lanzadores `run.bat` y `run.sh` provistos. |
| Gestión de Mesas Abiertas (Comandas) | *No incluido* | Próxima fase recomendada. |
| Control de Acceso por Roles (Login) | *No incluido* | Próxima fase recomendada. |
| Recetas / Escandallo de Ingredientes | *No incluido* | Requiere módulo de materias primas. |
| Facturación Tributaria Oficial | *No incluido* | Requiere conector o certificado digital de cada país. |
| Sincronización Multi-sucursal Nube | *No incluido* | Fuera del alcance del diseño local. |

---

### 5. Recomendaciones de Escalabilidad (Roadmap Sugerido)

1. **Fase 1 (Seguridad y Auditoría):**
   - Incorporar autenticación simple (PIN numérico o credenciales JWT) para separar los permisos de venta de la administración de inventario y configuración.
2. **Fase 2 (Experiencia Gastronómica):**
   - Habilitar estados de mesas: *Libre*, *Ocupada*, *Por Cobrar*, permitiendo agregar rondas de consumo a una misma cuenta antes del checkout definitivo.
3. **Fase 3 (Hardware):**
   - Integrar un servicio ligero de impresión directa vía sockets o `python-escpos` para imprimir tickets térmicos instantáneamente sin la ventana emergente del navegador.
4. **Fase 4 (Empaquetado Portable):**
   - Generar un ejecutable autónomo con PyInstaller (`CoffeePOS.exe`) que empaquete Python, FastAPI y los recursos web en un solo archivo distribuible sin requerir instalación previa.
