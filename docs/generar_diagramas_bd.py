"""
generar_diagramas_bd.py — Regenera las páginas de docs con los diagramas de tablas y relaciones.

Lee las definiciones de modules/schema_generator.py (ADMIN_TABLES, WMS_TABLES,
INTERCAMBIO_TABLES) y escribe docs/arquitectura/base-de-datos/diagrama-{admin,wms,intercambio}.html
con los diagramas en SVG embebidos, para que la documentación muestre siempre el
schema vigente. No usa librerías externas: la disposición se calcula acá.

Una base con muchas tablas (taurus_wms) se divide en áreas (clave 'areas' de BASES):
un mapa general muestra cómo dependen las áreas entre sí y cada área tiene su propio
diagrama, chico, donde las tablas de otras áreas aparecen como referencias externas.

Uso (desde cualquier directorio), después de cambiar el schema:
    python modules/schema_generator.py --all
    python docs/generar_scripts_bd.py
    python docs/generar_diagramas_bd.py

Hay dos cosas que no salen del schema y se mantienen a mano en este archivo:
    - RELACIONES_LOGICAS: relaciones que el código usa sin declararlas en la base.
    - 'areas' de taurus_wms: a qué área pertenece cada tabla. Si se agrega una
      tabla y no se la asigna a un área, el script falla y lo avisa.
"""
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.schema_generator import ADMIN_TABLES, INTERCAMBIO_TABLES, WMS_TABLES

DESTINO = ROOT / 'docs' / 'arquitectura' / 'base-de-datos'

# Relaciones que el código usa (JOIN o búsqueda por valor) pero que la base no
# declara como FOREIGN KEY: (tabla, columna, tabla referenciada, columna referenciada).
RELACIONES_LOGICAS = {
    'admin': [
        ('usuarios', 'rol', 'roles', 'nombre'),
        ('roles_rutas', 'rol', 'roles', 'nombre'),
        ('audit_logs', 'usuario_id', 'admin_usuarios', 'id'),
    ],
    'wms': [
        ('ubicaciones', 'tipoubicacion', 'tipoubicacion', 'id'),
        ('materiales', 'unidad_medida_id', 'unidades_medida', 'id_unidad'),
        ('stock_movimientos', 'id_ubicacion', 'ubicaciones', 'id'),
        ('stock_movimientos', 'id_material', 'materiales', 'id'),
        ('inventarios_detalle', 'id_ubicacion', 'ubicaciones', 'id'),
        ('inventarios_detalle', 'id_material', 'materiales', 'id'),
    ],
    'intercambio': [],
}

