"""
generar_scripts_bd.py — Regenera las páginas de docs con los scripts de creación (MySQL).

Lee docs/migrations/create_{admin,wms,intercambio}_mysql.sql y escribe
docs/inicio/base-de-datos/taurus-{admin,wms,intercambio}.html con el script
embebido, para que la documentación muestre siempre el script vigente.

Uso (desde cualquier directorio), después de regenerar el schema:
    python modules/schema_generator.py --all
    python docs/generar_scripts_bd.py
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / 'docs' / 'migrations'
DESTINO = ROOT / 'docs' / 'inicio' / 'base-de-datos'

BASES = [
    {
        'clave': 'admin',
        'base': 'taurus_admin',
        'bajada': 'Base administrativa: usuarios, tenants, roles, permisos y configuración.',
        'orden': 'Es la primera que hay que crear: las dos aplicaciones la necesitan para arrancar.',
        'ejecutar': """        <p>Ejecutar el script <code>docs/migrations/{archivo}</code> en el servidor MySQL.</p>
""",
        'notas': """
        <h2>Datos iniciales</h2>
        <p>El script no crea usuarios ni tenants. Solo carga lo que la aplicación necesita para funcionar:</p>
        <ul>
            <li>Los roles <code>ADMIN</code>, <code>OPERADOR</code> y <code>CONSULTA</code>, con sus rutas
                permitidas.</li>
            <li>Tres parámetros generales en la tabla <code>configuracion</code> (nombre y versión de la
                aplicación, modo mantenimiento).</li>
        </ul>

        <h2>Paso siguiente</h2>
        <p>Como no hay usuarios por defecto, después de crear la base hay que dar de alta el primer usuario
        del panel con <a href="superusuario.html">superusuario.exe</a>. Con ese usuario se ingresa al panel
        admin y se crean los tenants y los usuarios del WMS.</p>
""",
    },
    {
        'clave': 'wms',
        'base': 'taurus_wms',
        'bajada': 'Base operativa: maestros, stock, recepciones, pedidos y movimientos.',
        'orden': 'Se crea después de <a href="taurus-admin.html">taurus_admin</a>.',
        'notas': """
        <h2>Datos iniciales</h2>
        <p>El script solo carga las clases de pedido: Venta, Reposicion, Muestra y Devolucion. El resto de los
        maestros se carga desde la aplicación o por importación.</p>
""",
    },
    {
        'clave': 'intercambio',
        'base': 'taurus_intercambio',
        'bajada': 'Base de la interfase con sistemas externos.',
        'orden': 'Solo hace falta si se usa <a href="../../integraciones/intercambio.html">Intercambio</a>.',
        'notas': """
        <h2>Datos iniciales</h2>
        <p>Ninguno: las tablas quedan vacías hasta que el sistema externo inserte registros.</p>
""",
    },
]

# Bloque "Ejecutar" por defecto; una base puede definir el suyo con la clave 'ejecutar'.
EJECUTAR = """        <p>Desde la raíz del proyecto, con un usuario de MySQL que pueda crear bases:</p>
<pre><code>mysql -u root -p -e "source docs/migrations/{archivo}"</code></pre>
        <p>Después, registrar las migraciones como aplicadas:</p>
<pre><code>python migrate.py --db {clave} --baseline</code></pre>
"""

PLANTILLA = """<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{base} — Taurus WMS</title>
    <link rel="stylesheet" href="../../assets/docs.css">
</head>
<!-- Página generada por docs/generar_scripts_bd.py: no editar a mano. -->
<body data-root="../../" data-page="inicio/base-de-datos/taurus-{clave}.html">
<div class="layout">
    <nav id="sidebar"></nav>
    <main class="content">
        <p class="migas">Primeros pasos · Instalación · Base de datos</p>
        <h1>{base}</h1>
        <p class="bajada">{bajada}</p>

        <p>{orden}</p>

        <div class="aviso peligro">
            <p><strong>El script borra la base si ya existe.</strong> Empieza con
            <code>DROP DATABASE IF EXISTS {base}</code>. Sirve para una instalación nueva; sobre una base en
            uso, se pierden todos los datos.</p>
        </div>

        <h2>Ejecutar</h2>
{ejecutar}
        <h2>Tablas ({cantidad})</h2>
        <p>{tablas}</p>
{notas}
        <h2>Script</h2>
        <p>Archivo: <a href="../../migrations/{archivo}"><code>docs/migrations/{archivo}</code></a>
        ({lineas} líneas). Lo genera <code>modules/schema_generator.py</code>; no se edita a mano.</p>
        <details class="script">
            <summary>Ver el script completo</summary>
<pre><code>{script}</code></pre>
        </details>

        <div id="pager"></div>
    </main>
</div>
<script src="../../assets/docs.js"></script>
</body>
</html>
"""


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    for b in BASES:
        archivo = f"create_{b['clave']}_mysql.sql"
        sql = (MIGRATIONS / archivo).read_text(encoding='utf-8')
        tablas = re.findall(r'^CREATE TABLE(?: IF NOT EXISTS)? `?(\w+)`?', sql, flags=re.MULTILINE)
        pagina = PLANTILLA.format(
            archivo=archivo,
            cantidad=len(tablas),
            tablas=', '.join(f'<code>{t}</code>' for t in tablas),
            lineas=len(sql.splitlines()),
            script=html.escape(sql.rstrip(), quote=False),
            ejecutar=b.get('ejecutar', EJECUTAR).format(archivo=archivo, clave=b['clave']),
            **{k: v for k, v in b.items() if k != 'ejecutar'},
        )
        salida = DESTINO / f"taurus-{b['clave']}.html"
        salida.write_text(pagina, encoding='utf-8', newline='\n')
        print(f"{salida.relative_to(ROOT)}: {len(tablas)} tablas, {len(sql.splitlines())} líneas")
    return 0


if __name__ == '__main__':
    sys.exit(main())
