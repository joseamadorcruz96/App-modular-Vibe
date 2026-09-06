-- Pragmas obligatorios de inicialización y resiliencia
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 10000;
PRAGMA synchronous = NORMAL;
PRAGMA encoding = 'UTF-8';

-- 1. Tabla de Configuración General
CREATE TABLE IF NOT EXISTS configuracion (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    descripcion TEXT,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabla de Catálogo de Productos
CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE COLLATE NOCASE,
    nombre TEXT NOT NULL,
    stock_inicial INTEGER NOT NULL CHECK (stock_inicial >= 0),
    stock_actual INTEGER NOT NULL CHECK (stock_actual >= 0),
    costo_unitario REAL NOT NULL CHECK (costo_unitario >= 0),
    precio_venta REAL NOT NULL CHECK (precio_venta >= 0),
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_productos_codigo ON productos(codigo);
CREATE INDEX IF NOT EXISTS idx_productos_activo ON productos(activo);
CREATE INDEX IF NOT EXISTS idx_productos_stock_alerta ON productos(stock_actual) WHERE activo = 1;

-- 3. Tabla de Pedidos (Cabecera de Ticket)
CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_ticket TEXT NOT NULL UNIQUE,
    fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mesa TEXT NOT NULL,
    cliente TEXT DEFAULT 'Consumidor Final',
    medio_pago TEXT NOT NULL CHECK (medio_pago IN ('Efectivo', 'Débito', 'Crédito', 'Transferencia')),
    subtotal REAL NOT NULL CHECK (subtotal >= 0),
    descuento REAL NOT NULL DEFAULT 0.0 CHECK (descuento >= 0),
    total REAL NOT NULL CHECK (total >= 0),
    estado TEXT NOT NULL DEFAULT 'Completado' CHECK (estado IN ('Pendiente', 'Completado', 'Anulado'))
);

CREATE INDEX IF NOT EXISTS idx_pedidos_fecha ON pedidos(fecha_hora);
CREATE INDEX IF NOT EXISTS idx_pedidos_medio_pago ON pedidos(medio_pago);
CREATE INDEX IF NOT EXISTS idx_pedidos_numero_ticket ON pedidos(numero_ticket);

-- 4. Tabla de Líneas de Pedido (Detalles de Ticket)
CREATE TABLE IF NOT EXISTS pedido_detalles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER NOT NULL,
    producto_id INTEGER NOT NULL,
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario REAL NOT NULL CHECK (precio_unitario >= 0),
    subtotal REAL NOT NULL CHECK (subtotal >= 0),
    FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE,
    FOREIGN KEY (producto_id) REFERENCES productos(id)
);

CREATE INDEX IF NOT EXISTS idx_detalles_pedido_id ON pedido_detalles(pedido_id);
CREATE INDEX IF NOT EXISTS idx_detalles_producto_id ON pedido_detalles(producto_id);

-- 5. Tabla de Auditoría de Cierres de Caja
CREATE TABLE IF NOT EXISTS cierres_caja (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_cierre DATE NOT NULL,
    fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_recaudado REAL NOT NULL CHECK (total_recaudado >= 0),
    total_efectivo REAL NOT NULL CHECK (total_efectivo >= 0),
    total_debito REAL NOT NULL CHECK (total_debito >= 0),
    total_credito REAL NOT NULL CHECK (total_credito >= 0),
    total_transferencia REAL NOT NULL CHECK (total_transferencia >= 0),
    cantidad_pedidos INTEGER NOT NULL CHECK (cantidad_pedidos >= 0),
    archivo_backup TEXT NOT NULL
);

-- Semillas iniciales por defecto (si no existen)
INSERT OR IGNORE INTO configuracion (clave, valor, descripcion) VALUES
    ('mesas_activas', '8', 'Cantidad de mesas activas configuradas para la jornada'),
    ('nombre_local', 'CoffeePOS Stand', 'Nombre comercial de la cafetería'),
    ('moneda_simbolo', '$', 'Símbolo de la moneda'),
    ('formato_ticket', '80mm', 'Formato preferido para tickets térmicos (58mm u 80mm)');

