"""Modelo único de la navegación lateral del WMS.

Antes el menú estaba escrito a mano en ``templates/base.html``: tenía destinos
duplicados, sólo dos enlaces respetaban los permisos y no había forma de saber
qué sección correspondía al ítem activo. Acá vive la estructura canónica; el
template sólo la renderiza y Flask la filtra con las rutas permitidas del rol.

Es un módulo puro (sin Flask ni BD): recibe un callable ``tiene_permiso`` y el
path actual, y devuelve datos listos para Jinja. Eso lo hace testeable sin
levantar la aplicación.
"""

import json

# Claves reservadas dentro del JSON de preferencias del usuario. El resto de
# claves son los nombres de sección y guardan True = expandida. La columna
# ``usuarios.sidebar_preferences`` es TEXT: se mantiene el formato plano para
# no romper las preferencias ya guardadas.
PREF_MODO = '_modo'
PREF_FAVORITOS = '_favoritos'
MODOS = ('expandido', 'rail')
MAX_FAVORITOS = 6

# Preferencias del menú anterior: la sección "Consultas" se integró en
# "Sistema" y "Acceso Rápido" dejó de existir como sección (ahora son los
# favoritos). Se migran al abrir el menú por primera vez.
SECCIONES_LEGADO = {
    'consultas': 'sistema',
    'rapido': 'operaciones',
}

