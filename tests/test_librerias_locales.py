"""Las pantallas no cargan nada de internet: las librerías están copiadas en static/vendor."""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLAS = sorted((RAIZ / 'templates').rglob('*.html'))

EXTERNO = re.compile(r"""<(?:script|link)\b[^>]*\b(?:src|href)=["'](?:https?:)?//[^"']+""", re.IGNORECASE)
LOCAL = re.compile(r"""url_for\('static',\s*filename='(vendor/[^']+)'\)""")


def test_las_plantillas_no_cargan_librerias_de_internet():
    externas = [f'{p.relative_to(RAIZ)}: {m.group(0)}' for p in PLANTILLAS
                for m in EXTERNO.finditer(p.read_text(encoding='utf-8'))]
    assert externas == []


def test_las_librerias_referenciadas_existen():
    referencias = {m.group(1) for p in PLANTILLAS for m in LOCAL.finditer(p.read_text(encoding='utf-8'))}
    assert referencias                                             # si queda vacío, el patrón dejó de encontrar
    assert [r for r in sorted(referencias) if not (RAIZ / 'static' / r).is_file()] == []


def test_font_awesome_tiene_sus_fuentes():
    vendor = RAIZ / 'static' / 'vendor' / 'fontawesome'
    fuentes = set(re.findall(r'url\(\.\./webfonts/([^)]+)\)', (vendor / 'css' / 'all.min.css').read_text(encoding='utf-8')))
    assert fuentes
    assert [f for f in sorted(fuentes) if not (vendor / 'webfonts' / f).is_file()] == []
