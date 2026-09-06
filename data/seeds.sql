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