# Cada destino aparece una sola vez. Los permisos se evalúan sobre ``ruta`` con
# el mismo helper que usa el middleware (``tiene_permiso_ruta``).
NAVEGACION = (
    {
        'clave': 'inicio',
        'etiqueta': 'Inicio',
        'icono': 'fas fa-home',
        'directo': True,
        'items': (
            {
                'clave': 'panel',
                'etiqueta': 'Panel de control',
                'icono': 'fas fa-home',
                'ruta': '/',
                'endpoint': 'index',
                'palabras_clave': 'inicio panel control home',
            },
        ),
    },
    {
        'clave': 'favoritos',
        'etiqueta': 'Favoritos',
        'icono': 'fas fa-star',
        'items': (),  # dinámico: se arma desde PREF_FAVORITOS
    },
    {
        'clave': 'operaciones',
        'etiqueta': 'Operaciones',
        'icono': 'fas fa-cogs',
        'items': (
            {
                'clave': 'pedidos',
                'etiqueta': 'Pedidos',
                'icono': 'fas fa-shopping-cart',
                'ruta': '/pedidos',
                'endpoint': 'pedidos.listar',
                'palabras_clave': 'pedidos ordenes orden venta',
            },
            {
                'clave': 'recepciones',
                'etiqueta': 'Recepciones',
                'icono': 'fas fa-sign-in-alt',
                'ruta': '/recepciones',
                'endpoint': 'recepciones.listar',
                'palabras_clave': 'recepciones ingreso entrada mercaderia',
            },
            {
                'clave': 'despacho',
                'etiqueta': 'Despacho',
                'icono': 'fas fa-truck-loading',
                'ruta': '/despacho',
                'endpoint': 'despacho.listar',
                'palabras_clave': 'despacho salida expedicion picking',
            },
            {
                'clave': 'movil',
                'etiqueta': 'Móvil',
                'icono': 'fas fa-mobile-alt',
                'ruta': '/movil',
                'endpoint': 'movil.hub',
                'palabras_clave': 'movil app terminal smartphone',
            },
        ),
    },
    {
        'clave': 'maestros',
        'etiqueta': 'Maestros',
        'icono': 'fas fa-boxes',
        'items': (
            {
                'clave': 'materiales',
                'etiqueta': 'Materiales',
                'icono': 'fas fa-boxes',
                'ruta': '/materiales',
                'endpoint': 'materiales.listar',
                'palabras_clave': 'materiales articulos productos',
            },
            {
                'clave': 'categorias',
                'etiqueta': 'Categorías',
                'icono': 'fas fa-tags',
                'ruta': '/categorias',
                'endpoint': 'categorias.listar',
                'palabras_clave': 'categorias rubros familias',
            },
            {
                'clave': 'unidades',
                'etiqueta': 'Unidades de medida',
                'icono': 'fas fa-ruler-combined',
                'ruta': '/unidades',
                'endpoint': 'unidades.unidades',
                'palabras_clave': 'unidades medida um',
            },
            {
                'clave': 'clases_pedido',
                'etiqueta': 'Clases de pedido',
                'icono': 'fas fa-layer-group',
                'ruta': '/clases-pedido',
                'endpoint': 'clases_pedido.listar',
                'palabras_clave': 'clases pedido tipos',
            },
        ),
    },
    {
        'clave': 'logistica',
        'etiqueta': 'Logística',
        'icono': 'fas fa-route',
        'items': (
            {
                'clave': 'clientes',
                'etiqueta': 'Clientes',
                'icono': 'fas fa-users',
                'ruta': '/clientes',
                'endpoint': 'clientes.listar',
                'palabras_clave': 'clientes compradores destinatarios',
            },
            {
                'clave': 'proveedores',
                'etiqueta': 'Proveedores',
                'icono': 'fas fa-truck',
                'ruta': '/proveedores',
                'endpoint': 'proveedores.listar',
                'palabras_clave': 'proveedores origen',
            },
            {
                'clave': 'transportes',
                'etiqueta': 'Transportes',
                'icono': 'fas fa-shipping-fast',
                'ruta': '/transportes',
                'endpoint': 'transportes.listar',
                'palabras_clave': 'transportes camiones carriers',
            },
            {
                'clave': 'rutas',
                'etiqueta': 'Rutas',
                'icono': 'fas fa-route',
                'ruta': '/rutas',
                'endpoint': 'rutas.listar',
                'palabras_clave': 'rutas recorridos entregas',
            },
        ),
    },
    {
        'clave': 'almacen',
        'etiqueta': 'Almacén',
        'icono': 'fas fa-warehouse',
        'items': (
            {
                'clave': 'ubicaciones',
                'etiqueta': 'Ubicaciones',
                'icono': 'fas fa-warehouse',
                'ruta': '/ubicaciones',
                'endpoint': 'ubicaciones.listar',
                'palabras_clave': 'ubicaciones posiciones estanteria',
            },
            {
                'clave': 'zonas',
                'etiqueta': 'Zonas',
                'icono': 'fas fa-map-marked-alt',
                'ruta': '/zonas',
                'endpoint': 'zonas.listar',
                'palabras_clave': 'zonas areas sectores',
            },
            {
                'clave': 'tipoubicacion',
                'etiqueta': 'Tipos de ubicación',
                'icono': 'fas fa-project-diagram',
                'ruta': '/tipoubicacion',
                'endpoint': 'tipoubicacion.listar',
                'palabras_clave': 'tipos ubicacion muelles recepcion salida',
            },
            {
                'clave': 'stock',
                'etiqueta': 'Stock',
                'icono': 'fas fa-clipboard-check',
                'ruta': '/stockcontable',
                'endpoint': 'stockcontable.listar',
                'palabras_clave': 'stock existencias disponible saldo',
            },
            {
                'clave': 'inventario',
                'etiqueta': 'Inventario',
                'icono': 'fas fa-clipboard-list',
                'ruta': '/inventario',
                'endpoint': 'inventario.listar',
                'palabras_clave': 'inventario conteo recuento',
            },
            {
                'clave': 'omc',
                'etiqueta': 'Movimientos (OMC)',
                'icono': 'fas fa-exchange-alt',
                'ruta': '/omc',
                'endpoint': 'omc.listar',
                'palabras_clave': 'omc movimientos transferencias',
            },
        ),
    },
    {
        'clave': 'sistema',
        'etiqueta': 'Reportes y sistema',
        'icono': 'fas fa-sliders-h',
        'items': (
            {
                'clave': 'reportes',
                'etiqueta': 'Reportes',
                'icono': 'fas fa-chart-bar',
                'ruta': '/reportes',
                'endpoint': 'reportes.listar',
                'palabras_clave': 'reportes informes estadisticas consultas',
            },
            {
                'clave': 'intercambio',
                'etiqueta': 'Intercambio',
                'icono': 'fas fa-exchange-alt',
                'ruta': '/intercambio',
                'endpoint': 'intercambio.listar',
                'palabras_clave': 'intercambio interfase integracion importacion',
            },
            {
                'clave': 'parametros',
                'etiqueta': 'Parámetros',
                'icono': 'fas fa-sliders-h',
                'ruta': '/parametros',
                'endpoint': 'parametros.parametros',
                'palabras_clave': 'parametros configuracion ajustes',
            },
            {
                'clave': 'estado',
                'etiqueta': 'Info del sistema',
                'icono': 'fas fa-info-circle',
                'ruta': '/estado',
                'endpoint': 'estado',
                'palabras_clave': 'estado info sistema salud',
            },
            {
                'clave': 'manual',
                'etiqueta': 'Manual de usuario',
                'icono': 'fas fa-book-open',
                'ruta': '/manual',
                'endpoint': 'manual',
                'palabras_clave': 'manual ayuda guia documentacion tutorial como usar',
            },
        ),
    },
)

SECCIONES_CLAVES = tuple(seccion['clave'] for seccion in NAVEGACION)
ITEMS_POR_RUTA = {
    item['ruta']: item
    for seccion in NAVEGACION
    for item in seccion['items']
}
RUTAS_VALIDAS = frozenset(ITEMS_POR_RUTA)


