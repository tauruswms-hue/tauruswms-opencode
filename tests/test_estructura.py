"""Guardarails de estructura: endpoints y plantillas huérfanas.

Estos tests evitan que vuelva a pasar lo de /configuracion-db: una plantilla
con un endpoint inexistente sólo falla cuando alguien visita esa ruta.
"""

import re
from pathlib import Path

from admin import app as admin_app
from app import app as wms_app

ROOT = Path(__file__).resolve().parents[1]
PLANTILLAS = ROOT / 'templates'
ENDPOINT_LITERAL = re.compile(r"url_for\(\s*['\"]([A-Za-z_][A-Za-z0-9_.]*)['\"]")


def _archivos(carpeta, sufijo):
    return [
        ruta for ruta in carpeta.rglob(sufijo)
        if '.venv' not in ruta.parts and '__pycache__' not in ruta.parts
    ]


def test_todos_los_endpoints_literales_de_las_plantillas_existen():
    endpoints = set(wms_app.view_functions) | set(admin_app.view_functions)
    fallos = []

    for plantilla in _archivos(PLANTILLAS, '*.html'):
        texto = plantilla.read_text(encoding='utf-8')
        for endpoint in ENDPOINT_LITERAL.findall(texto):
            if endpoint not in endpoints:
                fallos.append(f'{plantilla.relative_to(ROOT)}: {endpoint}')

    assert not fallos, 'Endpoints inexistentes en plantillas: ' + ', '.join(fallos)


def test_no_hay_plantillas_huerfanas():
    archivos = _archivos(PLANTILLAS, '*.html')
    referencias = '\n'.join(
        ruta.read_text(encoding='utf-8', errors='ignore')
        for ruta in _archivos(ROOT, '*.py')
    )
    referencias += '\n' + '\n'.join(
        ruta.read_text(encoding='utf-8', errors='ignore') for ruta in archivos
    )

    huerfanas = [
        ruta.relative_to(ROOT).as_posix() for ruta in archivos
        if ruta.name not in referencias
    ]
    assert not huerfanas, 'Plantillas sin renderizar ni incluir: ' + ', '.join(huerfanas)
