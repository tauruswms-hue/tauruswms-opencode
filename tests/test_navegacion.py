"""Tests del modelo de navegación lateral (sin BD ni request real)."""

from flask import url_for

from modules.navegacion import (
    ITEMS_POR_RUTA,
    MAX_FAVORITOS,
    NAVEGACION,
    construir_navegacion,
    es_activo,
    normalizar_preferencias,
)


def _todo_permitido(_ruta):
    return True


def test_cada_destino_aparece_una_sola_vez():
    rutas = [item['ruta'] for seccion in NAVEGACION for item in seccion['items']]
    assert len(rutas) == len(set(rutas))


def test_todos_los_endpoints_del_menu_existen():
    from app import app

    with app.test_request_context('/'):
        for item in ITEMS_POR_RUTA.values():
            assert url_for(item['endpoint']) == item['ruta']


def test_filtrado_por_permisos_oculta_secciones_completas():
    permitir = lambda ruta: ruta == '/materiales'
    nav = construir_navegacion(permitir, '/materiales', {})

    claves = [seccion['clave'] for seccion in nav['secciones']]
    assert claves == ['favoritos', 'maestros']
    assert [item['ruta'] for item in nav['secciones'][1]['items']] == ['/materiales']


def test_item_activo_expande_su_seccion_aunque_este_cerrada():
    nav = construir_navegacion(
        _todo_permitido,
        '/pedidos/nuevo',
        {'operaciones': False},
    )

    operaciones = next(s for s in nav['secciones'] if s['clave'] == 'operaciones')
    assert operaciones['expandida'] is True
    assert [i['etiqueta'] for i in operaciones['items'] if i['activo']] == ['Pedidos']


def test_es_activo_reconoce_subrutas_pero_no_otras_rutas():
    assert es_activo('/pedidos/ver/3', '/pedidos')
    assert not es_activo('/pedidos-especiales', '/pedidos')
    assert not es_activo('/', '/materiales')


def test_preferencias_históricas_se_migran():
    prefs = normalizar_preferencias(
        '{"consultas": true, "rapido": true, "_modo": "rail"}'
    )
    assert prefs['sistema'] is True
    assert prefs['operaciones'] is True
    assert prefs['_modo'] == 'rail'
    assert prefs['_favoritos'] == []


def test_preferencias_corruptas_no_rompen_el_menu():
    assert normalizar_preferencias('no es json') == {
        '_modo': 'expandido',
        '_favoritos': [],
    }
    assert normalizar_preferencias(None)['_modo'] == 'expandido'


def test_favoritos_se_filtran_por_permiso_y_se_limitan():
    nav = construir_navegacion(
        lambda ruta: ruta == '/pedidos',
        '/pedidos',
        {'_favoritos': ['/pedidos', '/reportes', '/no-existe']},
    )
    assert nav['favoritos_paths'] == ('/pedidos',)
    assert [item['ruta'] for item in nav['favoritos']] == ['/pedidos']

    exceso = list(ITEMS_POR_RUTA)[: MAX_FAVORITOS + 4]
    prefs = normalizar_preferencias({'_favoritos': exceso})
    assert len(prefs['_favoritos']) == MAX_FAVORITOS


def test_la_busqueda_incluye_sinonimos_del_negocio():
    nav = construir_navegacion(_todo_permitido, '/stockcontable', {})

    items = {item['clave']: item for seccion in nav['secciones'] for item in seccion['items']}
    assert 'existencias' in items['stock']['buscar']
    assert 'orden' in items['pedidos']['buscar']
    assert 'transferencias' in items['omc']['buscar']
    assert items['stock']['buscar'].startswith('Stock')


def test_cada_seccion_expone_su_total_de_destinos():
    nav = construir_navegacion(_todo_permitido, '/materiales', {})

    secciones = {seccion['clave']: seccion for seccion in nav['secciones']}
    assert secciones['maestros']['total'] == len(secciones['maestros']['items']) == 4
    assert secciones['favoritos']['total'] == 0
