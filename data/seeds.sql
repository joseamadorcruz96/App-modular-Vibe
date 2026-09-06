-- ==============================================================================
-- CATÁLOGO OFICIAL Y SEMILLAS DE PRECARGA - COFFEESOKA
-- Fuente: menu_cafeteria (1).md
-- Nota: Sin costos inventados (costo = 0) y sin recetas predefinidas.
-- ==============================================================================

INSERT OR IGNORE INTO productos (codigo, nombre, stock_inicial, stock_actual, costo_unitario, precio_venta, activo) VALUES
    -- Salado
    ('SAL01', 'Completo italiano', 40, 40, 0.0, 2500.0, 1),
    ('SAL02', 'Hamburguesa', 30, 30, 0.0, 3500.0, 1),

    -- Pasteles
    ('PAS01', 'Torta amor', 11, 11, 0.0, 4000.0, 1),
    ('PAS02', 'Brownie', 16, 16, 0.0, 1300.0, 1),
    ('PAS03', 'Kuchen de manzana', 8, 8, 0.0, 2000.0, 1),
    ('PAS04', 'Pie de maracuyá', 16, 16, 0.0, 2500.0, 1),
    ('PAS05', 'Pie de limón', 16, 16, 0.0, 2000.0, 1),
    ('PAS06', 'Rollitos de canela', 12, 12, 0.0, 1500.0, 1),
    ('PAS07', 'Rollito canela / manzana', 6, 6, 0.0, 2000.0, 1),
    ('PAS08', 'Rollito canela / pie de limón', 6, 6, 0.0, 2000.0, 1),
    ('PAS09', 'Queque Masala chai naranja', 14, 14, 0.0, 1500.0, 1),
    ('PAS10', 'Kuchen de nuez', 8, 8, 0.0, 2000.0, 1),

    -- Café
    ('CAF01', 'Expresso', 0, 0, 0.0, 1500.0, 1),
    ('CAF02', 'Americano', 0, 0, 0.0, 1800.0, 1),
    ('CAF03', 'Capuchino', 0, 0, 0.0, 2500.0, 1),
    ('CAF04', 'Latte', 0, 0, 0.0, 2500.0, 1),
    ('CAF05', 'Mocca', 0, 0, 0.0, 3000.0, 1),

    -- Bebestibles: Té e infusiones
    ('INF01', 'Hoja con canela', 0, 0, 0.0, 800.0, 1),
    ('INF02', 'Masala chai', 0, 0, 0.0, 2000.0, 1),
    ('INF03', 'Earl grey', 0, 0, 0.0, 1500.0, 1),
    ('INF04', 'Chai latte', 0, 0, 0.0, 2500.0, 1),
    ('INF05', 'Basilur raspberry & rosehip', 0, 0, 0.0, 1500.0, 1),

    -- Bebestibles: Otros
    ('BEB01', 'Café instantáneo', 0, 0, 0.0, 700.0, 1),
    ('BEB02', 'Bebida', 0, 0, 0.0, 600.0, 1);
