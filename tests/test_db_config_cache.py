"""Archivo de conexiones: validación y caché con TTL (refleja cambios sin reiniciar)."""

import json

import pytest

from modules import db_config


@pytest.fixture
def cache_limpia(monkeypatch):
    monkeypatch.setattr(db_config, '_conexiones_fijas', {})
    db_config.clear_config_cache()
    yield
    db_config.clear_config_cache()


def _conexion(host='a', **extra):
    return {'engine': 'mysql', 'host': host, 'port': 3306, 'user': 'u', 'password': 'p',
            'database': 'wms', **extra}


def _conexiones(host):
    return {b: db_config.normalizar_conexion(b, _conexion(host), 'test') for b in ('admin', 'wms')}


@pytest.fixture
def archivo(tmp_path, monkeypatch, cache_limpia):
    """Escribe un conexiones.json temporal y hace que db_config lo use."""
    ruta = tmp_path / 'conexiones.json'
    monkeypatch.setenv(db_config.CONEXIONES_ENV, str(ruta))

    def escribir(datos):
        ruta.write_text(datos if isinstance(datos, str) else json.dumps(datos), encoding='utf-8')
        return ruta
    return escribir


# --- Caché ---

def test_conexiones_se_cachean_dentro_del_ttl(monkeypatch, cache_limpia):
    lecturas = []
    monkeypatch.setattr(db_config, '_leer_conexiones', lambda: lecturas.append(1) or _conexiones('a'))
    db_config.get_conexion('wms')
    db_config.get_conexion('admin')
    assert len(lecturas) == 1


def test_conexiones_se_releen_al_expirar_y_resetean_pools(monkeypatch, cache_limpia):
    valores = iter([_conexiones('a'), _conexiones('b')])
    monkeypatch.setattr(db_config, '_leer_conexiones', lambda: next(valores))
    assert db_config.get_conexion('wms')['host'] == 'a'

    cerrados = []
    monkeypatch.setitem(db_config._pools, ('mysql', 'x'), type('P', (), {'close': lambda self: cerrados.append(1)})())
    monkeypatch.setattr(db_config, 'CONFIG_CACHE_TTL', 0)

    assert db_config.get_conexion('wms')['host'] == 'b'
    assert cerrados == [1]
    assert db_config._pools == {}


def test_conexiones_mantienen_cache_si_falla_el_refresco(monkeypatch, cache_limpia):
    monkeypatch.setattr(db_config, '_leer_conexiones', lambda: _conexiones('a'))
    db_config.get_conexion('wms')

    def falla():
        raise db_config.ConexionesError('archivo ilegible')
    monkeypatch.setattr(db_config, '_leer_conexiones', falla)
    monkeypatch.setattr(db_config, 'CONFIG_CACHE_TTL', 0)
    assert db_config.get_conexion('wms')['host'] == 'a'


# --- Lectura y validación del archivo ---

def test_lee_las_tres_bases_y_completa_defaults(archivo):
    archivo({'admin': _conexion('h1'), 'wms': {**_conexion('h2'), 'port': None},
             'intercambio': _conexion('h3', engine='postgresql', port=None)})
    assert db_config.get_conexion('admin')['host'] == 'h1'
    assert db_config.get_conexion('wms') == {
        'engine': 'mysql', 'host': 'h2', 'port': 3306, 'user': 'u', 'password': 'p',
        'database': 'wms', 'charset': 'utf8mb4'}
    intercambio = db_config.get_conexion('intercambio')
    assert (intercambio['port'], intercambio['charset']) == (5432, 'UTF8')
    assert db_config.get_db_engine() == 'mysql'
    assert db_config.get_db_config()['DB_HOST'] == 'h2'


def test_intercambio_es_opcional_pero_se_avisa_al_pedirlo(archivo):
    archivo({'admin': _conexion(), 'wms': _conexion()})
    assert db_config.get_conexion('wms')['host'] == 'a'
    with pytest.raises(db_config.ConexionesError, match="falta la sección 'intercambio'"):
        db_config.get_conexion('intercambio')


@pytest.mark.parametrize('contenido, mensaje', [
    ('{no es json', 'no es un JSON válido'),
    ({'admin': _conexion()}, 'faltan las secciones: wms'),
    ({'admin': _conexion(), 'wms': _conexion(), 'otra': {}}, 'secciones desconocidas: otra'),
    ({'admin': _conexion(), 'wms': {**_conexion(), 'password': ''}}, "obligatorias en 'wms': password"),
    ({'admin': _conexion(), 'wms': _conexion(clave_rara=1)}, 'claves desconocidas'),
    ({'admin': _conexion(), 'wms': _conexion(engine='oracle')}, "engine 'oracle' no soportado"),
    ({'admin': _conexion(), 'wms': {**_conexion(), 'port': 'abc'}}, 'port debe ser numérico'),
])
def test_archivo_invalido_explica_el_problema(archivo, contenido, mensaje):
    archivo(contenido)
    with pytest.raises(db_config.ConexionesError, match=mensaje):
        db_config.get_conexion('wms')


def test_archivo_faltante_indica_que_crear(tmp_path, monkeypatch, cache_limpia):
    monkeypatch.setenv(db_config.CONEXIONES_ENV, str(tmp_path / 'no-existe.json'))
    with pytest.raises(db_config.ConexionesError, match='secciones admin, wms e intercambio'):
        db_config.get_conexion('admin')


def test_set_conexion_fija_una_base_sin_leer_el_archivo(tmp_path, monkeypatch, cache_limpia):
    """superusuario.exe trae sus credenciales de taurus_admin y no necesita conexiones.json."""
    monkeypatch.setenv(db_config.CONEXIONES_ENV, str(tmp_path / 'no-existe.json'))
    db_config.set_conexion('admin', _conexion('exe'), origen='superusuario.json')
    assert db_config.get_conexion('admin')['host'] == 'exe'


def test_passwords_bd_bloquea_production_sin_archivo(tmp_path, monkeypatch, cache_limpia):
    import logging

    from modules.bootstrap import passwords_bd
    monkeypatch.setenv(db_config.CONEXIONES_ENV, str(tmp_path / 'no-existe.json'))
    assert passwords_bd('development', logging.getLogger('test')) == []
    with pytest.raises(RuntimeError, match='No se encontró el archivo de conexiones'):
        passwords_bd('production', logging.getLogger('test'))
