"""superusuario.exe: limpieza de la auditoría del panel (scripts/admin_superusuario.py)."""

import json

import pytest

from scripts import admin_superusuario as su
from tests.conftest import requires_db

# Fechas muy anteriores a cualquier registro real: la limpieza del test no toca la auditoría existente
FECHA_VIEJA = '2000-01-01 10:00:00'
MARCA = 'test-limpieza-auditoria'


@pytest.fixture
def auditoria_vieja():
    """Inserta un registro de auditoría del año 2000 y lo borra al final si quedó."""
    from modules.db_config import _get_admin_connection
    conn = _get_admin_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO audit_logs (accion, modulo, detalle, created_at) VALUES ('ACCESS', 'tenants', %s, %s)",
                (MARCA, FECHA_VIEJA))
    conn.commit()
    yield conn
    cur.execute("DELETE FROM audit_logs WHERE detalle = %s", (MARCA,))
    conn.commit()
    conn.close()


def _responder(monkeypatch, respuestas):
    """Simula lo que se tipea en la consola, en orden."""
    it = iter(respuestas)
    monkeypatch.setattr('builtins.input', lambda prompt='': next(it))
    monkeypatch.setattr(su, 'limpiar_pantalla', lambda: None)


def _quedan(conn):
    conn.commit()  # refresca el snapshot de la transacción
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM audit_logs WHERE detalle = %s", (MARCA,))
    return cur.fetchone()['n']


@requires_db
def test_limpiar_auditoria_borra_hasta_la_fecha_y_lo_registra(monkeypatch, auditoria_vieja, usuario_panel):
    conn = auditoria_vieja
    # fecha, usuario, contraseña, confirmación
    _responder(monkeypatch, ['02/01/2000', usuario_panel['username'], usuario_panel['password'], 's'])
    su.limpiar_auditoria(conn, conn.cursor())

    assert _quedan(conn) == 0
    cur = conn.cursor()
    cur.execute("""
        SELECT a.usuario_nombre, a.detalle, a.user_agent FROM audit_logs a
        JOIN admin_usuarios u ON u.id = a.usuario_id
        WHERE u.username = %s AND a.accion = 'DELETE' AND a.modulo = 'audit'
    """, (usuario_panel['username'],))
    registro = cur.fetchone()
    assert registro, 'la limpieza no quedó registrada en la auditoría'
    detalle = json.loads(registro['detalle'])
    assert detalle['hasta'] == '02/01/2000' and detalle['eliminados'] >= 1
    assert detalle['username'] == usuario_panel['username']
    assert registro['user_agent'] == 'superusuario.exe'


@requires_db
@pytest.mark.parametrize('respuestas', [
    ['02/01/2000', '{usuario}', 'clave-incorrecta'],   # contraseña equivocada
    ['02/01/2000', 'no-existe', 'x'],                  # usuario inexistente
    ['02/01/2000', '{usuario}', '{password}', 'n'],    # no confirma
    ['31/02/2000'],                                    # fecha inválida
    ['01/01/2999'],                                    # fecha futura
])
def test_limpiar_auditoria_no_borra_sin_autorizacion(monkeypatch, auditoria_vieja, usuario_panel, respuestas):
    conn = auditoria_vieja
    _responder(monkeypatch, [r.format(usuario=usuario_panel['username'], password=usuario_panel['password'])
                             for r in respuestas])
    su.limpiar_auditoria(conn, conn.cursor())
    assert _quedan(conn) == 1


@requires_db
def test_limpiar_auditoria_exige_rol_superadmin(monkeypatch, auditoria_vieja, usuario_panel):
    conn = auditoria_vieja
    cur = conn.cursor()
    cur.execute("UPDATE admin_usuarios SET rol = 'ADMIN' WHERE username = %s", (usuario_panel['username'],))
    conn.commit()
    _responder(monkeypatch, ['02/01/2000', usuario_panel['username'], usuario_panel['password'], 's'])
    su.limpiar_auditoria(conn, cur)
    assert _quedan(conn) == 1