BASES = [
    {
        'clave': 'admin',
        'base': 'taurus_admin',
        'tablas': ADMIN_TABLES,
        'bajada': 'Tablas de la base administrativa y cómo se relacionan: usuarios, tenants, roles y auditoría.',
        'notas': """
        <h2>Para tener en cuenta</h2>
        <ul>
            <li><strong>Dos tablas de usuarios.</strong> <code>admin_usuarios</code> son los que ingresan al panel
                admin; <code>usuarios</code> son los del WMS y pertenecen a un tenant.</li>
            <li><strong>Los roles se relacionan por nombre.</strong> <code>usuarios.rol</code> y
                <code>roles_rutas.rol</code> guardan el nombre del rol, no su <code>id</code>. Por eso, al renombrar
                un rol el panel actualiza también esas dos tablas.</li>
            <li><strong><code>tenants.id</code> sale de esta base.</strong> Todas las tablas de
                <a href="diagrama-wms.html">taurus_wms</a> lo guardan en su columna <code>tenant_id</code>. Como son
                bases distintas, esa relación no puede declararse como clave foránea.</li>
            <li><code>configuracion</code> no se relaciona con ninguna tabla.</li>
        </ul>
""",
    },
    {
        'clave': 'wms',
        'base': 'taurus_wms',
        'tablas': WMS_TABLES,
        'bajada': 'Tablas de la base operativa y cómo se relacionan, divididas en áreas: depósito, materiales, '
                  'distribución, stock, recepciones, pedidos, órdenes de movimiento e inventarios.',
        'areas': [
            {'id': 'deposito', 'titulo': 'Depósito',
             'desc': 'La estructura física: cada ubicación pertenece a una zona y tiene un tipo.',
             'tablas': ['zonas', 'tipoubicacion', 'ubicaciones']},
            {'id': 'materiales', 'titulo': 'Materiales y proveedores',
             'desc': 'El catálogo de lo que se almacena: cada material tiene una categoría y una unidad de medida, '
                     'puede tener varias presentaciones y varios proveedores habituales.',
             'tablas': ['categorias', 'unidades_medida', 'materiales', 'material_presentaciones', 'proveedores',
                        'material_proveedor']},
            {'id': 'distribucion', 'titulo': 'Clientes y distribución',
             'desc': 'A quién y cómo se entrega: los clientes tienen una ruta y un transporte predeterminado, y cada '
                     'transporte cubre una o más rutas y sale por un muelle (una ubicación).',
             'tablas': ['rutas', 'transportes', 'transporte_rutas', 'clientes']},
            {'id': 'stock', 'titulo': 'Stock',
             'desc': 'Cuánto hay y qué se movió: <code>stockcontable</code> es el saldo actual de cada material en '
                     'cada ubicación, y <code>stock_movimientos</code> el historial de ingresos y egresos.',
             'tablas': ['stockcontable', 'stock_movimientos']},
            {'id': 'recepciones', 'titulo': 'Recepciones',
             'desc': 'El ingreso de mercadería: una cabecera por recepción (proveedor, ubicación de recepción y de '
                     'destino) y un renglón de detalle por material.',
             'tablas': ['recepciones_cabecera', 'recepciones_detalle']},
            {'id': 'pedidos', 'titulo': 'Pedidos',
             'desc': 'Lo que piden los clientes: una cabecera por pedido (cliente, clase, ruta y transporte) y un '
                     'renglón de detalle por material.',
             'tablas': ['clases_pedido', 'pedidos_cabecera', 'pedidos_detalle']},
            {'id': 'omc', 'titulo': 'Órdenes de movimiento (OMC)',
             'desc': 'Los traslados dentro del depósito: cada orden va de una ubicación a otra y puede originarse en '
                     'una recepción (guardado) o en un pedido (preparación).',
             'tablas': ['omc', 'omc_contenedores']},
            {'id': 'inventarios', 'titulo': 'Inventarios',
             'desc': 'Los conteos físicos: una cabecera por inventario y un renglón por cada material contado en '
                     'cada ubicación.',
             'tablas': ['inventarios_cabecera', 'inventarios_detalle']},
        ],
        'notas': """
        <h2>Para tener en cuenta</h2>
        <ul>
            <li><strong><code>tenant_id</code> no se dibuja.</strong> Todas las tablas lo tienen y apunta a
                <code>tenants.id</code> de <a href="diagrama-admin.html">taurus_admin</a>. Al estar en otra base no
                es una clave foránea; el aislamiento lo hace el código (ver
                <a href="../multi-tenancy.html">Multi-tenancy</a>).</li>
            <li><strong>Los nombres de las claves no son uniformes.</strong> Algunas tablas usan <code>id</code> y
                otras <code>id_pedido</code>, <code>id_cliente</code>, <code>id_transporte</code>, etc.
                <code>stockcontable</code> usa nombres con mayúsculas (<code>ID</code>, <code>Ubicacion</code>,
                <code>Material</code>).</li>
            <li><strong><code>id_contenedor</code> no es una relación.</strong> Es el código del contenedor
                (pallet, caja), un dato; no hay una tabla de contenedores.</li>
            <li><strong>Cabecera y detalle.</strong> Recepciones, pedidos e inventarios se guardan en dos tablas:
                la cabecera con los datos generales y el detalle con un renglón por material.</li>
        </ul>
""",
    },
    {
        'clave': 'intercambio',
        'base': 'taurus_intercambio',
        'tablas': INTERCAMBIO_TABLES,
        'bajada': 'Tablas de la interfase con sistemas externos.',
        'notas': """
        <h2>Para tener en cuenta</h2>
        <ul>
            <li><strong>No hay relaciones entre estas tablas.</strong> Cada una es una cola independiente: un
                registro es una operación (alta, modificación o baja) que el sistema externo deja para que el WMS
                la aplique.</li>
            <li><strong>Las referencias son por código, no por id.</strong> Un pedido indica su cliente con
                <code>cliente_codigo</code>, su ruta con <code>ruta_nombre</code>, etc. El proceso los resuelve
                contra <a href="diagrama-wms.html">taurus_wms</a> al aplicar el registro.</li>
            <li><strong><code>tenant_codigo</code></strong> se resuelve contra <code>tenants.codigo</code> de
                <a href="diagrama-admin.html">taurus_admin</a>.</li>
            <li><code>intercambio_log</code> guarda el historial de ejecuciones del proceso.</li>
        </ul>
        <p>El funcionamiento completo está en <a href="../../integraciones/intercambio.html">Intercambio</a>.</p>
""",
        # Columna que guarda el id del registro resultante en el WMS, y tabla del WMS a la que corresponde
        'destinos': {
            'intercambio_materiales': ('id_material_wms', 'materiales.id'),
            'intercambio_rutas': ('id_ruta_wms', 'rutas.id_ruta'),
            'intercambio_transportes': ('id_transporte_wms', 'transportes.id_transporte'),
            'intercambio_transporte_rutas': (None, 'transporte_rutas'),
            'intercambio_clientes': ('id_cliente_wms', 'clientes.id_cliente'),
            'intercambio_pedidos': ('id_pedido_wms', 'pedidos_cabecera.id_pedido'),
        },
    },
]

