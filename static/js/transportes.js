$(document).ready(function() {
    $('#tablaTransportes').DataTable({
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

// Escapa un valor para insertarlo en HTML (texto o atributo)
function escTra(valor) {
    return String(valor === null || valor === undefined ? '' : valor)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ─── Rutas que cubre el transporte ───────────────────────────────────────────
function actualizarRutas() {
    var cantidad = $('#listaRutasCuerpo tr').length;
    $('#tra_sin_rutas').toggle(cantidad === 0);
    $('.tra-tabla').toggle(cantidad > 0);
}

function agregarFilaRuta(idRuta, obs) {
    var options = '<option value="">Seleccionar ruta…</option>';
    listaRutasDB.forEach(function(r) {
        // Las inactivas no se ofrecen, salvo la que el transporte ya tiene
        if (!r.activo && r.id_ruta != idRuta) return;
        options += '<option value="' + escTra(r.id_ruta) + '"' + (r.id_ruta == idRuta ? ' selected' : '') + '>' +
            escTra(r.nombre_ruta) + (r.activo ? '' : ' (inactiva)') + '</option>';
    });
    $('#listaRutasCuerpo').append('<tr>' +
        '<td><select name="rutas_ids[]" required>' + options + '</select></td>' +
        '<td><input type="text" name="rutas_obs[]" value="' + escTra(obs) + '" placeholder="Ej: frecuencia semanal"></td>' +
        '<td style="text-align:center;"><button type="button" class="tra-quitar" title="Quitar" ' +
        'onclick="$(this).closest(\'tr\').remove(); actualizarRutas();"><i class="fas fa-times"></i></button></td>' +
        '</tr>');
    actualizarRutas();
}

// La misma ruta dos veces no tiene sentido: se avisa antes de enviar
$(document).on('submit', '#formTransportes', function(e) {
    var usadas = [], repetida = false;
    $('select[name="rutas_ids[]"]').each(function() {
        var id = $(this).val();
        if (!id) return;
        if (usadas.indexOf(id) !== -1) repetida = true;
        usadas.push(id);
    });
    if (repetida) {
        e.preventDefault();
        alert('Hay una ruta repetida en la lista de rutas.');
    }
});

// `actual` es el transporte que se edita: si su muelle ya no está entre los que se ofrecen (la
// ubicación quedó inactiva o dejó de ser de salida) se lo agrega marcado, para no quitárselo al guardar.
function _poblarSelectMuelles(idSeleccionado, actual) {
    const $sel = $('#form_id_muelle_salida');
    $sel.empty().append('<option value="">-- Sin muelle asignado --</option>');
    if (actual && idSeleccionado && !muelles.some(function(m) { return m.id == idSeleccionado; })) {
        $sel.append($('<option>').val(idSeleccionado).prop('selected', true)
            .text((actual.muelle_codigo || idSeleccionado) + ' — ' + (actual.muelle_aviso || 'ya no se ofrece')));
    }
    muelles.forEach(function(m) {
        // La descripción del muelle es opcional
        var texto = m.codigo + (m.descipcion ? ' - ' + m.descipcion : '');
        $sel.append($('<option>').val(m.id).text(texto).prop('selected', m.id == idSeleccionado));
    });
}

function openModal() {
    $('#formTransportes')[0].reset();
    $('#form_id_transporte').val('');
    $('#form_activo').val('1');   // un transporte nuevo se propone Activo
    $('#listaRutasCuerpo').empty();
    actualizarRutas();
    $('#modalTitle').text('Nuevo Transporte');
    _poblarSelectMuelles('');
    $('#modalTransportes').css('display', 'flex').hide().fadeIn(200);
}

function closeModal() {
    $('#modalTransportes').fadeOut(200);
}

function editTransporte(data) {
    openModal();
    $('#modalTitle').text('Editar: ' + data.razonsocial);
    $('#form_id_transporte').val(data.id_transporte);
    $('#form_codigo').val(data.codigo);
    $('#form_razonsocial').val(data.razonsocial);
    $('#form_cuit').val(data.cuit);
    formatCuit(document.getElementById('form_cuit'));
    $('#form_telefono').val(data.telefono);
    $('#form_email').val(data.email);
    $('#form_activo').val(data.activo ? '1' : '0');
    _poblarSelectMuelles(data.id_muelle_salida, data);

    relacionesExistentes.filter(function(r) { return r.id_transporte == data.id_transporte; })
        .forEach(function(rel) { agregarFilaRuta(rel.id_ruta, rel.observaciones || ''); });
}
