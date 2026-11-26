"""Genera el índice del buscador del manual de usuario.

Uso: python manual/generar_indice.py

Reutiliza el extractor de encabezados del generador de la documentación, pero
apunta sólo a las páginas del manual. No editar manual/assets/buscador-indice.js
a mano.
"""
import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
GENERADOR_DOCS = RAIZ.parent / 'docs' / 'generar_buscador.py'


def _modulo():
    especificacion = importlib.util.spec_from_file_location('generar_buscador_docs', GENERADOR_DOCS)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    modulo.DOCS = RAIZ
    modulo.DESTINO = RAIZ / 'assets' / 'buscador-indice.js'
    return modulo


def construir():
    """Contenido del índice del manual."""
    contenido = _modulo().construir()
    return contenido.replace(
        '// Índice del buscador de la documentación. Generado por docs/generar_buscador.py: no editar a mano.',
        '// Índice del buscador del manual de usuario. Generado por manual/generar_indice.py: no editar a mano.',
        1,
    )


def main():
    contenido = construir()
    destino = RAIZ / 'assets' / 'buscador-indice.js'
    destino.write_text(contenido, encoding='utf-8', newline='\n')
    print(f"{destino.relative_to(RAIZ.parent)}: {contenido.count(chr(10)) - 3} entradas, "
          f"{len(contenido.encode('utf-8')) / 1024:.0f} KB")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