# --- Medidas del dibujo (px) ---
ANCHO = 230          # ancho de cada caja
ALTO_TITULO = 26
ALTO_FILA = 19
SEP_V = 26           # separación vertical entre cajas de una misma columna
SEP_H = 84           # separación horizontal entre columnas (canal por donde pasan las líneas)
MARGEN = 16
# Un color por caja referenciada, para poder seguir sus líneas (legibles en tema claro y oscuro).
# Tienen que coincidir con las clases .c0 ... .c9 de docs/assets/docs.css.
COLORES = ['#3182ce', '#dd6b20', '#38a169', '#805ad5', '#d53f8c', '#319795', '#b7791f', '#e53e3e',
           '#5a67d8', '#718096']


# ============================================================================
# Relaciones y contenido de las cajas
# ============================================================================

def relaciones_de(tablas, logicas):
    """Lista de relaciones {tabla, columna, ref_tabla, ref_columna, logica}."""
    rels = []
    for t in tablas:
        for fk in t.get('foreign_keys', []):
            for col, ref_col in zip(fk['columns'], fk['ref_columns'], strict=True):
                rels.append({'tabla': t['name'], 'columna': col, 'ref_tabla': fk['ref_table'],
                             'ref_columna': ref_col, 'logica': False})
    for tabla, col, ref_tabla, ref_col in logicas:
        rels.append({'tabla': tabla, 'columna': col, 'ref_tabla': ref_tabla, 'ref_columna': ref_col, 'logica': True})
    return rels


def claves_primarias(tabla):
    return tabla.get('primary_key') or [c['name'] for c in tabla['columns'] if c.get('pk')]


def nodo_tabla(tabla, rels):
    """Caja de una tabla: claves primarias y columnas que participan en alguna de las relaciones dadas."""
    pks = claves_primarias(tabla)
    salientes = {r['columna'] for r in rels if r['tabla'] == tabla['name'] and not r['logica']}
    logicas = {r['columna'] for r in rels if r['tabla'] == tabla['name'] and r['logica']}
    entrantes = {r['ref_columna'] for r in rels if r['ref_tabla'] == tabla['name']}
    filas = []
    for c in tabla['columns']:
        nombre = c['name']
        if nombre in pks or nombre in salientes or nombre in logicas or nombre in entrantes:
            marca = 'PK' if nombre in pks else ''
            if nombre in salientes:
                marca = (marca + ' FK').strip()
            elif nombre in logicas:
                marca = (marca + ' REF').strip()
            filas.append({'nombre': nombre, 'marca': marca})
    resto = len(tabla['columns']) - len(filas)
    if resto:
        filas.append({'nombre': f'+ {resto} columna{"s" if resto != 1 else ""} más', 'nota': True})
    return {'titulo': tabla['name'], 'filas': filas}


def nodo_externo(tabla, rels, area):
    """Caja de una tabla de otra área: solo las columnas a las que se hace referencia."""
    pks = claves_primarias(tabla)
    usadas = {r['ref_columna'] for r in rels if r['ref_tabla'] == tabla['name']}
    filas = [{'nombre': c['name'], 'marca': 'PK' if c['name'] in pks else ''}
             for c in tabla['columns'] if c['name'] in usadas]
    filas.append({'nombre': f'área: {area["titulo"]}', 'nota': True})
    return {'titulo': tabla['name'], 'filas': filas, 'externa': True, 'href': f'#area-{area["id"]}'}


def aristas_de(rels):
    """Líneas de un diagrama de tablas: de la clave referenciada a la columna que la referencia."""
    return [{
        'origen': r['ref_tabla'], 'fila_origen': r['ref_columna'],
        'destino': r['tabla'], 'fila_destino': r['columna'], 'logica': r['logica'],
        'titulo': (f"{r['tabla']}.{r['columna']} → {r['ref_tabla']}.{r['ref_columna']}"
                   + (' (sin clave foránea declarada)' if r['logica'] else '')),
    } for r in rels]


