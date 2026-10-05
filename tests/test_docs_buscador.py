"""Buscador de la documentación: el índice versionado tiene que estar al día."""

import importlib.util
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / 'docs'


def _generador():
    spec = importlib.util.spec_from_file_location('generar_buscador', DOCS / 'generar_buscador.py')
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_indice_del_buscador_al_dia():
    """Si falla: correr `python docs/generar_buscador.py` y commitear el resultado."""
    actual = (DOCS / 'assets' / 'buscador-indice.js').read_text(encoding='utf-8')
    assert actual == _generador().construir(), 'docs/assets/buscador-indice.js está desactualizado'


def test_slug_de_encabezados():
    slug = _generador().slug
    assert slug('Cómo se lee un registro') == 'como-se-lee-un-registro'
    assert slug('Órdenes de movimiento (OMC)') == 'ordenes-de-movimiento-omc'
    assert slug('  ¿Qué?  ') == 'que'
    assert slug('---') == 'seccion'


def test_anclas_unicas_por_pagina():
    gen = _generador()
    for ruta in DOCS.rglob('*.html'):
        if ruta.name in gen.EXCLUIR:
            continue
        anclas = [e['a'] for e in gen.entradas_de(ruta) if e['a']]
        assert len(anclas) == len(set(anclas)), f'anclas repetidas en {ruta.name}'
