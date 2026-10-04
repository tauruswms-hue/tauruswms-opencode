-- ============================================================
-- Datos de prueba: Clientes, Proveedores, material_proveedor
-- También agrega rutas, transportes y ubicación de recepción.
-- Seguro para re-ejecutar (INSERT IGNORE / ON DUPLICATE KEY).
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- 1. TIPO DE UBICACIÓN: Recepción Material nuevo
--    (necesario para el módulo de Recepciones)
-- ============================================================
INSERT IGNORE INTO tipoubicacion (`descipción`) VALUES
    ('Recepción Material nuevo');

-- Ubicación física de recepción
INSERT INTO ubicaciones
    (codigo, descipcion, tipoubicacion, zona,
     coordenadaA, coordenadaB, coordenadaC, coordenadaD,
     capacidad_maxima, disponible_entrada, disponible_salida)
VALUES
    ('RECEP-01', 'Zona de recepción de materiales',
     (SELECT id FROM tipoubicacion WHERE `descipción` = 'Recepción Material nuevo' LIMIT 1),
     'RECEP', 'R', '01', '01', '01', 5000, 1, 0)
ON DUPLICATE KEY UPDATE descipcion = VALUES(descipcion);


-- ============================================================
-- 2. RUTAS DE DISTRIBUCIÓN
-- ============================================================
INSERT INTO rutas (nombre_ruta, descripcion) VALUES
    ('Zona Norte',   'Clientes zona norte: Rosario Norte, Villa Gobernador Gálvez'),
    ('Zona Sur',     'Clientes zona sur: Funes, Roldán, Soldini'),
    ('Zona Centro',  'Clientes zona centro: microcentro y área comercial')
ON DUPLICATE KEY UPDATE descripcion = VALUES(descripcion);


-- ============================================================
-- 3. TRANSPORTES
-- ============================================================
INSERT INTO transportes (codigo, razonsocial, cuit, telefono, email, activo) VALUES
    ('TRA-001', 'Logística Rápida S.A.',        '30712345678', '0341-4100001', 'logistica@rapida.com.ar',  1),
    ('TRA-002', 'Transporte del Sur S.R.L.',    '30787654321', '0341-4200002', 'operaciones@trasur.com.ar', 1),
    ('TRA-003', 'Distribuidora Centro S.A.',    '30798765432', '0341-4300003', 'centro@distribuidora.com',  1)
ON DUPLICATE KEY UPDATE razonsocial = VALUES(razonsocial);

-- Asignación transporte ↔ rutas
INSERT IGNORE INTO transporte_rutas (id_transporte, id_ruta, observaciones)
SELECT t.id_transporte, r.id_ruta, 'Asignación inicial'
FROM transportes t, rutas r
WHERE (t.codigo = 'TRA-001' AND r.nombre_ruta IN ('Zona Norte', 'Zona Centro'))
   OR (t.codigo = 'TRA-002' AND r.nombre_ruta = 'Zona Sur')
   OR (t.codigo = 'TRA-003' AND r.nombre_ruta = 'Zona Centro');


-- ============================================================
-- 4. PROVEEDORES
-- ============================================================
INSERT INTO proveedores (codigo, razonsocial, cuit, direccion, telefono, email, activo) VALUES
    ('PROV-001', 'Alimentos del Sur S.A.',                '30501234567', 'Av. Circunvalación 1200, Rosario',   '0341-4501200', 'compras@alimentosdelsur.com',    1),
    ('PROV-002', 'Distribuidora Limpieza Hogar S.R.L.',   '30512345678', 'Calle Tucumán 450, Rosario',         '0341-4512345', 'ventas@limpiezahogar.com',        1),
    ('PROV-003', 'Laboratorios Farmacéuticos Norte S.A.', '30523456789', 'Parque Industrial Lote 22, Rosario', '0341-4523456', 'pedidos@labfarmnorte.com',        1),
    ('PROV-004', 'Tech Supplies Argentina S.A.',          '30534567890', 'Av. Pellegrini 800, Rosario',        '0341-4534567', 'comercial@techsupplies.com.ar',   1),
    ('PROV-005', 'Envases Plásticos S.R.L.',              '30545678901', 'Ruta 9 Km 12, Granadero Baigorria',  '0341-4545678', 'ventas@envasesplasticos.com.ar', 1),
    ('PROV-006', 'Importadora General S.A.',              '30556789012', 'Av. San Martín 3500, Rosario',       '0341-4556789', 'importa@importadorageneral.com',  1)
ON DUPLICATE KEY UPDATE razonsocial = VALUES(razonsocial), activo = VALUES(activo);