# ============================================================================
# Dibujo
# ============================================================================

def calcular_columnas(nombres, aristas):
    """Reparte las cajas en columnas: cada una queda a la derecha de las que referencia."""
    padres = {n: set() for n in nombres}
    hijos = {n: set() for n in nombres}
    for a in aristas:
        if a['origen'] != a['destino']:
            padres[a['destino']].add(a['origen'])
            hijos[a['origen']].add(a['destino'])

    nivel = {}

    def profundidad(n, visitando=()):
        if n not in nivel:
            nivel[n] = 1 + max((profundidad(p, (*visitando, n)) for p in padres[n] if p not in visitando), default=-1)
        return nivel[n]

    for n in nombres:
        profundidad(n)
    # Una caja que nadie obliga a estar a la izquierda se acerca a las que la referencian
    for n in sorted(nombres, key=lambda x: -nivel[x]):
        if hijos[n]:
            nivel[n] = max(nivel[n], min(nivel[h] for h in hijos[n]) - 1)

    sueltas = [n for n in nombres if not padres[n] and not hijos[n]]
    columnas = [[] for _ in range(max(nivel.values()) + 1)]
    for n in nombres:
        if n not in sueltas:
            columnas[nivel[n]].append(n)
    columnas = [c for c in columnas if c]

    # Orden dentro de cada columna: cerca de sus vecinas (baricentro), para cruzar menos líneas
    vecinos = {n: padres[n] | hijos[n] for n in nombres}
    for _ in range(12):
        for cols in (columnas, columnas[::-1]):
            pos = {n: i for c in columnas for i, n in enumerate(c)}
            for c in cols:
                c.sort(key=lambda n: (sum(pos[v] for v in vecinos[n]) / len(vecinos[n]), pos[n]))
                pos.update({n: i for i, n in enumerate(c)})
    return columnas, sueltas