def _preferencias_vacias():
    return {PREF_MODO: 'expandido', PREF_FAVORITOS: []}


def normalizar_preferencias(preferencias):
    """Convierte el JSON guardado en un dict de preferencias válido.

    Acepta el formato plano histórico (``{seccion: bool}``), una cadena JSON y
    valores corruptos (devuelve los valores por defecto). No muta el argumento
    recibido y siempre incluye las claves reservadas.
    """

    if isinstance(preferencias, str):
        try:
            preferencias = json.loads(preferencias)
        except (TypeError, ValueError):
            return _preferencias_vacias()
    if not isinstance(preferencias, dict):
        return _preferencias_vacias()

    limpias = {
        str(clave): valor
        for clave, valor in preferencias.items()
        if clave in SECCIONES_CLAVES or clave in (PREF_MODO, PREF_FAVORITOS)
    }
    for vieja, nueva in SECCIONES_LEGADO.items():
        if vieja in preferencias and nueva not in limpias:
            limpias[nueva] = bool(preferencias[vieja])

    limpias[PREF_MODO] = (
        'rail' if preferencias.get(PREF_MODO) == 'rail' else 'expandido'
    )

    favoritos = preferencias.get(PREF_FAVORITOS) or []
    if isinstance(favoritos, str):
        try:
            favoritos = json.loads(favoritos)
        except (TypeError, ValueError):
            favoritos = []
    if not isinstance(favoritos, list):
        favoritos = []
    limpias[PREF_FAVORITOS] = [
        ruta for ruta in favoritos[:MAX_FAVORITOS]
        if isinstance(ruta, str) and ruta in RUTAS_VALIDAS
    ]
    return limpias


def es_activo(ruta_actual, ruta_item):
    """Marca el destino actual, incluidas las subrutas del mismo módulo."""

    if not ruta_actual or not ruta_item:
        return False
    if ruta_actual == ruta_item:
        return True
    return ruta_item != '/' and ruta_actual.startswith(ruta_item + '/')


def construir_navegacion(tiene_permiso, ruta_actual='', preferencias=None):
    """Devuelve el menú visible para el usuario actual.

    ``tiene_permiso(ruta)`` es un callable que decide si el rol puede ver ese
    destino. La sección activa se expande aunque el usuario la tenga cerrada,
    para que el ítem resaltado nunca quede oculto.
    """

    prefs = normalizar_preferencias(preferencias)
    modo = prefs[PREF_MODO]
    favoritos = prefs[PREF_FAVORITOS]

    def preparar(item):
        return {
            'clave': item['clave'],
            'etiqueta': item['etiqueta'],
            'icono': item['icono'],
            'ruta': item['ruta'],
            'endpoint': item['endpoint'],
            # Sinónimos del negocio para que "existencias", "orden" o
            # "transferencias" encuentren los destinos correctos.
            'buscar': ' '.join(filter(None, (
                item['etiqueta'],
                item['ruta'],
                item.get('palabras_clave', ''),
            ))),
            'activo': es_activo(ruta_actual, item['ruta']),
            'favorito': item['ruta'] in favoritos,
        }

    secciones = []
    for seccion in NAVEGACION:
        if seccion['clave'] == 'favoritos':
            continue
        items = [
            preparar(item)
            for item in seccion['items']
            if tiene_permiso(item['ruta'])
        ]
        if not items:
            continue
        secciones.append({
            'clave': seccion['clave'],
            'etiqueta': seccion['etiqueta'],
            'icono': seccion['icono'],
            'directo': seccion.get('directo', False),
            'items': items,
            'total': len(items),
            'expandida': bool(prefs.get(seccion['clave'])) or any(
                item['activo'] for item in items
            ),
        })

    items_favoritos = []
    vistos = set()
    for ruta in favoritos:
        item = ITEMS_POR_RUTA.get(ruta)
        if item and ruta not in vistos and tiene_permiso(ruta):
            items_favoritos.append(preparar(item))
            vistos.add(ruta)

    seccion_favoritos = {
        'clave': 'favoritos',
        'etiqueta': 'Favoritos',
        'icono': 'fas fa-star',
        'directo': False,
        'items': items_favoritos,
        'total': len(items_favoritos),
        'expandida': True,
    }

    # Los favoritos van justo debajo de Inicio: son atajos, no una sección más.
    indice_inicio = next(
        (i for i, seccion in enumerate(secciones) if seccion['clave'] == 'inicio'),
        -1,
    )
    secciones.insert(indice_inicio + 1, seccion_favoritos)

    return {
        'secciones': secciones,
        'favoritos': items_favoritos,
        'favoritos_paths': tuple(vistos),
        'modo': modo,
        'ruta_actual': ruta_actual,
        'total_destinos': sum(len(seccion['items']) for seccion in secciones),
    }
