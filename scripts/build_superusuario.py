"""
build_superusuario.py — Genera superusuario-dist/superusuario.exe (PyInstaller).

Empaqueta scripts/admin_superusuario.py en un único ejecutable de consola que
no requiere Python instalado. Las credenciales NO van dentro del ejecutable:
se leen en tiempo de ejecución de superusuario.json (junto al .exe) o de
--config <ruta.json>.

Uso (desde cualquier directorio, con el .venv del proyecto):
    pip install -r requirements-build.txt
    python scripts/build_superusuario.py

Salida:
    superusuario-dist/superusuario.exe            (versionado)
    superusuario-dist/superusuario.example.json   (plantilla, versionada)
    superusuario-dist/superusuario.json           (credenciales reales, gitignored)
Los archivos intermedios quedan en build/ (gitignored).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'superusuario-dist'
WORK = ROOT / 'build' / 'superusuario'
ENTRADA = ROOT / 'scripts' / 'admin_superusuario.py'
ICONO = ROOT / 'logo' / 'Taurussuite.jpg'

# Módulos que el ejecutable no usa (el script solo necesita modules.db_config,
# modules.sql_dialect y modules.passwords): se excluyen para achicar el binario.
EXCLUIR = ['tkinter', 'flask', 'jinja2', 'openpyxl', 'flask_wtf', 'flask_limiter', 'pytest']


def main():
    try:
        import PyInstaller.__main__
    except ImportError:
        print("Falta PyInstaller: pip install -r requirements-build.txt")
        return 1

    args = [
        str(ENTRADA),
        '--name', 'superusuario',
        '--onefile',
        '--console',
        '--clean',
        '--noconfirm',
        '--distpath', str(DIST),
        '--workpath', str(WORK),
        '--specpath', str(WORK),
        '--paths', str(ROOT),
    ]
    for mod in EXCLUIR:
        args += ['--exclude-module', mod]
    try:
        import PIL  # noqa: F401  (PyInstaller necesita Pillow para convertir el .jpg a ícono)
        args += ['--icon', str(ICONO)]
    except ImportError:
        print("Pillow no instalado: el ejecutable se genera sin ícono.")

    PyInstaller.__main__.run(args)
    exe = DIST / ('superusuario.exe' if sys.platform == 'win32' else 'superusuario')
    print(f"\nListo: {exe} ({exe.stat().st_size / 1_048_576:.1f} MB)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
