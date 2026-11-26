/* Comportamiento del menú lateral: riel, búsqueda, favoritos y drawer móvil.
   El estado activo y los permisos vienen del servidor; acá sólo se manipula la
   presentación y se guardan las preferencias del usuario. */

(function () {
    'use strict';

    var sidebar = document.getElementById('sidebar-principal');
    if (!sidebar) return;

    var urlPreferencias = sidebar.getAttribute('data-preferences-url') || '/sidebar-preferences';

    var preferencias = {};
    try {
        preferencias = JSON.parse(sidebar.getAttribute('data-preferencias') || '{}') || {};
    } catch (error) {
        preferencias = {};
    }

    var modo = preferencias._modo === 'rail' ? 'rail' : 'expandido';
    var favoritos = Array.isArray(preferencias._favoritos) ? preferencias._favoritos.slice() : [];
    var MAX_FAVORITOS = 6;
    var movil = window.matchMedia('(max-width: 768px)');

    var botonMovil = document.getElementById('btn-menu-movil');
    var backdrop = document.getElementById('sidebar-backdrop');
    var buscador = document.getElementById('sidebar-buscar');
    var resultados = sidebar.querySelector('#sidebar-resultados');
    var estadoGuardado = sidebar.querySelector('#sidebar-estado');
    var sinResultados = sidebar.querySelector('.sidebar-no-resultados');
    var secciones = Array.prototype.slice.call(sidebar.querySelectorAll('.sidebar-section'));

    // ---- Guardado de preferencias -----------------------------------------
    var colaGuardado = Promise.resolve();
    var temporizadorEstado;

    function mostrarEstado(texto) {
        if (!estadoGuardado) return;
        estadoGuardado.textContent = texto;
        estadoGuardado.hidden = false;
        window.clearTimeout(temporizadorEstado);
        temporizadorEstado = window.setTimeout(function () {
            estadoGuardado.hidden = true;
            estadoGuardado.textContent = '';
        }, 4000);
    }

    // En cola para que varios cambios rápidos no se pisen entre sí, y sin
    // recargar la página si falla la conexión: se conserva el estado en sesión.
    function guardar(cambios) {
        colaGuardado = colaGuardado.then(function () {
            return fetch(urlPreferencias, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(cambios)
            }).then(function (respuesta) {
                if (!respuesta.ok) throw new Error('No se pudieron guardar las preferencias');
                return respuesta.json();
            });
        }).catch(function (error) {
            console.warn('[sidebar]', error);
            mostrarEstado('No se pudo guardar el cambio; sigue activo en esta sesión.');
        });
        return colaGuardado;
    }

    function aplicarModo() {
        document.body.classList.toggle('sidebar-rail', modo === 'rail' && !movil.matches);
        document.body.classList.toggle('sidebar-drawer', movil.matches);

        var boton = sidebar.querySelector('.sidebar-mode-btn');
        if (boton) {
            var contraer = modo === 'expandido';
            var etiqueta = contraer ? 'Contraer menú a iconos' : 'Expandir menú';
            boton.setAttribute('aria-label', etiqueta);
            boton.setAttribute('title', etiqueta);
            boton.setAttribute('data-tooltip', etiqueta);
            boton.innerHTML = '<i class="fas fa-' +
                (contraer ? 'angle-double-left' : 'angle-double-right') +
                '" aria-hidden="true"></i>';
        }
        ocultarTooltip();
    }

    // ---- Tooltip del riel -------------------------------------------------
    var tooltip = document.createElement('div');
    tooltip.id = 'sidebar-tooltip';
    tooltip.hidden = true;
    document.body.appendChild(tooltip);

    function mostrarTooltip(elemento) {
        if (!document.body.classList.contains('sidebar-rail')) return;
        var texto = elemento.getAttribute('data-tooltip') ||
            elemento.getAttribute('aria-label') ||
            elemento.textContent.trim();
        if (!texto) return;
        tooltip.textContent = texto;
        var rect = elemento.getBoundingClientRect();
        tooltip.hidden = false;
        tooltip.style.left = (rect.right + 10) + 'px';
        tooltip.style.top = (rect.top + rect.height / 2 - tooltip.offsetHeight / 2) + 'px';
    }

    function ocultarTooltip() {
        tooltip.hidden = true;
    }

    sidebar.addEventListener('mouseover', function (evento) {
        var destino = evento.target.closest('.sidebar-link, .sidebar-mode-btn');
        if (destino) mostrarTooltip(destino);
    });
    sidebar.addEventListener('mouseout', function (evento) {
        var destino = evento.target.closest('.sidebar-link, .sidebar-mode-btn');
        if (destino && !destino.contains(evento.relatedTarget)) ocultarTooltip();
    });
    sidebar.addEventListener('focusin', function (evento) {
        var destino = evento.target.closest('.sidebar-link, .sidebar-mode-btn');
        if (destino) mostrarTooltip(destino);
    });
    sidebar.addEventListener('focusout', ocultarTooltip);
    window.addEventListener('scroll', ocultarTooltip, true);

    // ---- Contraer / expandir ----------------------------------------------
    var botonModo = sidebar.querySelector('.sidebar-mode-btn');
    if (botonModo) {
        botonModo.addEventListener('click', function () {
            modo = modo === 'rail' ? 'expandido' : 'rail';
            aplicarModo();
            guardar({ modo: modo });
        });
    }

    // ---- Acordeones --------------------------------------------------------
    sidebar.querySelectorAll('.sidebar-toggle').forEach(function (boton) {
        boton.addEventListener('click', function () {
            var clave = boton.getAttribute('data-section');
            var submenu = document.getElementById('section-' + clave);
            if (!submenu) return;
            var abierto = boton.getAttribute('aria-expanded') !== 'true';
            boton.setAttribute('aria-expanded', String(abierto));
            submenu.hidden = !abierto;
            guardar({ section: clave, value: abierto });
        });
    });

    // ---- Favoritos ---------------------------------------------------------
    function actualizarEstrella(ruta, activo) {
        sidebar.querySelectorAll('.fav-btn[data-favorito]').forEach(function (boton) {
            if (boton.getAttribute('data-favorito') !== ruta) return;
            boton.setAttribute('aria-pressed', String(activo));
            boton.setAttribute('title', activo ? 'Quitar de favoritos' : 'Fijar en favoritos');
            var icono = boton.querySelector('i');
            if (icono) icono.className = activo ? 'fas fa-star' : 'far fa-star';
        });
    }

    function actualizarFavoritos(ruta, activo) {
        var submenu = document.getElementById('section-favoritos');
        if (!submenu) return;
        var selector = '.sidebar-item-row[data-ruta="' + ruta + '"]';
        var copias = submenu.querySelectorAll(selector);

        if (activo) {
            if (!copias.length && favoritos.length <= MAX_FAVORITOS) {
                var original = sidebar.querySelector(
                    '.sidebar-section:not([data-seccion="favoritos"]) ' + selector
                );
                if (original) {
                    var copia = original.cloneNode(true);
                    // La página activa sólo puede tener un aria-current en el DOM.
                    var copiaActiva = copia.querySelector('.sidebar-link.active');
                    if (copiaActiva) copiaActiva.removeAttribute('aria-current');
                    submenu.appendChild(copia);
                }
            }
        } else {
            copias.forEach(function (fila) { fila.remove(); });
        }

        var hueco = sidebar.querySelector('.favoritos-vacio');
        if (hueco) hueco.hidden = submenu.querySelectorAll('.sidebar-item-row').length > 0;
        actualizarEstrella(ruta, activo);
    }

    sidebar.addEventListener('click', function (evento) {
        var boton = evento.target.closest('.fav-btn');
        if (!boton) return;
        evento.preventDefault();
        evento.stopPropagation();

        var ruta = boton.getAttribute('data-favorito');
        var indice = favoritos.indexOf(ruta);
        var activo = indice === -1;

        if (activo) {
            if (favoritos.length >= MAX_FAVORITOS) {
                mostrarEstado('Máximo ' + MAX_FAVORITOS + ' favoritos.');
                return;
            }
            favoritos.push(ruta);
        } else {
            favoritos.splice(indice, 1);
        }

        actualizarFavoritos(ruta, activo);
        guardar({ favorito: ruta, value: activo });
    });

    // ---- Buscar en el menú -------------------------------------------------
    function normalizar(texto) {
        return (texto || '').toLowerCase()
            .normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    }

    var estadoAcordeones = null;

    function filtrar() {
        if (!buscador) return;
        var consulta = normalizar(buscador.value.trim());
        var hayResultados = false;
        var total = 0;

        if (consulta && !estadoAcordeones) {
            estadoAcordeones = {};
            sidebar.querySelectorAll('.sidebar-toggle').forEach(function (boton) {
                estadoAcordeones[boton.getAttribute('data-section')] =
                    boton.getAttribute('aria-expanded') === 'true';
            });
        }

        secciones.forEach(function (seccion) {
            var filas = seccion.querySelectorAll('.sidebar-item-row');
            var coincideSeccion = consulta &&
                normalizar(seccion.getAttribute('data-etiqueta')).indexOf(consulta) !== -1;
            var visibles = 0;

            filas.forEach(function (fila) {
                var texto = normalizar(fila.getAttribute('data-buscar'));
                var mostrar = !consulta || coincideSeccion || texto.indexOf(consulta) !== -1;
                fila.hidden = !mostrar;
                if (mostrar) { visibles++; total++; }
            });

            var mostrarSeccion = visibles > 0;
            seccion.classList.toggle('is-hidden', !mostrarSeccion);
            if (mostrarSeccion) hayResultados = true;

            var submenu = seccion.querySelector('.sidebar-submenu');
            var toggle = seccion.querySelector('.sidebar-toggle');
            if (consulta && submenu && toggle) {
                submenu.hidden = false;
                toggle.setAttribute('aria-expanded', 'true');
            } else if (submenu && toggle) {
                var clave = toggle.getAttribute('data-section');
                var abierto = estadoAcordeones
                    ? estadoAcordeones[clave] === true
                    : toggle.getAttribute('aria-expanded') === 'true';
                toggle.setAttribute('aria-expanded', String(abierto));
                submenu.hidden = !abierto;
            }
        });

        if (!consulta) estadoAcordeones = null;
        if (sinResultados) sinResultados.hidden = !consulta || hayResultados;
        if (resultados) {
            resultados.hidden = !consulta;
            resultados.textContent = !consulta ? ''
                : (total === 1 ? '1 resultado' : total + ' resultados');
        }
        ocultarTooltip();
    }

    function enlacesVisibles() {
        return Array.prototype.filter.call(
            sidebar.querySelectorAll('.sidebar-item-row:not([hidden]) .sidebar-link'),
            function (enlace) {
                var fila = enlace.closest('.sidebar-item-row');
                var seccion = fila && fila.closest('.sidebar-section');
                return !!seccion && !seccion.classList.contains('is-hidden') &&
                    enlace.offsetParent !== null;
            }
        );
    }

    function moverResultado(direccion) {
        var enlaces = enlacesVisibles();
        if (!enlaces.length) return;
        var actual = enlaces.indexOf(document.activeElement);
        var destino = direccion > 0
            ? (actual + 1) % enlaces.length
            : (actual <= 0 ? enlaces.length - 1 : actual - 1);
        enlaces[destino].focus();
    }

    if (buscador) {
        buscador.addEventListener('input', filtrar);
        buscador.addEventListener('keydown', function (evento) {
            if (evento.key === 'Escape' && buscador.value) {
                buscador.value = '';
                filtrar();
                evento.stopPropagation();
                return;
            }
            if (evento.key === 'ArrowDown' || evento.key === 'ArrowUp') {
                evento.preventDefault();
                moverResultado(evento.key === 'ArrowDown' ? 1 : -1);
                return;
            }
            if (evento.key === 'Enter') {
                var enlaces = enlacesVisibles();
                if (enlaces.length) {
                    evento.preventDefault();
                    enlaces[0].click();
                }
            }
        });
    }

    // Las flechas siguen funcionando cuando el foco ya está en un resultado.
    sidebar.addEventListener('keydown', function (evento) {
        if (evento.target === buscador || !buscador || !buscador.value) return;
        if (evento.key !== 'ArrowDown' && evento.key !== 'ArrowUp') return;
        var enlaces = enlacesVisibles();
        if (enlaces.indexOf(document.activeElement) === -1) return;
        evento.preventDefault();
        moverResultado(evento.key === 'ArrowDown' ? 1 : -1);
    });

    // ---- Drawer móvil ------------------------------------------------------
    function abrirDrawer() {
        document.body.classList.add('nav-abierto');
        if (backdrop) backdrop.hidden = false;
        if (botonMovil) botonMovil.setAttribute('aria-expanded', 'true');
        var primero = sidebar.querySelector('a[href], button');
        if (primero) primero.focus();
    }

    function cerrarDrawer(devolverFoco) {
        document.body.classList.remove('nav-abierto');
        if (backdrop) backdrop.hidden = true;
        if (botonMovil) {
            botonMovil.setAttribute('aria-expanded', 'false');
            if (devolverFoco) botonMovil.focus();
        }
    }

    if (botonMovil) {
        botonMovil.addEventListener('click', function () {
            if (document.body.classList.contains('nav-abierto')) cerrarDrawer(true);
            else abrirDrawer();
        });
    }
    if (backdrop) backdrop.addEventListener('click', function () { cerrarDrawer(true); });

    sidebar.addEventListener('click', function (evento) {
        if (movil.matches && evento.target.closest('a.sidebar-link')) cerrarDrawer(false);
    });

    document.addEventListener('keydown', function (evento) {
        if (evento.key === '/' && !evento.ctrlKey && !evento.metaKey && !evento.altKey) {
            var objetivo = evento.target;
            if (objetivo && (objetivo.isContentEditable ||
                    /^(INPUT|TEXTAREA|SELECT)$/.test(objetivo.tagName || ''))) return;
            if (!buscador || !buscador.offsetParent) return;
            evento.preventDefault();
            if (document.body.classList.contains('sidebar-drawer') &&
                    !document.body.classList.contains('nav-abierto')) abrirDrawer();
            buscador.focus();
            buscador.select();
            return;
        }
        if (evento.key === 'Escape' && document.body.classList.contains('nav-abierto')) {
            cerrarDrawer(true);
            return;
        }
        if (evento.key !== 'Tab' || !document.body.classList.contains('nav-abierto')) return;

        var enfocables = Array.prototype.filter.call(
            sidebar.querySelectorAll('a[href], button:not([disabled]), input'),
            function (elemento) { return elemento.offsetParent !== null; }
        );
        if (!enfocables.length) return;
        var primero = enfocables[0];
        var ultimo = enfocables[enfocables.length - 1];

        if (evento.shiftKey && document.activeElement === primero) {
            evento.preventDefault();
            ultimo.focus();
        } else if (!evento.shiftKey && document.activeElement === ultimo) {
            evento.preventDefault();
            primero.focus();
        }
    });

    function alCambiarViewport() {
        aplicarModo();
        if (!movil.matches) cerrarDrawer(false);
    }
    if (movil.addEventListener) movil.addEventListener('change', alCambiarViewport);
    else movil.addListener(alCambiarViewport);

    aplicarModo();
    filtrar();
})();