-- ============================================================
-- 5. CLIENTES
-- ============================================================
INSERT INTO clientes
    (codigo, razonsocial, cuit, direccion, localidad, provincia,
     telefono, email, contacto_nombre,
     id_ruta, id_transporte_predeterminado, activo)
VALUES
    -- Zona Norte
    ('CLI-001', 'Supermercado El Ahorro S.A.',
     '30611000001', 'Av. Francia 2800',       'Rosario', 'Santa Fe',
     '0341-4611001', 'compras@elahorro.com',  'Martín Soria',
     (SELECT id_ruta FROM rutas WHERE nombre_ruta='Zona Norte' LIMIT 1),
     (SELECT id_transporte FROM transportes WHERE codigo='TRA-001' LIMIT 1), 1),

    ('CLI-002', 'Mini Market Los Álamos',
     '20612000002', 'Catamarca 1450',         'Rosario', 'Santa Fe',
     '0341-4612002', 'losalamos@gmail.com',   'Laura Pérez',
     (SELECT id_ruta FROM rutas WHERE nombre_ruta='Zona Norte' LIMIT 1),
     (SELECT id_transporte FROM transportes WHERE codigo='TRA-001' LIMIT 1), 1),

    ('CLI-003', 'Hipermercado Río S.A.',
     '30613000003', 'Av. Avellaneda 5200',    'Rosario', 'Santa Fe',
     '0341-4613003', 'logistica@hiprio.com',  'Carlos Bianchi',
     (SELECT id_ruta FROM rutas WHERE nombre_ruta='Zona Norte' LIMIT 1),
     (SELECT id_transporte FROM transportes WHERE codigo='TRA-001' LIMIT 1), 1),

    -- Zona Sur
    ('CLI-004', 'Distribuidora del Sur S.R.L.',
     '30614000004', 'Ruta 9 Km 3, Local 2',  'Funes',   'Santa Fe',
     '0341-4614004', 'ventas@dissur.com',     'Roberto Gómez',
     (SELECT id_ruta FROM rutas WHERE nombre_ruta='Zona Sur' LIMIT 1),
     (SELECT id_transporte FROM transportes WHERE codigo='TRA-002' LIMIT 1), 1),

    ('CLI-005', 'Farmacia San Martín',
     '20615000005', 'San Martín 200',         'Roldán',  'Santa Fe',
     '03465-415005', 'farmsanmartin@gmail.com','Andrea López',
     (SELECT id_ruta FROM rutas WHERE nombre_ruta='Zona Sur' LIMIT 1),
     (SELECT id_transporte FROM transportes WHERE codigo='TRA-002' LIMIT 1), 1),

    ('CLI-006', 'Almacén La Esquina',
     '20616000006', 'Belgrano 88',            'Soldini',  'Santa Fe',
     '03465-416006', 'laesquina@outlook.com', 'Jorge Ibañez',
     (SELECT id_ruta FROM rutas WHERE nombre_ruta='Zona Sur' LIMIT 1),
     (SELECT id_transporte FROM transportes WHERE codigo='TRA-002' LIMIT 1), 1),

    -- Zona Centro
    ('CLI-007', 'Farmacia Central S.R.L.',
     '30617000007', 'Córdoba 1050',           'Rosario', 'Santa Fe',
     '0341-4617007', 'farmcentral@farma.com', 'Silvia Torres',
     (SELECT id_ruta FROM rutas WHERE nombre_ruta='Zona Centro' LIMIT 1),
     (SELECT id_transporte FROM transportes WHERE codigo='TRA-003' LIMIT 1), 1),

    ('CLI-008', 'Drugstore City',
     '30618000008', 'Entre Ríos 755',         'Rosario', 'Santa Fe',
     '0341-4618008', 'city@drugstore.com',    'Nicolás Vera',
     (SELECT id_ruta FROM rutas WHERE nombre_ruta='Zona Centro' LIMIT 1),
     (SELECT id_transporte FROM transportes WHERE codigo='TRA-003' LIMIT 1), 1),

    ('CLI-009', 'Kiosco & Bazar Don Pedro',
     '20619000009', 'Maipú 320 Local 4',      'Rosario', 'Santa Fe',
     '0341-4619009', 'donpedro@gmail.com',    'Pedro Ramírez',
     (SELECT id_ruta FROM rutas WHERE nombre_ruta='Zona Centro' LIMIT 1),
     (SELECT id_transporte FROM transportes WHERE codigo='TRA-003' LIMIT 1), 1),

    ('CLI-010', 'Mayorista El Depósito S.A.',
     '30620000010', 'Av. Ovidio Lagos 3100',  'Rosario', 'Santa Fe',
     '0341-4620010', 'compras@eldepositosa.com','Fernando Acosta',
     (SELECT id_ruta FROM rutas WHERE nombre_ruta='Zona Norte' LIMIT 1),
     (SELECT id_transporte FROM transportes WHERE codigo='TRA-001' LIMIT 1), 1)

