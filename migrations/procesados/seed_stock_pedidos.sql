-- =============================================================================
-- SEED: Stock inicial para cubrir pedidos en estado Pendiente
-- =============================================================================
-- Materiales necesarios:
--   id=1  TOR-001  Tornillo Phillips 4x40mm   → 395 u pedidas
--   id=2  TOR-002  Tornillo Allen 6x50mm      → 420 u pedidas
--   id=3  TOR-003  Clavo 2" x18               → 535 u pedidas
--   id=4  TOR-004  Tarugo plástico 6mm        → 485 u pedidas
--   id=5  HER-001  Martillo 500g              → 445 u pedidas
--
-- Distribución (un contenedor por ubicación; cada material en 2 ubicaciones):
--
--   CONT-A101 @ A-01-01 (id=3):  TOR-001 (500 u), TOR-002 (250 u)
--   CONT-A102 @ A-01-02 (id=4):  TOR-002 (250 u), TOR-003 (300 u)
--   CONT-A201 @ A-02-01 (id=5):  TOR-003 (300 u), TOR-004 (300 u)
--   CONT-B101 @ B-01-01 (id=6):  TOR-004 (250 u), HER-001 (300 u)
--   CONT-B102 @ B-01-02 (id=7):  HER-001 (200 u), TOR-001 (150 u)
--
-- Stock disponible total por material:
--   TOR-001 → 650 u  (cubre 395 + holgura)
--   TOR-002 → 500 u  (cubre 420 + holgura)
--   TOR-003 → 600 u  (cubre 535 + holgura)
--   TOR-004 → 550 u  (cubre 485 + holgura)
--   HER-001 → 500 u  (cubre 445 + holgura)
-- =============================================================================

INSERT INTO stockcontable
    (Ubicacion, Material, IDContenedor, Lote, TipoStock,
     StockTotal, StockDisponible, StockEntrando, StockSaliendo,
     UltimoMovimiento, UsuarioUltimoMov)
VALUES
-- ── A-01-01 (id=3) · Contenedor CONT-A101 ──────────────────────────────────
(3, 1, 'CONT-A101', 'UNICO', 'Libre Venta', 500.0000, 500.0000, 0.0000, 0.0000, NOW(), 'seed'),   -- TOR-001
(3, 2, 'CONT-A101', 'UNICO', 'Libre Venta', 250.0000, 250.0000, 0.0000, 0.0000, NOW(), 'seed'),   -- TOR-002

-- ── A-01-02 (id=4) · Contenedor CONT-A102 ──────────────────────────────────
(4, 2, 'CONT-A102', 'UNICO', 'Libre Venta', 250.0000, 250.0000, 0.0000, 0.0000, NOW(), 'seed'),   -- TOR-002
(4, 3, 'CONT-A102', 'UNICO', 'Libre Venta', 300.0000, 300.0000, 0.0000, 0.0000, NOW(), 'seed'),   -- TOR-003

-- ── A-02-01 (id=5) · Contenedor CONT-A201 ──────────────────────────────────
(5, 3, 'CONT-A201', 'UNICO', 'Libre Venta', 300.0000, 300.0000, 0.0000, 0.0000, NOW(), 'seed'),   -- TOR-003
(5, 4, 'CONT-A201', 'UNICO', 'Libre Venta', 300.0000, 300.0000, 0.0000, 0.0000, NOW(), 'seed'),   -- TOR-004

-- ── B-01-01 (id=6) · Contenedor CONT-B101 ──────────────────────────────────
(6, 4, 'CONT-B101', 'UNICO', 'Libre Venta', 250.0000, 250.0000, 0.0000, 0.0000, NOW(), 'seed'),   -- TOR-004
(6, 5, 'CONT-B101', 'UNICO', 'Libre Venta', 300.0000, 300.0000, 0.0000, 0.0000, NOW(), 'seed'),   -- HER-001

-- ── B-01-02 (id=7) · Contenedor CONT-B102 ──────────────────────────────────
(7, 5, 'CONT-B102', 'UNICO', 'Libre Venta', 200.0000, 200.0000, 0.0000, 0.0000, NOW(), 'seed'),   -- HER-001
(7, 1, 'CONT-B102', 'UNICO', 'Libre Venta', 150.0000, 150.0000, 0.0000, 0.0000, NOW(), 'seed');   -- TOR-001

-- =============================================================================
-- Verificación rápida (descomentar para revisar antes de aplicar):
-- =============================================================================
-- SELECT m.codigo, m.nombre,
--        SUM(sc.StockDisponible) AS disponible,
--        (SELECT SUM(d.cantidad)
--         FROM pedidos_detalle d
--         JOIN pedidos_cabecera pc ON pc.id_pedido = d.id_pedido
--         WHERE d.id_material = m.id AND pc.estado = 'Pendiente') AS pedido
-- FROM stockcontable sc
-- JOIN materiales m ON m.id = sc.Material
-- WHERE sc.Material IN (1,2,3,4,5)
-- GROUP BY m.id, m.codigo, m.nombre
-- ORDER BY m.id;
