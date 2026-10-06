$(document).ready(function() {
    $('#tablaClientes').DataTable({
        "paging": false,                    // todas las filas en el cuerpo; el scroll lo maneja la grilla
        "scrollY": "calc(100vh - 300px)",
        "scrollX": true,
        "scrollCollapse": true,
        "language": {
            sProcessing:   "Procesando...",
            sLengthMenu:   "Mostrar _MENU_ registros",
            sZeroRecords:  "No se encontraron resultados",
            sEmptyTable:   "Ningún dato disponible",
            sInfo:         "Mostrando _START_ a _END_ de _TOTAL_ registros",
            sInfoEmpty:    "Mostrando 0 a 0 de 0 registros",
            sInfoFiltered: "(filtrado de _MAX_ registros totales)",
            sSearch:       "Buscar:",
            sLoadingRecords: "Cargando...",
            oPaginate: {
                sFirst:    "« Primero",
                sLast:     "Último »",
                sNext:     "Siguiente »",
                sPrevious: "« Anterior"
            }
        }
    });
});

function filtrarTransportes(idRuta, selectedTransporteId = null) {
    const $selectTransp = $('#form_id_transporte');
    $selectTransp.empty().append('<option value="">-- Seleccionar Transporte --</option>');

    if (!idRuta) {
        transportesDB.forEach(t => {
            let selected = (t.id_transporte == selectedTransporteId) ? 'selected' : '';
            $selectTransp.append(`<option value="${t.id_transporte}" ${selected}>${t.razonsocial}</option>`);
        });
        return;
    }

    const idsValidos = relTransporteRutas
        .filter(rel => rel.id_ruta == idRuta)
        .map(rel => rel.id_transporte);

    // Si la ruta no tiene transportes asociados (transporte_rutas vacio),
    // se listan todos los transportes activos como fallback.
    const usarFiltro = idsValidos.length > 0;
    transportesDB.forEach(t => {
        if (!usarFiltro || idsValidos.includes(t.id_transporte)) {
            let selected = (t.id_transporte == selectedTransporteId) ? 'selected' : '';
            $selectTransp.append(`<option value="${t.id_transporte}" ${selected}>${t.razonsocial}</option>`);
        }
    });
}

// Escapa un valor para insertarlo en HTML (texto o atributo)
function escCli(valor) {
    return String(valor === null || valor === undefined ? '' : valor)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ─── Pestañas ────────────────────────────────────────────────────────────────
function mostrarPestanaCliente(idTab) {
    $('.cli-tab-btn').removeClass('active');
    $('.cli-tab-panel').removeClass('active');
    $('.cli-tab-btn[data-tab="' + idTab + '"]').addClass('active');
    $('#' + idTab).addClass('active');
}
$(document).on('click', '.cli-tab-btn', function() { mostrarPestanaCliente($(this).data('tab')); });

// ─── Contactos ───────────────────────────────────────────────────────────────
// Un cliente puede tener varios contactos; el primero de la lista es el principal.
function actualizarCuentaContactos() {
    var cantidad = $('#listaContactosCuerpo tr').length;
    $('#cli_contactos_cantidad').text(cantidad || '');
    $('#cli_sin_contactos').toggle(cantidad === 0);
    $('.cli-tabla').toggle(cantidad > 0);
}

function agregarFilaContacto(c) {
    c = c || {};
    var campo = function(nombre, valor, largo, extra) {
        return '<td><input type="' + (nombre === 'email' ? 'email' : 'text') + '" name="contacto_' + nombre + '[]" value="' +
            escCli(valor) + '" maxlength="' + largo + '"' + (extra || '') + '></td>';
    };
    $('#listaContactosCuerpo').append('<tr>' +
        campo('nombre', c.nombre, 100, ' required') +
        campo('apellido', c.apellido, 100) +
        campo('departamento', c.departamento, 100, ' placeholder="Compras, Pagos…"') +
        campo('rol', c.rol, 100, ' placeholder="Jefe, Analista…"') +
        campo('telefono', c.telefono, 50) +
        campo('email', c.email, 100) +
        '<td class="col-accion"><button type="button" class="cli-quitar" title="Quitar" ' +
        'onclick="$(this).closest(\'tr\').remove(); actualizarCuentaContactos();"><i class="fas fa-times"></i></button></td>' +
        '</tr>');
    actualizarCuentaContactos();
}

// Si falta el nombre de un contacto, el navegador no puede marcarlo en una pestaña oculta: se la muestra
$(document).on('submit', '#formCliente', function(e) {
    var faltante = $('#listaContactosCuerpo input[name="contacto_nombre[]"]').filter(function() { return !this.value.trim(); }).first();
    if (faltante.length) {
        e.preventDefault();
        mostrarPestanaCliente('tab-cli-contactos');
        alert('Falta el nombre de un contacto.');
        faltante.focus();
    }
});

function openModalCliente() {
    $('#formCliente')[0].reset();
    $('#form_id_cliente').val('');
    $('#form_activo').val('1');   // un cliente nuevo se propone Activo
    $('#form_id_transporte').empty().append('<option value="">-- Seleccionar Transporte --</option>');
    $('#listaContactosCuerpo').empty();
    actualizarCuentaContactos();
    mostrarPestanaCliente('tab-cli-datos');
    $('#modalCliente').css('display', 'flex').hide().fadeIn(150);
}

function closeModalCliente() { $('#modalCliente').fadeOut(150); }

function editCliente(data) {
    openModalCliente();
    $('#form_id_cliente').val(data.id_cliente);
    $('#form_codigo').val(data.codigo);
    $('#form_razonsocial').val(data.razonsocial);
    $('#form_cuit').val(data.cuit);
    formatCuit(document.getElementById('form_cuit'));
    $('#form_telefono').val(data.telefono);
    $('#form_email').val(data.email);
    $('#form_direccion').val(data.direccion);
    $('#form_localidad').val(data.localidad);
    $('#form_provincia').val(data.provincia);
    $('#form_activo').val(data.activo ? '1' : '0');
    $('#form_nombre_fantasia').val(data.nombre_fantasia || '');
    $('#form_sitio_web').val(data.sitio_web || '');
    contactosClientes.filter(function(c) { return c.id_cliente == data.id_cliente; }).forEach(agregarFilaContacto);

    $('#form_id_ruta').val(data.id_ruta);
    filtrarTransportes(data.id_ruta, data.id_transporte_predeterminado);
}