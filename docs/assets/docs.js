/*
 * Taurus WMS — navegación de la documentación.
 *
 * NAV es la única fuente del índice: de acá salen el menú lateral, el mapa de
 * la portada y los enlaces anterior/siguiente. Para agregar una página:
 *   1. Copiar docs/_plantilla.html a la carpeta de la sección.
 *   2. Ajustar data-root y data-page en su <body>.
 *   3. Agregarla acá con su estado: 'completa' | 'borrador' | 'pendiente'.
 */
(function () {
    var NAV = [
        {
            titulo: 'Primeros pasos',
            paginas: [
                { href: 'inicio/instalacion.html', titulo: 'Instalación', estado: 'completa',
                  desc: 'Requisitos, entorno, creación de las bases y arranque.' },
                { href: 'inicio/configuracion.html', titulo: 'Configuración (.env)', estado: 'completa',
                  desc: 'Variables de entorno, secretos y cachés.' },
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
                { href: 'administracion/panel-admin.html', titulo: 'Panel admin', estado: 'pendiente',
                  desc: 'Tenants, usuarios, roles y parámetros.' },
                { href: 'administracion/superusuario.html', titulo: 'Superusuario (exe)', estado: 'completa',
                  desc: 'Ejecutable portable para gestionar los usuarios del panel.' },
                { href: 'administracion/migraciones.html', titulo: 'Schema y migraciones', estado: 'completa',
                  desc: 'Generador de schema y migration runner.' }
            ]
        },
        {
            titulo: 'Módulos del WMS',
            paginas: [
                { href: 'modulos/index.html', titulo: 'Catálogo de módulos', estado: 'borrador',
                  desc: 'Listado de módulos y estado de su documentación.' }
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

    // Menú lateral
    var sidebar = document.getElementById('sidebar');
    if (sidebar) {
        var inicio = el('a', { href: root + 'index.html' }, ['Inicio']);
        if (actual === 'index.html') { inicio.className = 'activo'; }
        sidebar.appendChild(el('ul', {}, [el('li', {}, [inicio])]));
        NAV.forEach(function (grupo) {
            sidebar.appendChild(el('div', { 'class': 'grupo' }, [grupo.titulo]));
            var lista = el('ul', {});
            grupo.paginas.forEach(function (p) {
                var hijos = [p.titulo];
                if (p.estado !== 'completa') { hijos.push(badge(p.estado)); }
                var enlace = el('a', { href: root + p.href }, hijos);
                if (p.href === actual) { enlace.className = 'activo'; }
                lista.appendChild(el('li', {}, [enlace]));
            });
            sidebar.appendChild(lista);
        });
    }

    // Mapa de la portada
    var mapa = document.getElementById('mapa');
    if (mapa) {
        NAV.forEach(function (grupo) {
            var lista = el('ul', {});
            grupo.paginas.forEach(function (p) {
                lista.appendChild(el('li', {}, [
                    el('a', { href: root + p.href }, [p.titulo, badge(p.estado)]),
                    el('p', {}, [p.desc])
                ]));
            });
            mapa.appendChild(el('div', { 'class': 'tarjeta' }, [el('h3', {}, [grupo.titulo]), lista]));
        });
    }

    // Anterior / siguiente
    var pager = document.getElementById('pager');
    if (pager) {
        var plano = [{ href: 'index.html', titulo: 'Inicio' }];
        NAV.forEach(function (grupo) { plano = plano.concat(grupo.paginas); });
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
