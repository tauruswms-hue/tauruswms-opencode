-- ============================================================
-- Datos de prueba: Taurus WMS
-- Inserta: tipoubicacion, categorias, materiales, ubicaciones
-- y registros de stockcontable.
-- Seguro para re-ejecutar (INSERT IGNORE / ON DUPLICATE KEY).
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- 1. TIPOS DE UBICACIÓN
-- ============================================================
INSERT IGNORE INTO tipoubicacion (`descipción`) VALUES
    ('Rack selectivo'),
    ('Piso'),
    ('Cámara fría'),
    ('Zona de cuarentena');

-- ============================================================
-- 2. CATEGORÍAS DE MATERIAL
-- ============================================================
INSERT INTO categorias (codigo, nombre, descripcion, activo)
VALUES
    ('ALIM',  'Alimentos',          'Productos alimenticios y bebidas',      1),
    ('LIMP',  'Limpieza',           'Artículos de limpieza e higiene',       1),
    ('ELEC',  'Electrónica',        'Dispositivos y accesorios electrónicos',1),
    ('FARM',  'Farmacéuticos',      'Medicamentos y productos de salud',     1),
    ('PLAS',  'Plásticos',          'Envases y productos plásticos',         1)
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);

-- ============================================================
-- 3. MATERIALES
-- ============================================================
INSERT INTO materiales (codigo, nombre, descripcion, categoria_id, stock_minimo, stock_maximo, activo)
VALUES
    ('MAT-001', 'Arroz 000 x 1kg',          'Arroz largo fino bolsa 1 kg',       (SELECT id_categoria FROM categorias WHERE codigo='ALIM'), 100, 2000, 1),
    ('MAT-002', 'Aceite girasol x 900ml',    'Aceite de girasol botella 900 ml',  (SELECT id_categoria FROM categorias WHERE codigo='ALIM'),  50, 1500, 1),
    ('MAT-003', 'Detergente en polvo x 1kg', 'Detergente doméstico 1 kg',         (SELECT id_categoria FROM categorias WHERE codigo='LIMP'),  30,  800, 1),
    ('MAT-004', 'Lavandina 1L',              'Lavandina concentrada 1 litro',     (SELECT id_categoria FROM categorias WHERE codigo='LIMP'),  20,  600, 1),
    ('MAT-005', 'Ibuprofeno 400mg x 20 comp','Ibuprofeno 400 mg blíster 20 comp', (SELECT id_categoria FROM categorias WHERE codigo='FARM'),  10,  300, 1),
    ('MAT-006', 'Paracetamol 500mg x 24 tab','Paracetamol 500 mg tabletas x 24', (SELECT id_categoria FROM categorias WHERE codigo='FARM'),  10,  300, 1),
    ('MAT-007', 'Cable USB-C 1m',            'Cable carga rápida USB-C 1 metro',  (SELECT id_categoria FROM categorias WHERE codigo='ELEC'),   5,  200, 1),
    ('MAT-008', 'Bolsa polietileno 50x70',   'Bolsa transparente 50x70 cm x 100',(SELECT id_categoria FROM categorias WHERE codigo='PLAS'),  50, 1000, 1)
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);

-- ============================================================
-- 4. UBICACIONES
-- ============================================================
INSERT INTO ubicaciones (codigo, descipcion, tipoubicacion, zona, coordenadaA, coordenadaB, coordenadaC, coordenadaD, capacidad_maxima, disponible_entrada, disponible_salida)
VALUES
    ('A-01-01', 'Pasillo A, Rack 01, Nivel 1', (SELECT id FROM tipoubicacion WHERE `descipción`='Rack selectivo'    LIMIT 1), 'ZONA_A', 'A','01','01','01', 500, 1, 1),
    ('A-01-02', 'Pasillo A, Rack 01, Nivel 2', (SELECT id FROM tipoubicacion WHERE `descipción`='Rack selectivo'    LIMIT 1), 'ZONA_A', 'A','01','02','01', 500, 1, 1),
    ('A-02-01', 'Pasillo A, Rack 02, Nivel 1', (SELECT id FROM tipoubicacion WHERE `descipción`='Rack selectivo'    LIMIT 1), 'ZONA_A', 'A','02','01','01', 500, 1, 1),
    ('B-01-01', 'Pasillo B, Rack 01, Nivel 1', (SELECT id FROM tipoubicacion WHERE `descipción`='Rack selectivo'    LIMIT 1), 'ZONA_B', 'B','01','01','01', 400, 1, 1),
    ('B-01-02', 'Pasillo B, Rack 01, Nivel 2', (SELECT id FROM tipoubicacion WHERE `descipción`='Rack selectivo'    LIMIT 1), 'ZONA_B', 'B','01','02','01', 400, 1, 1),
    ('CF-01',   'Cámara fría 1',               (SELECT id FROM tipoubicacion WHERE `descipción`='Cámara fría'       LIMIT 1), 'FRIO',   'CF','01','01','01',1000, 1, 1),
    ('PISO-A',  'Zona piso A',                 (SELECT id FROM tipoubicacion WHERE `descipción`='Piso'              LIMIT 1), 'ZONA_A', 'A', 'P', '01','01',2000, 1, 1),
    ('CUAR-01', 'Cuarentena 1',                (SELECT id FROM tipoubicacion WHERE `descipción`='Zona de cuarentena'LIMIT 1), 'CUAR',   'C', '01','01','01', 200, 0, 0)
