-- ==============================================================================
-- SEMILLAS DE PRUEBAS UNITARIAS CON RECETAS E INSUMOS
-- Utilizado exclusivamente por las suites de pruebas de recetas, comandas e insumos.
-- ==============================================================================

-- 1. Catálogo de Productos Terminados para Pruebas
INSERT OR IGNORE INTO productos (codigo, nombre, stock_inicial, stock_actual, costo_unitario, precio_venta, activo) VALUES
    ('CAF01', 'Espresso Simple', 50, 45, 450, 1800, 1),
    ('CAF02', 'Espresso Doble', 50, 38, 900, 2400, 1),
    ('CAF03', 'Americano Clásico', 40, 32, 570, 2100, 1),
    ('CAF04', 'Capuccino Italiano', 40, 25, 675, 2800, 1),
    ('CAF05', 'Café Latte Vainilla', 30, 20, 870, 3200, 1),
    ('CAF06', 'Mocaccino Especial', 30, 15, 835, 3400, 1),
    ('PAN01', 'Croissant de Mantequilla Francés', 25, 12, 356, 2200, 1),
    ('PAN02', 'Tostón Palta Hass y Huevo de Campo', 20, 14, 1150, 3800, 1),
    ('BEB01', 'Té Matcha Latte Orgánico', 25, 20, 600, 2900, 1),
    ('BEB02', 'Jugo Naranja Natural Exprimido', 20, 18, 720, 2500, 1),
    ('SAN01', 'Sandwich Jamón Pierna y Queso Gouda', 20, 16, 1450, 3600, 1);

-- 2. Materias Primas / Insumos
INSERT OR IGNORE INTO insumos (codigo, nombre, unidad_medida, stock_actual, stock_minimo, costo_unitario, activo) VALUES
    ('INS-CAFE', 'Café en Grano Tostado Especial', 'g', 5000.0, 500.0, 25.0, 1),
    ('INS-LECHE', 'Leche Entera Barista', 'ml', 10000.0, 1000.0, 1.5, 1),
    ('INS-CHOCO', 'Salsa de Chocolate Belga', 'ml', 2000.0, 200.0, 8.0, 1),
    ('INS-VAINI', 'Jarabe de Vainilla Natural', 'ml', 1500.0, 150.0, 10.0, 1),
    ('INS-MATCHA', 'Té Matcha Grado Ceremonial en Polvo', 'g', 500.0, 50.0, 60.0, 1),
    ('INS-NARANJA', 'Naranjas Frescas para Jugo', 'unidad', 150.0, 30.0, 180.0, 1),
    ('INS-VASO', 'Vaso Térmico Polipapel 12oz', 'unidad', 200.0, 30.0, 120.0, 1),
    ('INS-PAN', 'Pan de Masa Madre Artesanal', 'unidad', 60.0, 10.0, 400.0, 1),
    ('INS-PALTA', 'Palta Hass Seleccionada', 'g', 3500.0, 500.0, 5.0, 1),
    ('INS-HUEVO', 'Huevo de Campo Fresco', 'unidad', 80.0, 12.0, 250.0, 1),
    ('INS-HARINA', 'Harina de Trigo Panadera', 'g', 10000.0, 1000.0, 1.2, 1),
    ('INS-MANTE', 'Mantequilla sin Sal 82% Grasa', 'g', 3000.0, 500.0, 6.5, 1),
    ('INS-JAMON', 'Jamón Pierna Artesanal Laminado', 'g', 2500.0, 400.0, 9.0, 1),
    ('INS-QUESO', 'Queso Gouda Laminado Fundido', 'g', 2500.0, 400.0, 8.5, 1);

-- 3. Recetas (Escandallos vinculados a productos terminados)
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 18.0 FROM productos p, insumos i WHERE p.codigo = 'CAF01' AND i.codigo = 'INS-CAFE';

INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 36.0 FROM productos p, insumos i WHERE p.codigo = 'CAF02' AND i.codigo = 'INS-CAFE';

INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 18.0 FROM productos p, insumos i WHERE p.codigo = 'CAF03' AND i.codigo = 'INS-CAFE';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 1.0 FROM productos p, insumos i WHERE p.codigo = 'CAF03' AND i.codigo = 'INS-VASO';

INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 18.0 FROM productos p, insumos i WHERE p.codigo = 'CAF04' AND i.codigo = 'INS-CAFE';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 150.0 FROM productos p, insumos i WHERE p.codigo = 'CAF04' AND i.codigo = 'INS-LECHE';

INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 18.0 FROM productos p, insumos i WHERE p.codigo = 'CAF05' AND i.codigo = 'INS-CAFE';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 180.0 FROM productos p, insumos i WHERE p.codigo = 'CAF05' AND i.codigo = 'INS-LECHE';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 15.0 FROM productos p, insumos i WHERE p.codigo = 'CAF05' AND i.codigo = 'INS-VAINI';

INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 18.0 FROM productos p, insumos i WHERE p.codigo = 'CAF06' AND i.codigo = 'INS-CAFE';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 150.0 FROM productos p, insumos i WHERE p.codigo = 'CAF06' AND i.codigo = 'INS-LECHE';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 20.0 FROM productos p, insumos i WHERE p.codigo = 'CAF06' AND i.codigo = 'INS-CHOCO';

INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 5.0 FROM productos p, insumos i WHERE p.codigo = 'BEB01' AND i.codigo = 'INS-MATCHA';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 200.0 FROM productos p, insumos i WHERE p.codigo = 'BEB01' AND i.codigo = 'INS-LECHE';

INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 4.0 FROM productos p, insumos i WHERE p.codigo = 'BEB02' AND i.codigo = 'INS-NARANJA';

INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 80.0 FROM productos p, insumos i WHERE p.codigo = 'PAN01' AND i.codigo = 'INS-HARINA';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 40.0 FROM productos p, insumos i WHERE p.codigo = 'PAN01' AND i.codigo = 'INS-MANTE';

INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 1.0 FROM productos p, insumos i WHERE p.codigo = 'PAN02' AND i.codigo = 'INS-PAN';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 100.0 FROM productos p, insumos i WHERE p.codigo = 'PAN02' AND i.codigo = 'INS-PALTA';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 1.0 FROM productos p, insumos i WHERE p.codigo = 'PAN02' AND i.codigo = 'INS-HUEVO';

INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 1.0 FROM productos p, insumos i WHERE p.codigo = 'SAN01' AND i.codigo = 'INS-PAN';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 60.0 FROM productos p, insumos i WHERE p.codigo = 'SAN01' AND i.codigo = 'INS-JAMON';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 60.0 FROM productos p, insumos i WHERE p.codigo = 'SAN01' AND i.codigo = 'INS-QUESO';
