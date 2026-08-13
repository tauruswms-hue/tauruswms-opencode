# -*- coding: utf-8 -*-
"""Tests de seguridad de Fase 1: CSRF, rate limiting, sesión y secretos."""

import datetime

import pytest

import app as wms
import admin as adm
from app import _check_secretos as wms_check_secretos
from admin import _check_secretos as adm_check_secretos


# --------------------------------------------------------------------------
# CSRF
# --------------------------------------------------------------------------
def test_csrf_post_sin_token_rechazado(client):
    """Con CSRF activo, un POST sin token debe ser rechazado (400)."""
    wms.app.config['WTF_CSRF_ENABLED'] = True
    resp = client.post('/login', data={'username': 'x', 'password': 'y'})
    assert resp.status_code == 400


def test_csrf_post_con_token_aceptado(client):
    """Con CSRF activo, un POST con token válido no debe ser rechazado."""
    import re
    wms.app.config['WTF_CSRF_ENABLED'] = True
    html = client.get('/login').get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    resp = client.post('/login', data={
        'username': 'x', 'password': 'y', 'csrf_token': token,
    })
    assert resp.status_code == 200  # credenciales inválidas, pero no CSRF


def test_csrf_header_en_login_admin(admin_client):
    """El login del admin también exige CSRF."""
    adm.app.config['WTF_CSRF_ENABLED'] = True
    resp = admin_client.post('/admin/login', data={
        'username': 'x', 'password': 'y',
    })
    assert resp.status_code == 400


# --------------------------------------------------------------------------
# Rate limiting en login
# --------------------------------------------------------------------------
def test_rate_limit_login_bloquea_tras_5(client):
    """6 intentos POST a /login deben dejar el 6to en 429."""
    wms.app.config['RATELIMIT_ENABLED'] = True
    wms.limiter.reset()
    for _ in range(5):
        r = client.post('/login', data={'username': 'x', 'password': 'y'})
        assert r.status_code != 429
    resp = client.post('/login', data={'username': 'x', 'password': 'y'})
    assert resp.status_code == 429
    wms.limiter.reset()


def test_rate_limit_admin_login_bloquea_tras_5(admin_client):
    adm.app.config['RATELIMIT_ENABLED'] = True
    from modules.admin import admin_limiter
    admin_limiter.reset()
    for _ in range(5):
        r = admin_client.post('/admin/login', data={'username': 'x', 'password': 'y'})
        assert r.status_code != 429
    resp = admin_client.post('/admin/login', data={'username': 'x', 'password': 'y'})
    assert resp.status_code == 429
    admin_limiter.reset()


# --------------------------------------------------------------------------
# Hardening de sesión
# --------------------------------------------------------------------------
def test_config_sesion_hardened():
    assert wms.app.config['SESSION_COOKIE_HTTPONLY'] is True
    assert wms.app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'
    assert wms.app.config['PERMANENT_SESSION_LIFETIME'] == datetime.timedelta(hours=8)
    assert adm.app.config['SESSION_COOKIE_HTTPONLY'] is True
    assert adm.app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'
    assert adm.app.config['PERMANENT_SESSION_LIFETIME'] == datetime.timedelta(hours=8)


def test_login_sesion_permanente(logged_client):
    """Tras login, la sesión debe marcarse como permanente (vida 8h)."""
    with logged_client.session_transaction() as sess:
        assert sess.permanent is True


def test_cookie_http_only_y_samesite(client):
    """La cookie de sesión debe salir con HttpOnly y SameSite=Lax."""
    resp = client.post('/login', data={
        'username': 'operador', 'password': 'Admin@2024!',
    })
    set_cookie = resp.headers.get('Set-Cookie', '')
    assert 'HttpOnly' in set_cookie
    assert 'SameSite=Lax' in set_cookie


# --------------------------------------------------------------------------
# Secretos por defecto
# --------------------------------------------------------------------------
def test_check_secretos_lanza_en_production(monkeypatch):
    """En producción, secretos por defecto deben bloquear el arranque."""
    monkeypatch.setattr(wms, 'APP_ENV', 'production')
    monkeypatch.setattr('app.os.getenv', lambda k, d='': {
        'SECRET_KEY': 'taurus-wms-secret-2024-dev',
        'ADMIN_SECRET_KEY': 'x', 'SECRET_SALT': 'x',
        'DB_ADMIN_PASSWORD': 'x', 'DB_PASSWORD': 'x',
        'DB_INTERCAMBIO_PASSWORD': 'x',
    }.get(k, d))
    with pytest.raises(RuntimeError):
        wms_check_secretos()


def test_check_secretos_ok_en_dev(monkeypatch):
    """En desarrollo no debe lanzar, solo advertir."""
    monkeypatch.setattr(wms, 'APP_ENV', 'development')
    wms_check_secretos()  # no debe lanzar


def test_admin_check_secretos_lanza_en_production(monkeypatch):
    monkeypatch.setattr(adm, 'APP_ENV', 'production')
    monkeypatch.setattr('admin.os.getenv', lambda k, d='': {
        'ADMIN_SECRET_KEY': 'taurus-admin-secret-2024-dev',
        'SECRET_KEY': 'x', 'SECRET_SALT': 'x',
        'DB_ADMIN_PASSWORD': 'x',
    }.get(k, d))
    with pytest.raises(RuntimeError):
        adm_check_secretos()


# --------------------------------------------------------------------------
# SQL injection: placeholders en queries
# --------------------------------------------------------------------------
def test_sql_placeholders_en_pedidos():
    """Los queries de pedidos usan %s, no interpolan strings de request."""
    from modules.pedidos import pedidos_bp
    import re
    source = __import__('modules.pedidos', fromlist=['x']).__file__
    with open(source, encoding='utf-8') as f:
        content = f.read()
    # no debe haber f-strings con request.form/args dentro de execute
    patrones_prohibidos = re.findall(
        r'f["\'][^"\']*\{[^}]*request\.(?:form|args|json|values)',
        content)
    assert patrones_prohibidos == []
