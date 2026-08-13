# -*- coding: utf-8 -*-
"""Tests de la lógica de permisos por ruta (app.py: _match_permiso, etc.)."""

import pytest

from app import _match_permiso, _ruta_en_catalogo


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