def dibujar(nodos, aristas, prefijo, etiqueta, ancho_caja=ANCHO, sep_h=SEP_H):
    """SVG de un diagrama.

    nodos:   {id: {'titulo', 'filas': [{'nombre', 'marca'?, 'nota'?}], 'externa'?, 'href'?}}
    aristas: [{'origen', 'fila_origen'?, 'destino', 'fila_destino'?, 'logica'?, 'titulo'}]
             ('origen' es la caja referenciada: queda a la izquierda y recibe la flecha)
    prefijo: identificador único del diagrama dentro de la página (para los ids del SVG).
    ancho_caja, sep_h: ancho de las cajas y separación entre columnas, si no son los habituales.
    """
    columnas, sueltas = calcular_columnas(list(nodos), aristas)
    cajas = {n: {'alto': ALTO_TITULO + ALTO_FILA * len(nodo['filas']) + 6} for n, nodo in nodos.items()}

    altos = [sum(cajas[n]['alto'] for n in c) + SEP_V * (len(c) - 1) for c in columnas]
    alto_rel = max(altos, default=0)
    for i, c in enumerate(columnas):
        x = MARGEN + i * (ancho_caja + sep_h)
        y = MARGEN + (alto_rel - altos[i]) / 2
        for n in c:
            cajas[n].update(x=x, y=y)
            y += cajas[n]['alto'] + SEP_V
    ancho_rel = MARGEN + len(columnas) * (ancho_caja + sep_h) - sep_h if columnas else MARGEN

    # Cajas sin relaciones: en filas debajo (o solas, si el diagrama no tiene relaciones)
    y_sueltas = MARGEN + alto_rel + (SEP_V * 2 if columnas else 0)
    por_fila = max(len(columnas), 3)
    sep_sueltas = 30
    for i, n in enumerate(sueltas):
        fila, col = divmod(i, por_fila)
        alto_filas_ant = sum(max(cajas[m]['alto'] for m in sueltas[f * por_fila:(f + 1) * por_fila]) + SEP_V
                             for f in range(fila))
        cajas[n].update(x=MARGEN + col * (ancho_caja + sep_sueltas), y=y_sueltas + alto_filas_ant)
    ancho_sueltas = MARGEN + min(len(sueltas), por_fila) * (ancho_caja + sep_sueltas) - sep_sueltas if sueltas else 0

    ancho = max(ancho_rel, ancho_sueltas) + MARGEN
    alto = max((c['y'] + c['alto'] for c in cajas.values()), default=0) + MARGEN
    indice_col = {n: i for i, c in enumerate(columnas) for n in c}

    def y_fila(n, fila):
        for i, f in enumerate(nodos[n]['filas']):
            if f['nombre'] == fila:
                return cajas[n]['y'] + ALTO_TITULO + ALTO_FILA * i + ALTO_FILA / 2
        return cajas[n]['y'] + ALTO_TITULO / 2

    def hueco(col, y):
        """Altura libre (entre cajas) de una columna intermedia más cercana a y."""
        cs = [cajas[n] for n in columnas[col]]
        huecos = [cs[0]['y'] - SEP_V / 2] + [c['y'] + c['alto'] + SEP_V / 2 for c in cs]
        return min(huecos, key=lambda h: abs(h - y))

    # Color de las líneas que llegan a cada caja referenciada
    referenciadas = sorted({a['origen'] for a in aristas}, key=lambda n: (indice_col[n], cajas[n]['y']))
    color = {n: i % len(COLORES) for i, n in enumerate(referenciadas)}

    # Recorrido de cada línea, pasando por los huecos de las columnas intermedias
    recorridos = []
    uso = {}
    for a in aristas:
        ci, cf = indice_col[a['origen']], indice_col[a['destino']]
        y0, y1 = y_fila(a['origen'], a.get('fila_origen')), y_fila(a['destino'], a.get('fila_destino'))
        pasos = []
        for col in range(ci + 1, cf):
            yh = hueco(col, y0 + (y1 - y0) * (col - ci) / (cf - ci))
            pasos.append((col, yh))
            uso.setdefault((col, yh), []).append(len(recorridos))
        recorridos.append((a, y0, y1, pasos))

    partes = []
    for i, (a, y0, y1, pasos) in enumerate(recorridos):
        puntos = [(cajas[a['origen']]['x'] + ancho_caja, y0)]
        for col, yh in pasos:
            # Varias líneas por el mismo hueco: se separan para que no se pisen
            compartido = uso[(col, yh)]
            yh += (compartido.index(i) - (len(compartido) - 1) / 2) * 5
            xc = MARGEN + col * (ancho_caja + sep_h)
            puntos += [(xc - 8, yh), (xc + ancho_caja + 8, yh)]
        puntos.append((cajas[a['destino']]['x'], y1))
        d = f'M{puntos[0][0]:.0f},{puntos[0][1]:.0f}'
        for j in range(1, len(puntos)):
            (xa, ya), (xb, yb) = puntos[j - 1], puntos[j]
            if ya == yb:
                d += f' L{xb:.0f},{yb:.0f}'
            else:
                k = (xb - xa) / 2
                d += f' C{xa + k:.0f},{ya:.1f} {xb - k:.0f},{yb:.1f} {xb:.0f},{yb:.1f}'
        c = color[a['origen']]
        clase = f'rel c{c}' + (' logica' if a.get('logica') else '')
        partes.append(f'<path class="{clase}" d="{d}" marker-start="url(#flecha-{prefijo}-{c})">'
                      f'<title>{html.escape(a["titulo"])}</title></path>')

    for n, nodo in nodos.items():
        c = cajas[n]
        x, y = c['x'], c['y']
        g = [f'<g class="tabla{" externa" if nodo.get("externa") else ""}">',
             f'<rect class="caja" x="{x:.0f}" y="{y:.0f}" width="{ancho_caja}" height="{c["alto"]}" rx="5"/>',
             f'<path class="titulo" d="M{x:.0f},{y + ALTO_TITULO:.0f} v-{ALTO_TITULO - 5} a5,5 0 0 1 5,-5 '
             f'h{ancho_caja - 10} a5,5 0 0 1 5,5 v{ALTO_TITULO - 5} z"/>',
             f'<text class="nombre" x="{x + 10:.0f}" y="{y + 17:.0f}">{html.escape(nodo["titulo"])}</text>']
        if n in color:
            # Franja del color de las líneas que llegan a esta caja
            g.append(f'<rect class="franja c{color[n]}" x="{x + ancho_caja - 6:.0f}" y="{y + ALTO_TITULO + 3:.0f}" '
                     f'width="4" height="{c["alto"] - ALTO_TITULO - 6}" rx="2"/>')
        yf = y + ALTO_TITULO
        for f in nodo['filas']:
            clase = 'resto' if f.get('nota') else 'col'
            g.append(f'<text class="{clase}" x="{x + 10:.0f}" y="{yf + 14:.0f}">{html.escape(f["nombre"])}</text>')
            if f.get('marca'):
                g.append(f'<text class="marca" x="{x + ancho_caja - 14:.0f}" y="{yf + 14:.0f}" '
                         f'text-anchor="end">{f["marca"]}</text>')
            yf += ALTO_FILA
        g.append('</g>')
        caja = '\n'.join(g)
        if nodo.get('href'):
            caja = f'<a href="{nodo["href"]}">{caja}</a>'
        partes.append(caja)

    marcadores = ''.join(
        f'<marker id="flecha-{prefijo}-{i}" viewBox="0 0 10 10" refX="0" refY="5" markerWidth="9" '
        f'markerHeight="9" orient="auto"><path class="punta c{i}" d="M0,5 L10,1 L10,9 z"/></marker>'
        for i in sorted(set(color.values())))
    return (f'<svg class="der ajustar" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho:.0f} {alto:.0f}" '
            f'width="{ancho:.0f}" height="{alto:.0f}" role="img" aria-label="{html.escape(etiqueta)}">\n'
            f'<defs>{marcadores}</defs>\n' + '\n'.join(partes) + '\n</svg>')


