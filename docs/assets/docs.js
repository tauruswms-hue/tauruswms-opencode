/*
 * Taurus WMS — navegación de la documentación.
 *
 * NAV es la única fuente del índice: de acá salen el menú lateral, el mapa de
 * la portada y los enlaces anterior/siguiente. Para agregar una página:
 *   1. Copiar docs/_plantilla.html a la carpeta de la sección.
 *   2. Ajustar data-root y data-page en su <body>.
 *   3. Agregarla acá con su estado: 'completa' | 'borrador' | 'pendiente'.
 * Una página puede tener subpáginas en `hijos` (se anidan en el menú).
 */
(function () {
    var NAV = [
        {
            titulo: 'Primeros pasos',
            paginas: [
                { href: 'inicio/instalacion.html', titulo: 'Instalación', estado: 'completa',
                  desc: 'Requisitos, entorno, creación de las bases y arranque.',
                  hijos: [
                      { href: 'inicio/base-de-datos/index.html', titulo: 'Base de datos', estado: 'completa',
                        desc: 'Creación de las tres bases en MySQL.',
                        hijos: [
                            { href: 'inicio/base-de-datos/taurus-admin.html', titulo: 'taurus_admin', estado: 'completa',
                              desc: 'Script de creación de la base administrativa.' },
                            { href: 'inicio/base-de-datos/superusuario.html', titulo: 'Superusuario (exe)', estado: 'completa',
                              desc: 'Alta del primer usuario del panel admin.' },
                            { href: 'inicio/base-de-datos/taurus-wms.html', titulo: 'taurus_wms', estado: 'completa',
                              desc: 'Script de creación de la base operativa.' },
                            { href: 'inicio/base-de-datos/taurus-intercambio.html', titulo: 'taurus_intercambio', estado: 'completa',
                              desc: 'Script de creación de la base de intercambio.' }
                        ] }
                  ] },
                { href: 'inicio/configuracion.html', titulo: 'Configuración', estado: 'completa',
                  desc: 'Archivo de conexiones a las bases, entorno y secretos.' },
                { href: 'inicio/docker.html', titulo: 'Docker', estado: 'borrador',
                  desc: 'Entorno de desarrollo con docker compose.' }
            ]
        },
        {
            titulo: 'Arquitectura',
            paginas: [
                { href: 'arquitectura/vision-general.html', titulo: 'Visión general', estado: 'completa',
                  desc: 'Las apps, los blueprints y los módulos transversales.' },
                { href: 'arquitectura/base-de-datos.html', titulo: 'Base de datos', estado: 'completa',
                  desc: 'Motores soportados, las tres bases, conexiones y pool.' },
                { href: 'arquitectura/multi-tenancy.html', titulo: 'Multi-tenancy', estado: 'completa',
                  desc: 'Cómo se aíslan los datos de cada tenant.' },
                { href: 'arquitectura/roles-permisos.html', titulo: 'Roles y permisos', estado: 'completa',
                  desc: 'Catálogo de rutas, asignación por rol y verificación.' }
            ]
        },
        {
            titulo: 'Administración',
            paginas: [
                { href: 'administracion/panel-admin.html', titulo: 'Panel admin', estado: 'completa',
                  desc: 'Tenants, usuarios, roles, parámetros, configuración y auditoría.' },
                { href: 'administracion/migraciones.html', titulo: 'Schema y migraciones', estado: 'completa',
                  desc: 'Generador de schema y migration runner.' }
            ]
        },
        {
            titulo: 'Módulos del WMS',
            paginas: [
                { href: 'modulos/index.html', titulo: 'Catálogo de módulos', estado: 'borrador',
                  desc: 'Listado de módulos y estado de su documentación.' },
                { href: 'modulos/flujo-stock.html', titulo: 'Flujo operativo y stock', estado: 'completa',
                  desc: 'El circuito de la mercadería y las reglas de stock.' },
                { href: 'modulos/recepciones.html', titulo: 'Recepciones', estado: 'completa',
                  desc: 'Ingreso de mercadería de proveedores.' },
                { href: 'modulos/omc.html', titulo: 'OMC', estado: 'completa',
                  desc: 'Órdenes de movimiento entre ubicaciones.' },
                { href: 'modulos/pedidos.html', titulo: 'Pedidos', estado: 'completa',
                  desc: 'Carga y preparación de pedidos de clientes.' },
                { href: 'modulos/despacho.html', titulo: 'Despacho', estado: 'completa',
                  desc: 'Salida de los pedidos preparados.' },
                { href: 'modulos/movil.html', titulo: 'Móvil', estado: 'completa',
                  desc: 'Recepción, picking e inventario con lector.' }
            ]
        },
        {
            titulo: 'Integraciones',
            paginas: [
                { href: 'integraciones/intercambio.html', titulo: 'Intercambio', estado: 'completa',
                  desc: 'Interfase por tablas con sistemas externos.' },
                { href: 'integraciones/api.html', titulo: 'API REST', estado: 'borrador',
                  desc: 'API JSON /api/v1 con token por tenant.' }
            ]
        },
        {
            titulo: 'Operación',
            paginas: [
                { href: 'operacion/produccion.html', titulo: 'Puesta en producción', estado: 'borrador',
                  desc: 'Lista de verificación antes de salir a producción.' }
            ]
        },
        {
            titulo: 'Desarrollo',
            paginas: [
                { href: 'desarrollo/tests-ci.html', titulo: 'Tests, lint y CI', estado: 'completa',
                  desc: 'pytest, ruff, CI y convenciones del código.' }
            ]
        }
    ];

    var ESTADOS = { completa: 'Completa', borrador: 'Borrador', pendiente: 'Pendiente' };

    var body = document.body;
    var root = body.getAttribute('data-root') || '';
    var actual = body.getAttribute('data-page') || 'index.html';

    function el(tag, attrs, hijos) {
        var nodo = document.createElement(tag);
        Object.keys(attrs || {}).forEach(function (k) { nodo.setAttribute(k, attrs[k]); });
        (hijos || []).forEach(function (h) {
            nodo.appendChild(typeof h === 'string' ? document.createTextNode(h) : h);
        });
        return nodo;
    }

    function badge(estado) {
        return el('span', { 'class': 'estado ' + estado }, [ESTADOS[estado] || estado]);
    }

    // Barra superior
    var boton = el('button', { 'class': 'menu-btn', type: 'button', 'aria-label': 'Abrir menú' }, ['☰']);
    boton.addEventListener('click', function () { body.classList.toggle('nav-abierto'); });
    var marca = el('a', { 'class': 'marca', href: root + 'index.html' }, [
        el('img', { src: root + 'assets/logo.jpg', alt: '' }),
        'Taurus WMS ',
        el('small', {}, ['Documentación'])
    ]);
    body.insertBefore(el('header', { 'class': 'topbar' }, [boton, marca]), body.firstChild);

    // Menú lateral (las páginas con `hijos` se anidan)
    function listaMenu(paginas, anidada) {
        var lista = el('ul', anidada ? { 'class': 'sub' } : {});
        paginas.forEach(function (p) {
            var hijos = [p.titulo];
            if (p.estado !== 'completa') { hijos.push(badge(p.estado)); }
            var enlace = el('a', { href: root + p.href }, hijos);
            if (p.href === actual) { enlace.className = 'activo'; }
            var item = el('li', {}, [enlace]);
            if (p.hijos) { item.appendChild(listaMenu(p.hijos, true)); }
            lista.appendChild(item);
        });
        return lista;
    }

    var sidebar = document.getElementById('sidebar');
    if (sidebar) {
        var inicio = el('a', { href: root + 'index.html' }, ['Inicio']);
        if (actual === 'index.html') { inicio.className = 'activo'; }
        sidebar.appendChild(el('ul', {}, [el('li', {}, [inicio])]));
        NAV.forEach(function (grupo) {
            sidebar.appendChild(el('div', { 'class': 'grupo' }, [grupo.titulo]));
            sidebar.appendChild(listaMenu(grupo.paginas, false));
        });
    }

    // Mapa de la portada
    function listaMapa(paginas, anidada) {
        var lista = el('ul', anidada ? { 'class': 'sub' } : {});
        paginas.forEach(function (p) {
            var item = el('li', {}, [
                el('a', { href: root + p.href }, [p.titulo, badge(p.estado)]),
                el('p', {}, [p.desc])
            ]);
            if (p.hijos) { item.appendChild(listaMapa(p.hijos, true)); }
            lista.appendChild(item);
        });
        return lista;
    }

    var mapa = document.getElementById('mapa');
    if (mapa) {
        NAV.forEach(function (grupo) {
            mapa.appendChild(el('div', { 'class': 'tarjeta' }, [
                el('h3', {}, [grupo.titulo]), listaMapa(grupo.paginas, false)
            ]));
        });
    }

    // Anterior / siguiente (recorre el árbol en orden)
    function aplanar(paginas, destino) {
        paginas.forEach(function (p) {
            destino.push(p);
            if (p.hijos) { aplanar(p.hijos, destino); }
        });
        return destino;
    }

    var pager = document.getElementById('pager');
    if (pager) {
        var plano = [{ href: 'index.html', titulo: 'Inicio' }];
        NAV.forEach(function (grupo) { aplanar(grupo.paginas, plano); });
        var i = plano.map(function (p) { return p.href; }).indexOf(actual);
        var enlace = function (p, rotulo) {
            if (!p) { return el('div', {}); }
            return el('a', { href: root + p.href }, [el('span', {}, [rotulo]), p.titulo]);
        };
        if (i >= 0) {
            pager.appendChild(enlace(plano[i - 1], '← Anterior'));
            pager.appendChild(enlace(plano[i + 1], 'Siguiente →'));
        }
    }
})();
