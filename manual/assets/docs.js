/*
 * Taurus WMS — navegación del manual de usuario.
 *
 * NAV es la única fuente del índice: de acá salen el menú lateral, el mapa de
 * la portada y los enlaces anterior/siguiente. El contenido está escrito para
 * quien opera el depósito: no incluye detalles de implementación.
 */
(function () {
    var NAV = [
        {
            titulo: 'Primeros pasos',
            paginas: [
                { href: 'acceso.html', titulo: 'Ingresar y moverse', estado: 'completa',
                  desc: 'Usuario, contraseña, menú lateral, búsqueda y favoritos.' },
                { href: 'maestros.html', titulo: 'Datos de base', estado: 'completa',
                  desc: 'Materiales, proveedores, clientes, ubicaciones, rutas y transportes.' },
                { href: 'flujo.html', titulo: 'Cómo circula la mercadería', estado: 'completa',
                  desc: 'Del ingreso a la salida: recepción, movimientos, pedidos y despacho.' }
            ]
        },
        {
            titulo: 'Operación diaria',
            paginas: [
                { href: 'recepciones.html', titulo: 'Recepciones', estado: 'completa',
                  desc: 'Registrar lo que llega de un proveedor y dejarlo disponible.' },
                { href: 'movimientos.html', titulo: 'Movimientos (OMC)', estado: 'completa',
                  desc: 'Trasladar contenedores entre ubicaciones y confirmar el destino.' },
                { href: 'pedidos.html', titulo: 'Pedidos', estado: 'completa',
                  desc: 'Cargar pedidos, verificar stock y prepararlos.' },
                { href: 'preparacion.html', titulo: 'Preparación (picking)', estado: 'completa',
                  desc: 'Usar la lista de picking y llevar la mercadería al muelle.' },
                { href: 'despacho.html', titulo: 'Despacho', estado: 'completa',
                  desc: 'Marcar como despachados los pedidos listos.' },
                { href: 'movil.html', titulo: 'Terminal móvil', estado: 'completa',
                  desc: 'Recepción, confirmación y consulta de stock con lector.' }
            ]
        },
        {
            titulo: 'Control y consultas',
            paginas: [
                { href: 'inventarios.html', titulo: 'Inventarios', estado: 'completa',
                  desc: 'Contar el stock y revisar diferencias.' },
                { href: 'reportes.html', titulo: 'Reportes', estado: 'completa',
                  desc: 'Consultar stock, valorización, movimientos, recepciones y pedidos.' },
                { href: 'intercambio.html', titulo: 'Datos de otros sistemas', estado: 'completa',
                  desc: 'Procesar los datos recibidos y reintentar los que dieron error.' }
            ]
        },
        {
            titulo: 'Ayuda',
            paginas: [
                { href: 'incidencias.html', titulo: 'Resolución de incidencias', estado: 'completa',
                  desc: 'Qué hacer cuando una operación no se puede completar.' },
                { href: 'glosario.html', titulo: 'Glosario', estado: 'completa',
                  desc: 'Términos que aparecen en las pantallas.' }
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

    // Encabezados: los que no tienen id reciben uno derivado de su texto, para que el
    // buscador pueda enlazar a cada sección. El generador del índice aplica la misma regla.
    function slug(texto) {
        return texto.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
            .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'seccion';
    }
    (function () {
        var encabezados = document.querySelectorAll('main.content h2, main.content h3');
        var usados = {};
        Array.prototype.forEach.call(encabezados, function (h) { if (h.id) { usados[h.id] = true; } });
        Array.prototype.forEach.call(encabezados, function (h) {
            if (h.id) { return; }
            var base = slug(h.textContent.replace(/\s+/g, ' ').trim()), id = base, n = 1;
            while (usados[id]) { n += 1; id = base + '-' + n; }
            usados[id] = true;
            h.id = id;
        });
        // El navegador ya intentó ir al ancla antes de que existiera: ir ahora
        if (location.hash.length > 1) {
            var destino = document.getElementById(decodeURIComponent(location.hash.slice(1)));
            if (destino) { destino.scrollIntoView(); }
        }
    })();

    // Barra superior
    var boton = el('button', { 'class': 'menu-btn', type: 'button', 'aria-label': 'Abrir menú' }, ['☰']);
    boton.addEventListener('click', function () { body.classList.toggle('nav-abierto'); });
    var marca = el('a', { 'class': 'marca', href: root + 'index.html' }, [
        el('img', { src: root + 'assets/logo.jpg', alt: '' }),
        'Taurus WMS ',
        el('small', {}, ['Manual de usuario'])
    ]);
    var buscadorGeneral = el('input', {
        'class': 'buscador', type: 'search', placeholder: 'Buscar en el manual  ( / )',
        'aria-label': 'Buscar en todo el manual', 'data-grupo': '', autocomplete: 'off'
    });
    body.insertBefore(el('header', { 'class': 'topbar' }, [
        boton, marca, el('div', { 'class': 'buscador-general' }, [buscadorGeneral])
    ]), body.firstChild);

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
            var lupa = el('button', {
                'class': 'lupa', type: 'button', title: 'Buscar en ' + grupo.titulo,
                'aria-label': 'Buscar en ' + grupo.titulo
            }, ['\u2315']);
            var campo = el('input', {
                'class': 'buscador', type: 'search', placeholder: 'Buscar en ' + grupo.titulo,
                'aria-label': 'Buscar en ' + grupo.titulo, 'data-grupo': grupo.titulo, autocomplete: 'off'
            });
            var fila = el('div', { 'class': 'grupo-buscar', hidden: '' }, [campo]);
            lupa.addEventListener('click', (function (fila, campo) {
                return function () {
                    fila.hidden = !fila.hidden;
                    if (!fila.hidden) { campo.focus(); }
                };
            })(fila, campo));
            sidebar.appendChild(el('div', { 'class': 'grupo' }, [grupo.titulo, lupa]));
            sidebar.appendChild(fila);
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
                el('h3', {}, [grupo.titulo]),
                el('input', {
                    'class': 'buscador', type: 'search', placeholder: 'Buscar en ' + grupo.titulo,
                    'aria-label': 'Buscar en ' + grupo.titulo, 'data-grupo': grupo.titulo, autocomplete: 'off'
                }),
                listaMapa(grupo.paginas, false)
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

    // ------------------------------------------------------------------
    // Buscador: general (barra superior) y por sección (menú y portada).
    // Busca en el índice del manual, generado a partir de las páginas.
    // ------------------------------------------------------------------
    var MAX_RESULTADOS = 40;
    var indice = null;          // entradas del índice, una por encabezado de cada página
    var cargando = false;
    var pendiente = null;       // búsqueda pedida mientras se cargaba el índice

    // Sección (grupo de NAV), título y orden de cada página
    var paginas = {};
    (function () {
        var orden = 0;
        function recorrer(lista, grupo) {
            lista.forEach(function (p) {
                paginas[p.href] = { grupo: grupo, titulo: p.titulo, orden: orden++ };
                if (p.hijos) { recorrer(p.hijos, grupo); }
            });
        }
        NAV.forEach(function (g) { recorrer(g.paginas, g.titulo); });
    })();

    function normalizar(texto) {
        return texto.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
    }

    function cargarIndice(alTerminar) {
        if (indice) { alTerminar(); return; }
        pendiente = alTerminar;
        if (cargando) { return; }
        cargando = true;
        var script = el('script', { src: root + 'assets/buscador-indice.js' });
        script.onload = function () {
            indice = (window.DOCS_INDICE || []).map(function (e) {
                var info = paginas[e.p] || { grupo: '', titulo: e.t, orden: 9999 };
                return {
                    href: e.p, ancla: e.a, pagina: e.t || info.titulo, encabezado: e.h, texto: e.x,
                    grupo: info.grupo, orden: info.orden,
                    nPagina: normalizar(e.t), nEncabezado: normalizar(e.h), nTexto: normalizar(e.x)
                };
            });
            if (pendiente) { pendiente(); }
        };
        script.onerror = function () {
            cargando = false;
            mostrarMensaje('No se pudo cargar el índice del buscador. ' +
                'Recargá la página del manual para volver a intentarlo.');
        };
        document.head.appendChild(script);
    }

    function buscar(consulta, grupo) {
        var terminos = normalizar(consulta).split(/\s+/).filter(function (t) { return t.length > 0; });
        var resultados = [];
        indice.forEach(function (e) {
            if (grupo && e.grupo !== grupo) { return; }
            var puntos = 0;
            for (var i = 0; i < terminos.length; i++) {
                var t = terminos[i], p = 0;
                if (e.nEncabezado.indexOf(t) >= 0) { p += 10; }
                if (e.nPagina.indexOf(t) >= 0) { p += 6; }
                if (e.nTexto.indexOf(t) >= 0) { p += 1 + Math.min(e.nTexto.split(t).length - 1, 5) * 0.2; }
                if (!p) { return; }          // tienen que estar todas las palabras
                puntos += p;
            }
            resultados.push({ e: e, puntos: puntos });
        });
        resultados.sort(function (a, b) { return b.puntos - a.puntos || a.e.orden - b.e.orden; });
        return { terminos: terminos, resultados: resultados };
    }

    // Fragmento del texto alrededor de la primera palabra encontrada, con las palabras resaltadas
    function fragmento(e, terminos) {
        var pos = -1;
        terminos.forEach(function (t) {
            var i = e.nTexto.indexOf(t);
            if (i >= 0 && (pos < 0 || i < pos)) { pos = i; }
        });
        var desde = Math.max(0, pos - 60);
        var texto = e.texto.slice(desde, desde + 200);
        var norm = e.nTexto.slice(desde, desde + 200);
        var marcas = [];
        terminos.forEach(function (t) {
            var i = norm.indexOf(t);
            while (i >= 0) { marcas.push([i, i + t.length]); i = norm.indexOf(t, i + t.length); }
        });
        marcas.sort(function (a, b) { return a[0] - b[0]; });
        var nodos = [desde > 0 ? '… ' : ''], cursor = 0;
        marcas.forEach(function (m) {
            if (m[0] < cursor) { return; }
            nodos.push(texto.slice(cursor, m[0]));
            nodos.push(el('mark', {}, [texto.slice(m[0], m[1])]));
            cursor = m[1];
        });
        nodos.push(texto.slice(cursor) + (desde + 200 < e.texto.length ? ' …' : ''));
        return el('span', { 'class': 'fragmento' }, nodos);
    }

    var panel = el('div', { id: 'buscador-panel', hidden: '', role: 'dialog', 'aria-label': 'Resultados de la búsqueda' });
    body.appendChild(panel);

    function cerrarPanel() { panel.hidden = true; }

    function cabecera(texto) {
        var cerrar = el('button', { type: 'button', 'class': 'cerrar', title: 'Cerrar (Esc)', 'aria-label': 'Cerrar' }, ['×']);
        cerrar.addEventListener('click', cerrarPanel);
        return el('div', { 'class': 'cab' }, [el('span', {}, texto), cerrar]);
    }

    function mostrarMensaje(texto) {
        panel.innerHTML = '';
        panel.appendChild(cabecera([texto]));
        panel.hidden = false;
    }

    function mostrar(campo) {
        var consulta = campo.value.trim();
        var grupo = campo.getAttribute('data-grupo');
        if (consulta.length < 2) { cerrarPanel(); return; }
        var r = buscar(consulta, grupo);
        var donde = grupo ? 'la sección ' + grupo : 'todo el manual';
        var total = r.resultados.length;
        panel.innerHTML = '';
        panel.appendChild(cabecera([
            el('strong', {}, [total === 1 ? '1 resultado' : total + ' resultados']),
            ' para "' + consulta + '" en ' + donde +
            (total > MAX_RESULTADOS ? ' (se muestran los primeros ' + MAX_RESULTADOS + ')' : '')
        ]));
        if (!total) {
            panel.appendChild(el('p', { 'class': 'vacio' }, [
                grupo ? 'No hay coincidencias en esta sección. Probar con el buscador general, arriba.'
                      : 'No hay coincidencias. Probar con otras palabras o con menos palabras.'
            ]));
        }
        var lista = el('ul', {});
        r.resultados.slice(0, MAX_RESULTADOS).forEach(function (res) {
            var e = res.e;
            var ruta = [e.grupo, e.pagina].filter(function (x) { return x; }).join(' › ');
            var enlace = el('a', { href: root + e.href + (e.ancla ? '#' + e.ancla : '') }, [
                el('span', { 'class': 'titulo' }, [e.encabezado || e.pagina]),
                el('span', { 'class': 'ruta' }, [ruta]),
                fragmento(e, r.terminos)
            ]);
            enlace.addEventListener('click', cerrarPanel);
            lista.appendChild(el('li', {}, [enlace]));
        });
        panel.appendChild(lista);
        panel.hidden = false;
        panel.scrollTop = 0;
    }

    Array.prototype.forEach.call(document.querySelectorAll('input.buscador'), function (campo) {
        campo.addEventListener('focus', function () { cargarIndice(function () { mostrar(campo); }); });
        campo.addEventListener('input', function () { cargarIndice(function () { mostrar(campo); }); });
        campo.addEventListener('keydown', function (ev) {
            var enlaces = panel.querySelectorAll('li a');
            if (ev.key === 'ArrowDown' && enlaces.length) { ev.preventDefault(); enlaces[0].focus(); }
            if (ev.key === 'Enter' && enlaces.length) { ev.preventDefault(); enlaces[0].click(); }
        });
    });

    // Flechas para recorrer los resultados
    panel.addEventListener('keydown', function (ev) {
        if (ev.key !== 'ArrowDown' && ev.key !== 'ArrowUp') { return; }
        var enlaces = Array.prototype.slice.call(panel.querySelectorAll('li a'));
        var i = enlaces.indexOf(document.activeElement);
        var otro = enlaces[i + (ev.key === 'ArrowDown' ? 1 : -1)];
        if (otro) { ev.preventDefault(); otro.focus(); }
    });

    document.addEventListener('keydown', function (ev) {
        var escribiendo = /^(INPUT|TEXTAREA|SELECT)$/.test((ev.target.tagName || ''));
        if (ev.key === 'Escape') { cerrarPanel(); if (escribiendo) { ev.target.blur(); } }
        if (ev.key === '/' && !escribiendo) { ev.preventDefault(); buscadorGeneral.focus(); buscadorGeneral.select(); }
    });

    // Clic fuera del panel y de los campos: cerrar
    document.addEventListener('click', function (ev) {
        if (panel.hidden || panel.contains(ev.target)) { return; }
        if (ev.target.classList && (ev.target.classList.contains('buscador') || ev.target.classList.contains('lupa'))) { return; }
        cerrarPanel();
    });
})();