def bloque_svg(svg):
    return f'        <div class="diagrama ancho">\n{svg}\n        </div>\n'


# ============================================================================
# Secciones de la página
# ============================================================================

LEYENDA = """        <h2>Cómo leer los diagramas</h2>
        <ul>
            <li>Cada caja es una tabla. Se muestran su clave primaria (<strong>PK</strong>) y las columnas que
                participan en una relación; el resto se resume en "+ N columnas más".</li>
            <li>Cada línea es una relación, y <strong>la flecha apunta a la tabla referenciada</strong>: va de la
                columna que guarda el dato a la clave que identifica al registro.</li>
            <li><strong>FK</strong> y línea continua: clave foránea declarada en la base. <strong>REF</strong> y
                línea punteada: relación que usa la aplicación pero que la base no controla.</li>
            <li>Todas las líneas que llegan a una misma tabla tienen el mismo color, que es el de la franja a la
                derecha de esa tabla.</li>
            <li>Las tablas se leen de izquierda a derecha: cada una está a la derecha de las que referencia.</li>
            <li>Al pasar el mouse sobre una línea se resalta y muestra qué columnas une.</li>
{extra}        </ul>
"""
LEYENDA_AREAS = """            <li>En el diagrama de un área, una caja gris de borde punteado es una tabla de <strong>otra área</strong>:
                se muestra solo para ver a dónde apunta la relación. Al hacer clic lleva al diagrama de su área.</li>
"""
LEYENDA_SIN_RELACIONES = """        <h2>Diagrama</h2>
        <p>Cada caja es una tabla, con su clave primaria (<strong>PK</strong>) y la cantidad de columnas restantes.
        No hay líneas porque estas tablas no se relacionan entre sí.</p>
"""


def seccion_unica(base, tablas, rels):
    """Bases chicas: un solo diagrama con todas las tablas."""
    nodos = {n: nodo_tabla(t, rels) for n, t in tablas.items()}
    svg = dibujar(nodos, aristas_de(rels), base['clave'], f'Diagrama de tablas y relaciones de {base["base"]}')
    if not rels:
        return LEYENDA_SIN_RELACIONES + bloque_svg(svg)
    return LEYENDA.format(extra='') + '\n        <h2>Diagrama</h2>\n' + bloque_svg(svg)