ON DUPLICATE KEY UPDATE descipcion = VALUES(descipcion);

-- ============================================================
-- 5. STOCK CONTABLE
-- ============================================================

-- Limpiar datos previos de prueba (opcional, comentar si no se desea)
-- DELETE FROM stockcontable;

INSERT INTO stockcontable
    (Ubicacion, Material, IDContenedor, Lote, TipoStock,
     StockTotal, StockDisponible, StockEntrando, StockSaliendo,
     UltimaEntrada, UltimaSalida, UltimoMovimiento, UsuarioUltimoMov,
     FechaVencimiento)
VALUES

-- Arroz en ZONA_A --------------------------------------------------------
(
    (SELECT id FROM ubicaciones WHERE codigo='A-01-01'),
    (SELECT id FROM materiales  WHERE codigo='MAT-001'),
    'CN-001', 'L2025-001', 'Libre Venta',
    350.0000, 350.0000, 0.0000, 0.0000,
    '2025-02-10 08:30:00', NULL, '2025-02-10 08:30:00', 'admin',
    '2026-08-01'
),
(
    (SELECT id FROM ubicaciones WHERE codigo='A-01-01'),
    (SELECT id FROM materiales  WHERE codigo='MAT-001'),
    'CN-002', 'L2025-002', 'Libre Venta',
    200.0000, 180.0000, 0.0000, 20.0000,
    '2025-03-05 09:15:00', '2025-03-10 14:00:00', '2025-03-10 14:00:00', 'jperez',
    '2026-09-01'
),
(
    (SELECT id FROM ubicaciones WHERE codigo='A-01-02'),
    (SELECT id FROM materiales  WHERE codigo='MAT-001'),
    'CN-003', 'L2024-012', 'Calidad',
    100.0000, 0.0000, 0.0000, 0.0000,
    '2024-12-20 07:00:00', NULL, '2025-01-15 10:00:00', 'supervisor',
    '2025-12-31'
),

-- Aceite ----------------------------------------------------------------
(
    (SELECT id FROM ubicaciones WHERE codigo='A-02-01'),
    (SELECT id FROM materiales  WHERE codigo='MAT-002'),
    'CN-010', 'L2025-010', 'Libre Venta',
    480.0000, 460.0000, 0.0000, 20.0000,
    '2025-01-18 11:00:00', '2025-02-28 16:30:00', '2025-02-28 16:30:00', 'admin',
    '2026-06-15'
),
(
    (SELECT id FROM ubicaciones WHERE codigo='PISO-A'),
    (SELECT id FROM materiales  WHERE codigo='MAT-002'),
    'CN-011', 'L2025-010', 'Libre Venta',
    600.0000, 600.0000, 150.0000, 0.0000,
    '2025-03-01 07:45:00', NULL, '2025-03-01 07:45:00', 'jperez',
    '2026-06-15'
),

-- Detergente ------------------------------------------------------------
(
    (SELECT id FROM ubicaciones WHERE codigo='B-01-01'),
    (SELECT id FROM materiales  WHERE codigo='MAT-003'),
    'CN-020', 'L2025-020', 'Libre Venta',
    250.0000, 250.0000, 0.0000, 0.0000,
    '2025-02-20 09:00:00', NULL, '2025-02-20 09:00:00', 'admin',
    '2027-02-20'
),
(
    (SELECT id FROM ubicaciones WHERE codigo='B-01-01'),
    (SELECT id FROM materiales  WHERE codigo='MAT-003'),
    'CN-021', 'L2024-045', 'Bloqueado',
    80.0000, 0.0000, 0.0000, 0.0000,
    '2024-11-05 10:00:00', NULL, '2025-01-10 08:00:00', 'supervisor',
    '2025-11-05'
),

