-- ============================================================
-- Migración: agrega campo UsuarioUltimoMov a stockcontable
-- ============================================================

ALTER TABLE stockcontable
    ADD COLUMN UsuarioUltimoMov VARCHAR(100) NULL
        COMMENT 'Usuario que realizó el último movimiento'
        AFTER UltimoMovimiento;