def seccion_areas(base, tablas, rels):
    """Bases grandes: mapa general de áreas y un diagrama por área."""
    areas = base['areas']
    area_de = {t: a for a in areas for t in a['tablas']}
    sin_area = sorted(set(tablas) - set(area_de))
    inexistentes = sorted(set(area_de) - set(tablas))
    if sin_area or inexistentes or sum(len(a['tablas']) for a in areas) != len(area_de):
        raise SystemExit(
            f"{base['base']}: revisar 'areas' en docs/generar_diagramas_bd.py. "
            f"Tablas sin área: {sin_area or '-'}. Tablas que ya no existen o están repetidas: {inexistentes or '-'}.")

    partes = [LEYENDA.format(extra=LEYENDA_AREAS)]

    # --- Mapa general: una caja por área, una línea por cada dependencia entre áreas ---
    nodos = {a['id']: {'titulo': a['titulo'], 'filas': [{'nombre': t} for t in a['tablas']],
                       'href': f'#area-{a["id"]}'} for a in areas}
    dependencias = {}
    for r in rels:
        origen, destino = area_de[r['ref_tabla']], area_de[r['tabla']]
        if origen is not destino:
            dependencias.setdefault((origen['id'], destino['id']), set()).add(f"{r['tabla']} → {r['ref_tabla']}")
    titulos = {a['id']: a['titulo'] for a in areas}
    aristas = [{'origen': o, 'destino': d,
                'titulo': f'{titulos[d]} usa tablas de {titulos[o]}: ' + ', '.join(sorted(pares))}
               for (o, d), pares in dependencias.items()]
    partes.append(f"""
        <h2>Mapa general</h2>
        <p>La base tiene {len(tablas)} tablas, agrupadas en {len(areas)} áreas. Este mapa muestra las áreas y de
        cuáles depende cada una: la flecha apunta al área cuyas tablas se usan. A la izquierda quedan los datos
        maestros, que no dependen de nadie; a la derecha, las operaciones, que se apoyan en ellos. Cada caja
        lleva al diagrama detallado de su área.</p>
""" + bloque_svg(dibujar(nodos, aristas, f'{base["clave"]}-mapa', f'Mapa de áreas de {base["base"]}',
                                 ancho_caja=206, sep_h=64)))

    filas = '\n'.join(
        f'                    <tr><td><a href="#area-{a["id"]}">{a["titulo"]}</a></td>'
        f'<td>{", ".join(f"<code>{t}</code>" for t in a["tablas"])}</td></tr>' for a in areas)
    partes.append(f"""        <div class="tabla-scroll">
            <table>
                <thead><tr><th>Área</th><th>Tablas</th></tr></thead>
                <tbody>
{filas}
                </tbody>
            </table>
        </div>

        <h2>Diagramas por área</h2>
""")

    # --- Un diagrama por área ---
    for a in areas:
        propias = set(a['tablas'])
        rels_area = [r for r in rels if r['tabla'] in propias]
        nodos = {t: nodo_tabla(tablas[t], rels_area) for t in a['tablas']}
        for t in sorted({r['ref_tabla'] for r in rels_area} - propias):
            nodos[t] = nodo_externo(tablas[t], rels_area, area_de[t])
        svg = dibujar(nodos, aristas_de(rels_area), f'{base["clave"]}-{a["id"]}',
                      f'Diagrama del área {a["titulo"]} de {base["base"]}')

        usa = sorted({area_de[r['ref_tabla']]['titulo'] for r in rels_area if r['ref_tabla'] not in propias})
        la_usan = {}
        for r in rels:
            if r['ref_tabla'] in propias and r['tabla'] not in propias:
                la_usan.setdefault(area_de[r['tabla']]['id'], set()).add(r['ref_tabla'])
        notas = []
        if usa:
            notas.append(f'<strong>Usa tablas de:</strong> {", ".join(usa)}.')
        if la_usan:
            detalle = '; '.join(
                f'<a href="#area-{ar}">{titulos[ar]}</a> ({", ".join(f"<code>{t}</code>" for t in sorted(ts))})'
                for ar, ts in sorted(la_usan.items(), key=lambda x: titulos[x[0]]))
            notas.append(f'<strong>La usan:</strong> {detalle}.')
        if not usa and not la_usan:
            notas.append('No se relaciona con otras áreas.')
        partes.append(f"""
        <h3 id="area-{a['id']}">{a['titulo']}</h3>
        <p>{a['desc']}</p>
""" + bloque_svg(svg) + f"        <p>{' '.join(notas)}</p>\n")

    # --- Diagrama completo, plegado ---
    nodos = {n: nodo_tabla(t, rels) for n, t in tablas.items()}
    completo = dibujar(nodos, aristas_de(rels), f'{base["clave"]}-todo',
                       f'Diagrama completo de tablas y relaciones de {base["base"]}')
    completo = completo.replace('class="der ajustar"', 'class="der"', 1)  # tamaño real, con desplazamiento
    partes.append(f"""
        <h2>Diagrama completo</h2>
        <p>Todas las tablas y relaciones en un solo dibujo. Sirve para ver el conjunto, pero es grande y denso:
        para entender una parte conviene el diagrama de su área.</p>
        <details class="ancho">
            <summary>Mostrar el diagrama completo</summary>
            <div class="diagrama">
{completo}
            </div>
        </details>
""")
    return ''.join(partes)


