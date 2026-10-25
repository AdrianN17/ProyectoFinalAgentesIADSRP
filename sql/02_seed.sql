-- Datos de prueba · AndesSupply · caso CRE-001
-- Línea base estática. init_db.py aplica después, con la semilla 7885, los valores
-- derivados (límite/exposición de C-1003, stock y lead time de EDGE-ORIN, monto de revisión).

DELETE FROM ops.liberaciones;
DELETE FROM ops.pagos;
DELETE FROM ops.venta_items;
DELETE FROM ops.ventas;
DELETE FROM ops.inventario;
DELETE FROM ops.productos;
DELETE FROM ops.clientes;
DELETE FROM ops.parametros_caso;
GO

INSERT INTO ops.clientes (cliente_id, nombre, segmento, estado_credito, limite_credito, exposicion_actual, plazo_dias) VALUES
('C-1001', N'Minera Cordillera S.A.',       'gran_cuenta', 'activo', 250000.00, 40000.00, 30),  -- sano
('C-1002', N'Constructora Altiplano SAC',   'mediana',     'activo',  60000.00, 52000.00, 30),  -- línea ajustada
('C-1003', N'Industrias Pacífico SAC',      'mediana',     'activo',  40000.00, 30000.00, 45),  -- cliente del caso
('C-1004', N'Agroexport Valle Verde S.A.',  'mediana',     'hold',    80000.00, 78000.00, 30),  -- en hold por mora
('C-1005', N'Logística Andina EIRL',        'pequena',     'activo', 120000.00, 15000.00, 30);  -- sano

INSERT INTO ops.productos (sku, nombre, categoria, precio_unitario, lead_time_dias) VALUES
('EDGE-ORIN',  N'Gateway industrial EDGE-ORIN',     'edge_computing', 1850.00,  5),
('EDGE-VEGA',  N'Gateway industrial EDGE-VEGA',     'edge_computing', 2400.00,  7),
('SENS-TERRA', N'Sensor ambiental SENS-TERRA',      'sensores',        320.00,  3),
('SENS-AQUA',  N'Sensor de caudal SENS-AQUA',       'sensores',        410.00,  3),
('PLC-ANDES',  N'Controlador lógico PLC-ANDES',     'automatizacion', 3100.00, 10),
('CAB-IND',    N'Kit de cableado industrial CAB-IND','accesorios',       95.00,  2);

INSERT INTO ops.inventario (sku, stock_disponible, stock_reservado) VALUES
('EDGE-ORIN',   35,  4),
('EDGE-VEGA',   12,  0),
('SENS-TERRA', 400, 20),
('SENS-AQUA',  150,  0),
('PLC-ANDES',    8,  2),
('CAB-IND',    900, 50);

INSERT INTO ops.ventas (venta_id, cliente_id, fecha, total, estado, condicion_pago) VALUES
(5001, 'C-1001', '2026-03-10', 18500.00, 'facturada', 'credito_30'),
(5002, 'C-1001', '2026-06-02',  9600.00, 'facturada', 'credito_30'),
(5003, 'C-1002', '2026-05-12', 15500.00, 'facturada', 'credito_30'),
(5004, 'C-1002', '2026-09-03', 12400.00, 'facturada', 'credito_30'),
(5005, 'C-1003', '2026-02-18',  9250.00, 'facturada', 'credito_45'),
(5006, 'C-1003', '2026-05-05',  6400.00, 'facturada', 'credito_45'),
(5007, 'C-1003', '2026-09-12', 18500.00, 'liberada',  'credito_45'),
(5008, 'C-1004', '2026-04-02', 24000.00, 'facturada', 'credito_30'),
(5009, 'C-1004', '2026-06-15', 15500.00, 'facturada', 'credito_30'),
(5010, 'C-1005', '2026-08-01',  4100.00, 'facturada', 'credito_30'),
(5011, 'C-1005', '2026-09-20',  1900.00, 'facturada', 'credito_30');

INSERT INTO ops.venta_items (venta_id, sku, cantidad, precio_unitario) VALUES
(5001, 'EDGE-ORIN',  10, 1850.00),
(5002, 'EDGE-VEGA',   4, 2400.00),
(5003, 'PLC-ANDES',   5, 3100.00),
(5004, 'PLC-ANDES',   4, 3100.00),
(5005, 'EDGE-ORIN',   5, 1850.00),
(5006, 'SENS-TERRA', 20,  320.00),
(5007, 'EDGE-ORIN',  10, 1850.00),
(5008, 'EDGE-VEGA',  10, 2400.00),
(5009, 'PLC-ANDES',   5, 3100.00),
(5010, 'SENS-AQUA',  10,  410.00),
(5011, 'CAB-IND',    20,   95.00);

INSERT INTO ops.pagos (pago_id, venta_id, cliente_id, monto, fecha_vencimiento, fecha_pago, estado) VALUES
(9001, 5001, 'C-1001', 18500.00, '2026-04-09', '2026-04-05', 'pagado'),
(9002, 5002, 'C-1001',  9600.00, '2026-07-02', '2026-07-01', 'pagado'),
(9003, 5003, 'C-1002', 15500.00, '2026-06-11', '2026-06-30', 'pagado'),   -- pagó con atraso
(9004, 5004, 'C-1002', 12400.00, '2026-10-02', NULL,         'vencido'),
(9005, 5005, 'C-1003',  9250.00, '2026-04-04', '2026-04-02', 'pagado'),
(9006, 5006, 'C-1003',  6400.00, '2026-06-19', '2026-06-18', 'pagado'),
(9007, 5007, 'C-1003', 18500.00, '2026-10-27', NULL,         'pendiente'),
(9008, 5008, 'C-1004', 24000.00, '2026-05-02', NULL,         'vencido'),
(9009, 5009, 'C-1004', 15500.00, '2026-07-15', NULL,         'vencido'),
(9010, 5010, 'C-1005',  4100.00, '2026-08-31', '2026-08-28', 'pagado'),
(9011, 5011, 'C-1005',  1900.00, '2026-10-19', NULL,         'pendiente');

INSERT INTO ops.parametros_caso (clave, valor) VALUES
('caso_id',        'CRE-001'),
('semilla',        '7885'),
('monto_revision', '20000.00');
GO
