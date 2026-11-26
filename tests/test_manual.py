"""El manual online es una guía operativa, separada de la documentación interna."""

import importlib.util
import re
from pathlib import Path

from conftest import requires_db

from modules.navegacion import construir_navegacion

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / 'manual'
INDICE = MANUAL / 'assets' / 'buscador-indice.js'

# Palabras que delatan documentación de desarrollo filtrada al usuario final.
TECNICO = re.compile(
    r'app\.py|admin\.py|schema_app\.py|modules/|ROUTE_CATALOG|blueprint|Flask|'
    r'pytest|ruff|Docker|MySQL|PostgreSQL|SQL Server|SQLite|conexiones\.json|\.env|'
    r'\btenant\b|stockcontable|stock_movimientos|pedidos_cabecera|pedidos_detalle|'
    r'recepciones_cabecera|omc_contenedores|intercambio_[a-z]|/api/',
    re.I,
)


def _generador():
    especificacion = importlib.util.spec_from_file_location('generar_indice', MANUAL / 'generar_indice.py')
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def test_manual_esta_en_el_modelo_del_menu_y_se_puede_buscar():
    nav = construir_navegacion(lambda _ruta: True, '/manual', {})
    items = {item['clave']: item for seccion in nav['secciones'] for item in seccion['items']}

    manual = items['manual']
    assert manual['ruta'] == '/manual'
    assert manual['endpoint'] == 'manual'
    assert manual['activo']  # el submenú se abre mientras se lee el manual
    assert 'ayuda' in manual['buscar'] and 'manual' in manual['buscar']


def test_manual_requiere_iniciar_sesion(client):
    respuesta = client.get('/manual')

    assert respuesta.status_code == 302
    assert '/login' in respuesta.headers['Location']


@requires_db
def test_manual_se_sirve_dentro_de_la_app_y_esta_en_la_barra_lateral(logged_client):
    respuesta = logged_client.get('/manual')
    assert respuesta.status_code == 302
    assert respuesta.headers['Location'].endswith('/manual/index.html')

    pagina = logged_client.get('/manual/index.html')
    assert pagina.status_code == 200
    html = pagina.get_data(as_text=True)
    assert 'Manual de usuario' in html
    assert 'Guía práctica' in html
    assert logged_client.get('/manual/assets/docs.js').status_code == 200
    assert logged_client.get('/manual/assets/docs.css').status_code == 200

    inicio = logged_client.get('/').get_data(as_text=True)
    assert 'Manual de usuario' in inicio
    assert 'href="/manual"' in inicio


@requires_db
def test_manual_no_expone_la_documentacion_interna(logged_client):
    for ruta in (
        '/manual/../docs/index.html',
        '/manual/../docs/arquitectura/vision-general.html',
        '/manual/generar_indice.py',
        '/manual/../requirements.txt',
    ):
        assert logged_client.get(ruta).status_code == 404, ruta


def test_indice_del_buscador_del_manual_al_dia():
    actual = INDICE.read_text(encoding='utf-8')
    assert actual == _generador().construir(), 'manual/assets/buscador-indice.js está desactualizado'


def test_assets_servidos_no_mencionan_la_documentacion_interna():
    for ruta in (MANUAL / 'assets' / 'docs.js', INDICE, MANUAL / 'assets' / 'docs.css'):
        texto = ruta.read_text(encoding='utf-8')
        assert 'docs/' not in texto, ruta.name
        assert not TECNICO.search(texto), ruta.name


def test_todas_las_paginas_del_manual_estan_en_el_indice_y_no_tienen_datos_tecnicos():
    nav = (MANUAL / 'assets' / 'docs.js').read_text(encoding='utf-8')
    hrefs = set(re.findall(r"href: '([^']+\.html)'", nav))
    paginas = {ruta.name for ruta in MANUAL.glob('*.html')}

    assert hrefs | {'index.html'} == paginas
    indice = INDICE.read_text(encoding='utf-8')
    fallos = []
    for ruta in sorted(MANUAL.glob('*.html')):
        if ruta.name not in indice:
            fallos.append(f'{ruta.name}: sin entradas en el índice')
        coincidencia = TECNICO.search(ruta.read_text(encoding='utf-8'))
        if coincidencia:
            fallos.append(f'{ruta.name}: {coincidencia.group(0)}')
    assert not fallos, '; '.join(fallos)