ON DUPLICATE KEY UPDATE razonsocial = VALUES(razonsocial), activo = VALUES(activo);


-- ============================================================
-- 6. MATERIAL ↔ PROVEEDOR
--    Cada proveedor tiene sus materiales principales
--    + PROV-006 (Importadora General) tiene materiales cruzados
-- ============================================================

-- Limpiar relaciones anteriores para re-insertar limpio
DELETE FROM material_proveedor
WHERE id_proveedor IN (
    SELECT id FROM proveedores WHERE codigo IN
        ('PROV-001','PROV-002','PROV-003','PROV-004','PROV-005','PROV-006')
);

-- PROV-001: Alimentos del Sur → Arroz y Aceite
INSERT INTO material_proveedor (id_material, id_proveedor, codigo_referencia_prov)
SELECT m.id, p.id, ref.cod_ref
FROM (SELECT 'MAT-001' AS cod_mat, 'ADS-ARR-001' AS cod_ref UNION ALL
      SELECT 'MAT-002',            'ADS-ACE-900') AS ref
JOIN materiales  m ON m.codigo = ref.cod_mat
JOIN proveedores p ON p.codigo = 'PROV-001';

-- PROV-002: Limpieza Hogar → Detergente y Lavandina
INSERT INTO material_proveedor (id_material, id_proveedor, codigo_referencia_prov)
SELECT m.id, p.id, ref.cod_ref
FROM (SELECT 'MAT-003' AS cod_mat, 'LH-DET-1KG' AS cod_ref UNION ALL
      SELECT 'MAT-004',            'LH-LAV-1LT') AS ref
JOIN materiales  m ON m.codigo = ref.cod_mat
JOIN proveedores p ON p.codigo = 'PROV-002';

-- PROV-003: Lab. Farmacéuticos → Ibuprofeno y Paracetamol
INSERT INTO material_proveedor (id_material, id_proveedor, codigo_referencia_prov)
SELECT m.id, p.id, ref.cod_ref
FROM (SELECT 'MAT-005' AS cod_mat, 'LFN-IBU-400' AS cod_ref UNION ALL
      SELECT 'MAT-006',            'LFN-PAR-500') AS ref
JOIN materiales  m ON m.codigo = ref.cod_mat
JOIN proveedores p ON p.codigo = 'PROV-003';

-- PROV-004: Tech Supplies → Cable USB-C
INSERT INTO material_proveedor (id_material, id_proveedor, codigo_referencia_prov)
SELECT m.id, p.id, 'TSA-USBC-1M'
FROM materiales  m
JOIN proveedores p ON p.codigo = 'PROV-004'
WHERE m.codigo = 'MAT-007';

-- PROV-005: Envases Plásticos → Bolsas
INSERT INTO material_proveedor (id_material, id_proveedor, codigo_referencia_prov)
SELECT m.id, p.id, 'EP-BOL-5070'
FROM materiales  m
JOIN proveedores p ON p.codigo = 'PROV-005'
WHERE m.codigo = 'MAT-008';

-- PROV-006: Importadora General → proveedor alternativo de varios materiales
INSERT INTO material_proveedor (id_material, id_proveedor, codigo_referencia_prov)
SELECT m.id, p.id, ref.cod_ref
FROM (SELECT 'MAT-001' AS cod_mat, 'IMP-ARR-A1'  AS cod_ref UNION ALL
      SELECT 'MAT-002',            'IMP-ACE-G9'           UNION ALL
      SELECT 'MAT-003',            'IMP-DET-P1'           UNION ALL
      SELECT 'MAT-007',            'IMP-USB-C1'           UNION ALL
      SELECT 'MAT-008',            'IMP-BOL-XL') AS ref
JOIN materiales  m ON m.codigo = ref.cod_mat
JOIN proveedores p ON p.codigo = 'PROV-006';

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- VERIFICACIÓN
-- ============================================================
SELECT 'Proveedores'      AS tabla, COUNT(*) AS total FROM proveedores    UNION ALL
SELECT 'Clientes'         AS tabla, COUNT(*) AS total FROM clientes        UNION ALL
SELECT 'Rutas'            AS tabla, COUNT(*) AS total FROM rutas           UNION ALL
SELECT 'Transportes'      AS tabla, COUNT(*) AS total FROM transportes     UNION ALL
SELECT 'Material-Prov'    AS tabla, COUNT(*) AS total FROM material_proveedor;
