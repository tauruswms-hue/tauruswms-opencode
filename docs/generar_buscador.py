"""
generar_buscador.py — Regenera el índice del buscador de la documentación.

Recorre las páginas HTML de docs/ y escribe docs/assets/buscador-indice.js con el
texto de cada página, partido por encabezado (h1, h2, h3). El buscador de
docs/assets/docs.js carga ese archivo y busca en él: como la documentación se abre
desde el disco, no puede leer las otras páginas en el momento.

Uso (desde cualquier directorio), después de crear o cambiar una página:
    python docs/generar_buscador.py

Si hay páginas generadas (scripts o diagramas de base de datos), regenerarlas antes:
    python docs/generar_scripts_bd.py
    python docs/generar_diagramas_bd.py
    python docs/generar_buscador.py

Cada resultado enlaza al encabezado donde está el texto. Los encabezados sin `id`
reciben uno derivado de su texto; docs.js calcula el mismo al abrir la página
(función `slug` en los dos archivos: si se cambia una, cambiar la otra).
"""
import json
import re
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

DOCS = Path(__file__).resolve().parent
DESTINO = DOCS / 'assets' / 'buscador-indice.js'
EXCLUIR = {'_plantilla.html'}
ENCABEZADOS = ('h1', 'h2', 'h3')
SIN_TEXTO = ('svg', 'script', 'style')


def slug(texto):
    """Identificador de un encabezado a partir de su texto (igual que `slug` en docs.js)."""
    s = re.sub('[̀-ͯ]', '', unicodedata.normalize('NFD', texto.lower()))
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-') or 'seccion'


class _Pagina(HTMLParser):
    """Extrae el texto de <main>, partido en tramos por encabezado."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.en_main = 0
        self.omitir = 0
        self.encabezado = None      # tramo cuyo encabezado se está leyendo
        self.tramos = []            # {'nivel', 'id', 'titulo', 'texto': [..]}

    def handle_starttag(self, tag, attrs):
        if tag == 'main':
            self.en_main += 1
        if not self.en_main:
            return
        if tag in SIN_TEXTO:
            self.omitir += 1
        elif tag in ENCABEZADOS and not self.omitir:
            self.encabezado = {'nivel': tag, 'id': dict(attrs).get('id') or '', 'titulo': [], 'texto': []}
            self.tramos.append(self.encabezado)

    def handle_endtag(self, tag):
        if tag == 'main':
            self.en_main -= 1
        elif tag in SIN_TEXTO and self.omitir:
            self.omitir -= 1
        elif tag in ENCABEZADOS:
            self.encabezado = None
        elif self.tramos and self.en_main and not self.omitir:
            self.tramos[-1]['texto'].append(' ')   # separa celdas, ítems y párrafos

    def handle_data(self, data):
        if not self.en_main or self.omitir:
            return
        if self.encabezado is not None:
            self.encabezado['titulo'].append(data)
        elif self.tramos:
            self.tramos[-1]['texto'].append(data)


def _limpio(partes):
    return re.sub(r'\s+', ' ', ''.join(partes)).strip()


def entradas_de(ruta):
    """Entradas del índice de una página: una por encabezado."""
    pagina = _Pagina()
    pagina.feed(ruta.read_text(encoding='utf-8'))
    href = ruta.relative_to(DOCS).as_posix()

    titulo = ''
    usados = {t['id'] for t in pagina.tramos if t['nivel'] != 'h1' and t['id']}
    entradas = []
    for t in pagina.tramos:
        encabezado = _limpio(t['titulo'])
        if t['nivel'] == 'h1':
            titulo, ancla, encabezado = encabezado, '', ''
        elif t['id']:
            ancla = t['id']
        else:
            # Mismo criterio que docs.js: texto del encabezado y, si se repite, un número
            ancla, n = slug(encabezado), 1
            while ancla in usados:
                n += 1
                ancla = f'{slug(encabezado)}-{n}'
            usados.add(ancla)
        entradas.append({'p': href, 't': titulo, 'h': encabezado, 'a': ancla, 'x': _limpio(t['texto'])})
    return entradas


def construir():
    """Contenido completo de buscador-indice.js."""
    entradas = []
    for ruta in sorted(DOCS.rglob('*.html'), key=lambda r: r.relative_to(DOCS).as_posix()):
        if ruta.name not in EXCLUIR:
            entradas += entradas_de(ruta)
    lineas = ',\n'.join(json.dumps(e, ensure_ascii=False, separators=(',', ':')) for e in entradas)
    return ('// Índice del buscador de la documentación. Generado por docs/generar_buscador.py: no editar a mano.\n'
            f'window.DOCS_INDICE = [\n{lineas}\n];\n')


def main():
    contenido = construir()
    DESTINO.write_text(contenido, encoding='utf-8', newline='\n')
    print(f"{DESTINO.relative_to(DOCS.parent)}: {contenido.count(chr(10)) - 3} entradas, "
          f"{len(contenido.encode('utf-8')) / 1024:.0f} KB")
    return 0


if __name__ == '__main__':
    sys.exit(main())
