-- Semillas de prueba opcionales (Cafetería Demo)
INSERT OR IGNORE INTO productos (codigo, nombre, stock_inicial, stock_actual, costo_unitario, precio_venta, activo) VALUES
    ('CAF01', 'Espresso Simple', 50, 45, 600, 1800, 1),
    ('CAF02', 'Espresso Doble', 50, 38, 900, 2400, 1),
    ('CAF03', 'Americano Clásico', 40, 32, 700, 2100, 1),
    ('CAF04', 'Capuccino Italiano', 40, 25, 1100, 2800, 1),
    ('CAF05', 'Café Latte Vainilla', 30, 20, 1300, 3200, 1),
    ('CAF06', 'Mocaccino Especial', 30, 15, 1400, 3400, 1),
    ('PAN01', 'Croissant de Mantequilla', 25, 12, 1000, 2200, 1),
    ('PAN02', 'Tostón Palta y Huevo', 20, 4, 1600, 3800, 1),
    ('BEB01', 'Té Matcha Orgánico', 25, 3, 1200, 2900, 1),
    ('BEB02', 'Jugo Naranja Exprimido', 20, 18, 900, 2500, 1);

-- Insumos de prueba
INSERT OR IGNORE INTO insumos (codigo, nombre, unidad_medida, stock_actual, stock_minimo, costo_unitario, activo) VALUES
    ('INS-CAFE', 'Café en Grano Tostado Especial', 'g', 5000.0, 500.0, 25.0, 1),
    ('INS-LECHE', 'Leche Entera Barista', 'ml', 10000.0, 1000.0, 1.5, 1),
    ('INS-CHOCO', 'Salsa de Chocolate Belga', 'ml', 2000.0, 200.0, 8.0, 1),
    ('INS-VAINI', 'Jarabe de Vainilla Natural', 'ml', 1500.0, 150.0, 10.0, 1),
    ('INS-VASO', 'Vaso Térmico Polipapel 12oz', 'unidad', 200.0, 30.0, 120.0, 1);

-- Recetas para cafés (producto_id vinculados por id / subconsultas)
-- CAF01 (Espresso): 18g Café
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 18.0 FROM productos p, insumos i WHERE p.codigo = 'CAF01' AND i.codigo = 'INS-CAFE';

-- CAF04 (Capuccino): 18g Café + 150ml Leche
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 18.0 FROM productos p, insumos i WHERE p.codigo = 'CAF04' AND i.codigo = 'INS-CAFE';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 150.0 FROM productos p, insumos i WHERE p.codigo = 'CAF04' AND i.codigo = 'INS-LECHE';

-- CAF05 (Latte Vainilla): 18g Café + 180ml Leche + 15ml Vainilla
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 18.0 FROM productos p, insumos i WHERE p.codigo = 'CAF05' AND i.codigo = 'INS-CAFE';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 180.0 FROM productos p, insumos i WHERE p.codigo = 'CAF05' AND i.codigo = 'INS-LECHE';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 15.0 FROM productos p, insumos i WHERE p.codigo = 'CAF05' AND i.codigo = 'INS-VAINI';

-- CAF06 (Mocaccino): 18g Café + 150ml Leche + 20ml Chocolate
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 18.0 FROM productos p, insumos i WHERE p.codigo = 'CAF06' AND i.codigo = 'INS-CAFE';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 150.0 FROM productos p, insumos i WHERE p.codigo = 'CAF06' AND i.codigo = 'INS-LECHE';
INSERT OR IGNORE INTO receta_detalles (producto_id, insumo_id, cantidad)
SELECT p.id, i.id, 20.0 FROM productos p, insumos i WHERE p.codigo = 'CAF06' AND i.codigo = 'INS-CHOCO';
