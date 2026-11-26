"""Guardarails de la experiencia de usuario compartida.

Cubren los puntos que se degradaban sin que nadie visitara la pantalla:
etiquetas de login, notificaciones de error persistentes, foco/modal y tablas.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIN_SCOPE = re.compile(r"<th\b(?![^>]*\bscope=)[^>]*>", re.I)


def leer(relativo):
    return (ROOT / relativo).read_text(encoding='utf-8')


def test_login_wms_tiene_campos_nombrados_y_clave_visible_persistente(client):
    html = client.get('/login').get_data(as_text=True)

    assert 'for="usuario"' in html and 'id="usuario"' in html
    assert 'for="password"' in html and 'id="password"' in html
    assert 'aria-pressed="false"' in html
    # Antes la clave se ocultaba sola a los 3 s y los avisos desaparecían.
    assert 'setTimeout' not in html


def test_login_admin_tiene_las_mismas_ayudas(client):
    from admin import app as admin_app

    admin_app.config.update(TESTING=True)
    with admin_app.test_client() as admin_client:
        html = admin_client.get('/admin/login').get_data(as_text=True)

    assert 'for="usuario-admin"' in html and 'id="usuario-admin"' in html
    assert 'aria-pressed="false"' in html
    assert 'setTimeout' not in html


def test_errores_de_login_son_visibles_y_no_se_ocultan_solos(client):
    with client.session_transaction() as sesion:
        sesion['_flashes'] = [('danger', 'Usuario o contraseña incorrectos')]

    html = client.get('/login').get_data(as_text=True)
    assert 'Usuario o contraseña incorrectos' in html
    assert 'alert-danger' in html
    assert 'role="alert"' in html


def test_base_carga_el_componente_de_ui_y_las_notificaciones_accesibles():
    base = leer('templates/base.html')
    assert 'js/ui.js' in base
    assert "from 'partials/_flashes.html' import flashes" in base
    plantilla = leer('templates/partials/_flashes.html')
    assert 'aria-live="polite"' in plantilla
    assert 'role="status"' in plantilla and 'role="alert"' in plantilla


def test_movil_permite_zoom_y_anuncia_los_avisos():
    movil = leer('templates/movil_base.html')
    assert 'user-scalable=no' not in movil
    assert 'maximum-scale' not in movil
    assert 'aria-live="polite"' in movil
    assert 'movil-flash-error' in movil
    assert 'js/ui.js' in movil


def test_todas_las_cabeceras_de_tabla_tienen_scope():
    fallos = []
    for plantilla in (ROOT / 'templates').rglob('*.html'):
        for coincidencia in SIN_SCOPE.finditer(plantilla.read_text(encoding='utf-8')):
            fallos.append(f'{plantilla.name}: {coincidencia.group(0)[:60]}')
    assert not fallos, 'Cabeceras sin scope: ' + ', '.join(fallos[:10])


def test_estilos_tienen_alias_de_error_y_escala_de_capas():
    css = leer('static/css/style.css')
    assert '.flash-danger' in css
    assert '--z-modal' in css and '--z-toast' in css
    assert '.modal-overlay {' in css