-- Lavandina -------------------------------------------------------------
(
    (SELECT id FROM ubicaciones WHERE codigo='B-01-02'),
    (SELECT id FROM materiales  WHERE codigo='MAT-004'),
    'CN-030', 'L2025-030', 'Libre Venta',
    320.0000, 300.0000, 0.0000, 20.0000,
    '2025-02-25 08:00:00', '2025-03-08 13:00:00', '2025-03-08 13:00:00', 'jperez',
    '2026-02-25'
),

-- Ibuprofeno (farmacéutico con lotes de frío) ---------------------------
(
    (SELECT id FROM ubicaciones WHERE codigo='CF-01'),
    (SELECT id FROM materiales  WHERE codigo='MAT-005'),
    'CN-040', 'IB-2025-A01', 'Libre Venta',
    150.0000, 130.0000, 30.0000, 0.0000,
    '2025-01-10 06:00:00', '2025-02-15 11:30:00', '2025-02-15 11:30:00', 'farmacia',
    '2027-01-31'
),
(
    (SELECT id FROM ubicaciones WHERE codigo='CF-01'),
    (SELECT id FROM materiales  WHERE codigo='MAT-005'),
    'CN-041', 'IB-2024-B05', 'Calidad',
    40.0000, 0.0000, 0.0000, 0.0000,
    '2024-10-01 06:30:00', NULL, '2025-02-01 09:00:00', 'supervisor',
    '2026-09-30'
),
(
    (SELECT id FROM ubicaciones WHERE codigo='CUAR-01'),
    (SELECT id FROM materiales  WHERE codigo='MAT-005'),
    'CN-042', 'IB-2024-B03', 'Bloqueado',
    25.0000, 0.0000, 0.0000, 0.0000,
    '2024-09-15 07:00:00', NULL, '2025-01-20 14:00:00', 'supervisor',
    '2026-09-15'
),

-- Paracetamol -----------------------------------------------------------
(
    (SELECT id FROM ubicaciones WHERE codigo='CF-01'),
    (SELECT id FROM materiales  WHERE codigo='MAT-006'),
    'CN-050', 'PC-2025-001', 'Libre Venta',
    200.0000, 185.0000, 50.0000, 15.0000,
    '2025-02-01 06:15:00', '2025-03-05 10:00:00', '2025-03-05 10:00:00', 'farmacia',
    '2027-06-30'
),
(
    (SELECT id FROM ubicaciones WHERE codigo='CF-01'),
    (SELECT id FROM materiales  WHERE codigo='MAT-006'),
    'CN-051', 'PC-2024-010', 'Mal Estado',
    10.0000, 0.0000, 0.0000, 0.0000,
    '2024-08-01 06:00:00', NULL, '2025-01-05 08:30:00', 'supervisor',
    '2025-07-31'
),

-- Cable USB-C -----------------------------------------------------------
(
    (SELECT id FROM ubicaciones WHERE codigo='A-02-01'),
    (SELECT id FROM materiales  WHERE codigo='MAT-007'),
    'CN-060', 'UNICO', 'Libre Venta',
    90.0000, 80.0000, 0.0000, 10.0000,
    '2025-01-25 10:00:00', '2025-03-01 15:00:00', '2025-03-01 15:00:00', 'admin',
    NULL
),

-- Bolsas de polietileno -------------------------------------------------
(
    (SELECT id FROM ubicaciones WHERE codigo='PISO-A'),
    (SELECT id FROM materiales  WHERE codigo='MAT-008'),
    'CN-070', 'UNICO', 'Libre Venta',
    800.0000, 800.0000, 200.0000, 0.0000,
    '2025-03-03 07:00:00', NULL, '2025-03-03 07:00:00', 'jperez',
    NULL
),
(
    (SELECT id FROM ubicaciones WHERE codigo='B-01-02'),
    (SELECT id FROM materiales  WHERE codigo='MAT-008'),
    'CN-071', 'UNICO', 'Libre Venta',
    400.0000, 350.0000, 0.0000, 50.0000,
    '2025-02-10 09:30:00', '2025-03-07 12:00:00', '2025-03-07 12:00:00', 'admin',
    NULL
)

ON DUPLICATE KEY UPDATE
    StockTotal      = VALUES(StockTotal),
    StockDisponible = VALUES(StockDisponible),
    StockEntrando   = VALUES(StockEntrando),
    StockSaliendo   = VALUES(StockSaliendo);

SET FOREIGN_KEY_CHECKS = 1;

SELECT CONCAT('Registros en stockcontable: ', COUNT(*)) AS resultado FROM stockcontable;
