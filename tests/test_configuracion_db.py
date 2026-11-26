"""Humo de /configuracion-db: era un 500 por un endpoint mal escrito."""

from conftest import requires_db


@requires_db
def test_configuracion_db_renderiza_con_usuario_autenticado(logged_client):
    respuesta = logged_client.get('/configuracion-db')

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert 'Configuración de Base de Datos' in html
    # El enlace del sidebar interno debe apuntar al endpoint del blueprint.
    assert 'href="/parametros"' in html
