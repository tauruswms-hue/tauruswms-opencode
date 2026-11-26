/*
 * ui.js — comportamiento compartido de la interfaz WMS.
 *
 * Centraliza tres cosas que antes se resolvían en cada plantilla:
 *  - notificaciones (aria-live, cierre explícito, auto-ocultado sóLO de éxito/info);
 *  - modales: rol ARIA, Escape, foco inicial, trampa de Tab y retorno de foco;
 *  - utilidades para estados de carga y texto escapado.
 *
 * No cambia endpoints ni reemplaza las funciones openModal/closeModal de cada
 * módulo: observa el cambio de visibilidad de .modal-overlay y se adapta a ellas.
 */

(function () {
    'use strict';

    var UI = window.TaurusUI = window.TaurusUI || {};

    // ---- Notificaciones ----------------------------------------------------
    var ICONOS = {
        success: 'circle-check',
        error: 'circle-exclamation',
        warning: 'triangle-exclamation',
        info: 'circle-info'
    };

    function esVisible(elemento) {
        if (!elemento || elemento.hidden) return false;
        var estilo = window.getComputedStyle ? window.getComputedStyle(elemento) : null;
        if (!estilo || estilo.display === 'none' || estilo.visibility === 'hidden') return false;
        // offsetParent es null en position:fixed (justo el caso de los modales).
        var rect = elemento.getBoundingClientRect ? elemento.getBoundingClientRect() : null;
        return !rect || rect.width > 0 || rect.height > 0;
    }

    function ocultar(flash) {
        if (!flash || flash.dataset.uiCerrando) return;
        flash.dataset.uiCerrando = '1';
        flash.style.transition = 'opacity .25s ease, transform .25s ease';
        flash.style.opacity = '0';
        flash.style.transform = 'translateY(-6px)';
        window.setTimeout(function () { flash.remove(); }, 250);
    }

    function iniciarFlash(flash) {
        if (!flash || flash.dataset.uiListo) return;
        flash.dataset.uiListo = '1';

        var categoria = flash.getAttribute('data-flash') || 'info';
        // Errores y advertencias NO se borran solos: el usuario necesita leerlos
        // y corregir el formulario con el mensaje todavía visible (WCAG 2.2.1).
        if (categoria !== 'success' && categoria !== 'info') return;

        var temporizador;
        function programar(milis) {
            window.clearTimeout(temporizador);
            temporizador = window.setTimeout(function () { ocultar(flash); }, milis);
        }
        programar(7000);
        flash.addEventListener('mouseenter', function () { window.clearTimeout(temporizador); });
        flash.addEventListener('focusin', function () { window.clearTimeout(temporizador); });
        flash.addEventListener('mouseleave', function () { programar(2500); });
        flash.addEventListener('focusout', function () { programar(2500); });
    }

    function iniciarFlashes(root) {
        (root || document).querySelectorAll('[data-flash]').forEach(iniciarFlash);
    }

    document.addEventListener('click', function (evento) {
        var boton = evento.target.closest('[data-flash-cerrar]');
        if (!boton) return;
        var flash = boton.closest('[data-flash]');
        if (flash) ocultar(flash);
    });

    UI.notificar = function (mensaje, categoria) {
        var cat = categoria === 'danger' ? 'error' : (categoria || 'info');
        var contenedor = document.querySelector('[data-flash-container]');
        if (!contenedor) {
            contenedor = document.createElement('div');
            contenedor.className = 'flash-messages';
            contenedor.setAttribute('data-flash-container', '');
            contenedor.setAttribute('aria-live', 'polite');
            document.body.appendChild(contenedor);
        }
        var flash = document.createElement('div');
        flash.className = 'flash flash-' + cat;
        flash.setAttribute('data-flash', cat);
        flash.setAttribute('role', cat === 'error' || cat === 'warning' ? 'alert' : 'status');

        var icono = document.createElement('i');
        icono.className = 'fas fa-' + (ICONOS[cat] || ICONOS.info);
        icono.setAttribute('aria-hidden', 'true');
        var texto = document.createElement('span');
        texto.className = 'flash-texto';
        texto.textContent = mensaje;
        var cerrar = document.createElement('button');
        cerrar.type = 'button';
        cerrar.className = 'flash-cerrar';
        cerrar.setAttribute('data-flash-cerrar', '');
        cerrar.setAttribute('aria-label', 'Cerrar mensaje');
        cerrar.innerHTML = '<i class="fas fa-times" aria-hidden="true"></i>';

        flash.appendChild(icono);
        flash.appendChild(texto);
        flash.appendChild(cerrar);
        contenedor.appendChild(flash);
        iniciarFlash(flash);
        return flash;
    };

    // ---- Modales -----------------------------------------------------------
    function enfocables(overlay) {
        return Array.prototype.filter.call(
            overlay.querySelectorAll(
                'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]),' +
                ' select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
            ),
            esVisible
        );
    }

    function botonCerrar(overlay) {
        return overlay.querySelector('.close-btn, [data-ui-cerrar], button[onclick*="closeModal"]') ||
            Array.prototype.find.call(overlay.querySelectorAll('button'), function (boton) {
                return /cancelar|close/i.test(boton.textContent || '');
            });
    }

    function cerrar(overlay) {
        var boton = botonCerrar(overlay);
        if (boton) boton.click();
    }

    function abrir(overlay, disparador) {
        overlay.dataset.uiDisparador = disparador && disparador !== document.body
            ? String(disparador.id || '') : '';
        var primero = enfocables(overlay)[0];
        if (primero) primero.focus();
    }

    function alCerrar(overlay) {
        var id = overlay.getAttribute('data-ui-disparador');
        var disparador = id ? document.getElementById(id) : null;
        if (disparador && esVisible(disparador)) disparador.focus();
        overlay.removeAttribute('data-ui-disparador');
    }

    function prepararModal(overlay) {
        if (!overlay || overlay.dataset.uiModalListo) return;
        overlay.dataset.uiModalListo = '1';

        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');

        var titulo = overlay.querySelector('[data-modal-title], h1, h2, h3, h4');
        if (titulo) {
            if (!titulo.id) titulo.id = 'ui-titulo-' + (overlay.id || Math.random().toString(36).slice(2, 8));
            overlay.setAttribute('aria-labelledby', titulo.id);
        } else {
            overlay.setAttribute('aria-label', 'Ventana de diálogo');
        }

        overlay.querySelectorAll('.close-btn, button[onclick*="closeModal"]').forEach(function (boton) {
            if (!boton.getAttribute('aria-label')) boton.setAttribute('aria-label', 'Cerrar ventana');
        });

        overlay.addEventListener('keydown', function (evento) {
            if (evento.key === 'Escape') {
                evento.preventDefault();
                evento.stopPropagation();
                cerrar(overlay);
                return;
            }
            if (evento.key !== 'Tab') return;
            var lista = enfocables(overlay);
            if (!lista.length) {
                evento.preventDefault();
                return;
            }
            var primero = lista[0];
            var ultimo = lista[lista.length - 1];
            if (evento.shiftKey && document.activeElement === primero) {
                evento.preventDefault();
                ultimo.focus();
            } else if (!evento.shiftKey && document.activeElement === ultimo) {
                evento.preventDefault();
                primero.focus();
            }
        });
    }

    function observarModales() {
        if (!window.MutationObserver) return;
        var observador = new MutationObserver(function (cambios) {
            cambios.forEach(function (cambio) {
                var overlay = cambio.target;
                prepararModal(overlay);
                var visible = esVisible(overlay);
                var estabaAbierto = overlay.dataset.uiAbierto === '1';
                if (visible && !estabaAbierto) {
                    overlay.dataset.uiAbierto = '1';
                    abrir(overlay, document.activeElement);
                    iniciarFlashes(overlay);
                } else if (!visible && estabaAbierto) {
                    overlay.removeAttribute('data-ui-abierto');
                    alCerrar(overlay);
                }
            });
        });

        function vigilar() {
            document.querySelectorAll('.modal-overlay').forEach(function (overlay) {
                prepararModal(overlay);
                if (overlay.dataset.uiVigilado) return;
                overlay.dataset.uiVigilado = '1';
                observador.observe(overlay, {
                    attributes: true,
                    attributeFilter: ['style', 'class', 'hidden']
                });
            });
        }
        UI.observarModales = vigilar;
        vigilar();
    }

    // ---- Utilidades --------------------------------------------------------
    UI.escapeHtml = function (valor) {
        return String(valor === null || valor === undefined ? '' : valor)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    };

    UI.setBusy = function (boton, texto) {
        if (!boton) return function () {};
        if (!boton.getAttribute('data-ui-html')) boton.setAttribute('data-ui-html', boton.innerHTML);
        boton.disabled = true;
        boton.setAttribute('aria-busy', 'true');
        if (texto) {
            boton.innerHTML = '<i class="fas fa-spinner fa-spin" aria-hidden="true"></i> ' +
                UI.escapeHtml(texto);
        }
        return function () {
            var original = boton.getAttribute('data-ui-html');
            if (original !== null) boton.innerHTML = original;
            boton.disabled = false;
            boton.removeAttribute('aria-busy');
        };
    };

    function iniciar() {
        iniciarFlashes(document);
        observarModales();

        // Los modales se inyectan también desde includes que llegan después del script.
        document.addEventListener('DOMContentLoaded', function () {
            iniciarFlashes(document);
            if (UI.observarModales) UI.observarModales();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
})();
