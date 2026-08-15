"""Tests de la lógica de permisos por ruta (app.py: _match_permiso, etc.)."""

import pytest

from app import _match_permiso, _ruta_en_catalogo
from modules.permisos_cache import invalidar_permisos_cache, obtener_rutas_cached


@pytest.mark.parametrize('permiso,path,ruta,esperado', [
    # exacto
    ('/materiales', '/materiales', None, True),
    ('/materiales', '/materiales/guardar', None, False),
    # prefijo con /*
    ('/inventario/*', '/inventario', None, True),
    ('/inventario/*', '/inventario/crear', None, True),
    ('/inventario/*', '/inventario/crear/xyz', None, True),
    ('/inventario/*', '/inventario_otro', None, False),
    # parcial con * sin / (requiere el prefijo literal, incluido '_')
    ('/recepciones/buscar_*', '/recepciones/buscar_x', None, True),
    ('/recepciones/buscar_*', '/recepciones/buscar', None, False),
    ('/recepciones/buscar_*', '/recepciones/listar', None, False),
    # prefijo general con *
    ('/pedidos*', '/pedidos', None, True),
    ('/pedidos*', '/pedidos/eliminar', None, True),
    ('/pedidos*', '/otro', None, False),
    # endpoint (ruta) como segundo criterio: debe coincidir exacto
    ('/xyz', '/otra', 'mi_endpoint', False),
    ('/xyz', '/otra', 'xyz', False),
    ('xyz', '/otra', 'xyz', True),
    # acceso total
    ('*', '/cualquier', None, True),
])
def test_match_permiso(permiso, path, ruta, esperado):
    assert _match_permiso(permiso, path, ruta) is esperado


def test_ruta_en_catalogo_materiales():
    assert _ruta_en_catalogo('/materiales')


def test_ruta_en_catalogo_rutas_publicas_no_catalogadas():
    assert not _ruta_en_catalogo('/login')
    assert not _ruta_en_catalogo('/acerca')
    assert not _ruta_en_catalogo('/estado')


# --------------------------------------------------------------------------
# Cache de permisos por rol (FASE 2.7)
# --------------------------------------------------------------------------
def test_cache_usa_loader_una_sola_vez_dentro_del_ttl(monkeypatch):
    invalidar_permisos_cache()
    llamadas = []

    def loader():
        llamadas.append(1)
        return ['/materiales/*']

    from modules import permisos_cache
    ttl_original = permisos_cache.TTL
    permisos_cache.TTL = 1000.0
    try:
        r1 = obtener_rutas_cached('ROL-X', loader)
        r2 = obtener_rutas_cached('ROL-X', loader)
        assert r1 == ['/materiales/*']
        assert r2 == ['/materiales/*']
        assert len(llamadas) == 1
    finally:
        permisos_cache.TTL = ttl_original
        invalidar_permisos_cache()


def test_cache_invalida_despues_del_ttl(monkeypatch):
    invalidar_permisos_cache()
    valores = iter([['/a'], ['/b']])

    def loader():
        return next(valores)

    from modules import permisos_cache
    ttl_original = permisos_cache.TTL
    permisos_cache.TTL = 0.0
    try:
        assert obtener_rutas_cached('ROL-Y', loader) == ['/a']
        assert obtener_rutas_cached('ROL-Y', loader) == ['/b']
    finally:
        permisos_cache.TTL = ttl_original
        invalidar_permisos_cache()


def test_cache_roles_independientes():
    invalidar_permisos_cache()
    llamadas_a = []

    def loader_a():
        llamadas_a.append(1)
        return ['/a']

    assert obtener_rutas_cached('ROLA', loader_a) == ['/a']
    assert obtener_rutas_cached('ROLB', lambda: ['/b']) == ['/b']
    # ROL-A sigue cacheado, no se vuelve a consultar
    assert obtener_rutas_cached('ROLA', loader_a) == ['/a']
    assert len(llamadas_a) == 1
    invalidar_permisos_cache()


def test_invalidar_permisos_cache_limpia():
    invalidar_permisos_cache()
    llamadas = []

    def loader():
        llamadas.append(1)
        return ['/x']

    assert obtener_rutas_cached('ROLC', loader) == ['/x']
    invalidar_permisos_cache()
    assert obtener_rutas_cached('ROLC', loader) == ['/x']
    assert len(llamadas) == 2