def tabla_relaciones(base, rels):
    if not rels:
        return ''
    area_de = {t: a['titulo'] for a in base.get('areas', []) for t in a['tablas']}
    filas = []
    for r in sorted(rels, key=lambda r: (area_de.get(r['tabla'], ''), r['tabla'], r['columna'])):
        tipo = 'Lógica (sin clave foránea)' if r['logica'] else 'Clave foránea'
        area = f"<td>{area_de[r['tabla']]}</td>" if area_de else ''
        filas.append(f"                    <tr>{area}<td><code>{r['tabla']}.{r['columna']}</code></td>"
                     f"<td><code>{r['ref_tabla']}.{r['ref_columna']}</code></td><td>{tipo}</td></tr>")
    return ("""
        <h2>Todas las relaciones</h2>
        <p>Las relaciones de los diagramas, en una tabla. Se lee: la columna guarda la clave de un registro de la
        tabla referenciada.</p>
        <div class="tabla-scroll">
            <table>
                <thead><tr>""" + ('<th>Área</th>' if area_de else '') + """<th>Columna</th><th>Referencia a</th><th>Tipo</th></tr></thead>
                <tbody>
""" + '\n'.join(filas) + """
                </tbody>
            </table>
        </div>
""")


def tabla_destinos(base):
    """Para intercambio: a qué tabla del WMS se aplica cada tabla."""
    if 'destinos' not in base:
        return ''
    filas = []
    for tabla, (columna, destino) in base['destinos'].items():
        col = f'<code>{columna}</code>' if columna else '—'
        filas.append(f"                    <tr><td><code>{tabla}</code></td><td><code>{destino}</code></td><td>{col}</td></tr>")
    return ("""
        <h2>A qué tabla del WMS se aplica cada una</h2>
        <p>Al procesar un registro, el id del registro resultante en <code>taurus_wms</code> se guarda en la
        columna indicada. Son bases distintas, así que no es una clave foránea.</p>
        <div class="tabla-scroll">
            <table>
                <thead><tr><th>Tabla de intercambio</th><th>Se aplica sobre (taurus_wms)</th><th>Columna con el id resultante</th></tr></thead>
                <tbody>
""" + '\n'.join(filas) + """
                </tbody>
            </table>
        </div>
""")


PLANTILLA = """<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Diagrama de {base} — Taurus WMS</title>
    <link rel="stylesheet" href="../../assets/docs.css">
</head>
<!-- Página generada por docs/generar_diagramas_bd.py: no editar a mano. -->
<body data-root="../../" data-page="arquitectura/base-de-datos/diagrama-{clave}.html">
<div class="layout">
    <nav id="sidebar"></nav>
    <main class="content">
        <p class="migas">Arquitectura · Base de datos</p>
        <h1>Diagrama de {base}</h1>
        <p class="bajada">{bajada}</p>

        <p>{resumen} El script completo, con todas las columnas, está en
        <a href="../../inicio/base-de-datos/taurus-{clave}.html">{base}</a>.</p>

{diagramas}{relaciones}{notas}
        <h2>Mantener el diagrama al día</h2>
        <p>Esta página se genera desde <code>modules/schema_generator.py</code>. Después de un cambio de schema:</p>
<pre><code>python docs/generar_diagramas_bd.py</code></pre>
        <p>{mantenimiento}</p>

        <div id="pager"></div>
    </main>
</div>
<script src="../../assets/docs.js"></script>
</body>
</html>
"""


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    for base in BASES:
        tablas = {t['name']: t for t in base['tablas']}
        rels = relaciones_de(base['tablas'], RELACIONES_LOGICAS[base['clave']])
        declaradas = sum(1 for r in rels if not r['logica'])
        logicas = len(rels) - declaradas
        resumen = f"{len(tablas)} tablas"
        if rels:
            resumen += f", {declaradas} relaci{'ón declarada' if declaradas == 1 else 'ones declaradas'} como clave foránea"
            if logicas:
                resumen += f" y {logicas} relaci{'ón lógica' if logicas == 1 else 'ones lógicas'}"
        else:
            resumen += ", sin relaciones entre ellas"

        mantenimiento = ('Las relaciones sin clave foránea declarada no salen del schema: se mantienen a mano en '
                         '<code>RELACIONES_LOGICAS</code>, dentro de ese script.')
        if 'areas' in base:
            diagramas = seccion_areas(base, tablas, rels)
            mantenimiento += (' Ahí también está, en <code>areas</code>, a qué área pertenece cada tabla: una tabla '
                              'nueva hay que asignarla a un área, o el script avisa y no genera la página.')
        else:
            diagramas = seccion_unica(base, tablas, rels)

        pagina = PLANTILLA.format(
            base=base['base'], clave=base['clave'], bajada=base['bajada'], resumen=resumen + '.',
            diagramas=diagramas, relaciones=tabla_relaciones(base, rels) + tabla_destinos(base),
            notas=base['notas'], mantenimiento=mantenimiento,
        )
        destino = DESTINO / f"diagrama-{base['clave']}.html"
        destino.write_text(pagina, encoding='utf-8', newline='\n')
        print(f"{destino.relative_to(ROOT)}: {resumen}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
