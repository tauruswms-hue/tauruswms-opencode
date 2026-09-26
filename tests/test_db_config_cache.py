"""Cache de configuración con TTL: refleja cambios hechos desde otro proceso."""

import pytest

from modules import db_config


@pytest.fixture
def cache_limpia():
    db_config.clear_config_cache()
    yield
    db_config.clear_config_cache()


def _config(host):
    return {'DB_HOST': host, 'DB_PORT': '3306', 'DB_NAME': 'wms', 'DB_USER': 'u',
            'DB_PASSWORD': 'p', 'DB_ENGINE': 'mysql'}


def test_config_se_cachea_dentro_del_ttl(monkeypatch, cache_limpia):
    lecturas = []
    monkeypatch.setattr(db_config, '_leer_db_config', lambda: lecturas.append(1) or _config('a'))
    db_config.get_db_config()
    db_config.get_db_config()
    assert len(lecturas) == 1


def test_config_se_relee_al_expirar_y_resetea_pools(monkeypatch, cache_limpia):
    valores = iter([_config('a'), _config('b')])
    monkeypatch.setattr(db_config, '_leer_db_config', lambda: next(valores))
    assert db_config.get_db_config()['DB_HOST'] == 'a'

    cerrados = []
    monkeypatch.setitem(db_config._pools, ('mysql', 'x'), type('P', (), {'close': lambda self: cerrados.append(1)})())
    monkeypatch.setattr(db_config, 'CONFIG_CACHE_TTL', 0)

    assert db_config.get_db_config()['DB_HOST'] == 'b'
    assert cerrados == [1]
    assert db_config._pools == {}


def test_config_mantiene_cache_si_falla_el_refresco(monkeypatch, cache_limpia):
    monkeypatch.setattr(db_config, '_leer_db_config', lambda: _config('a'))
    db_config.get_db_config()

    def falla():
        raise RuntimeError('admin caída')
    monkeypatch.setattr(db_config, '_leer_db_config', falla)
    monkeypatch.setattr(db_config, 'CONFIG_CACHE_TTL', 0)
    assert db_config.get_db_config()['DB_HOST'] == 'a'
