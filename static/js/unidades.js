$(document).ready(function() {
    $('#tablaUnidades').DataTable({
        "paging": false,                    // todas las filas en el cuerpo; el scroll lo maneja la grilla
        "scrollY": "calc(100vh - 300px)",   // cuerpo con scroll vertical; el header queda fijo
        "scrollCollapse": true,
        "language": { "url": "//cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json" }
    });
});

// ─── Unidad base ─────────────────────────────────────────────────────────────
// La unidad base es aquella sobre la que se calculan los múltiplos y submúltiplos
// (1000 mm = 1 m: la base del milímetro es el metro, con conversión 0,001).
// La lista ofrece las unidades ya cargadas de la misma magnitud.
function cargarUnidadesBase(seleccion) {
    var magnitud = $('#tipo_magnitud').val();
    var idActual = String($('#form_id_unidad').val() || '');
    var $sel = $('#unidad_base_referencia');
    if (seleccion === undefined) seleccion = $sel.val() || '';
    $sel.empty().append($('<option>').val('').text('— Ninguna: esta es una unidad base —'));
    unidadesCargadas.forEach(function(u) {
        if (u.tipo_magnitud !== magnitud || String(u.id_unidad) === idActual) return;
        var texto = u.codigo + ' — ' + u.nombre + (u.simbolo ? ' (' + u.simbolo + ')' : '') + (u.activo ? '' : ' — inactiva');
        $sel.append($('<option>').val(u.codigo).text(texto));
    });
    $sel.val(seleccion);
    if ($sel.val() === null) $sel.val('');   // la base anterior era de otra magnitud
    actualizarAyudaBase();
}

function actualizarAyudaBase() {
    var base = $('#unidad_base_referencia').val();
    var $conv = $('#conversion_a_base');
    var propia = $('#simbolo').val() || $('#codigo').val() || 'esta unidad';
    if (!base) {
        // Una unidad base se mide en sí misma: su conversión es siempre 1
        $conv.val('1.0000').prop('readonly', true).addClass('readonly-input');
        $('#ayuda_unidad_base').text('Es una unidad base: los múltiplos y submúltiplos de esta magnitud se pueden calcular sobre ella.');
        return;
    }
    $conv.prop('readonly', false).removeClass('readonly-input');
    var unidadBase = unidadesCargadas.filter(function(u) { return u.codigo === base; })[0];
    var simboloBase = unidadBase ? (unidadBase.simbolo || unidadBase.codigo) : base;
    var factor = parseFloat($conv.val());
    $('#ayuda_unidad_base').text('Conversión a base: cuántas unidades base equivalen a una de esta. ' +
        (factor > 0 ? '1 ' + propia + ' = ' + factor + ' ' + simboloBase + '.' : '') +
        ' Ejemplo: para milímetro con base metro, 0,001 (1000 mm = 1 m).');
}

$(document).on('change', '#tipo_magnitud', function() { cargarUnidadesBase(); });
$(document).on('change', '#unidad_base_referencia', actualizarAyudaBase);
$(document).on('input', '#conversion_a_base, #simbolo, #codigo', actualizarAyudaBase);

function openModal() {
    $('#formUnidades')[0].reset();
    $('#form_id_unidad').val('');   // vacío = alta
    $('#modalTitle').text('Nueva Unidad');
    $('#codigo').prop('readonly', false).removeClass('readonly-input');
    cargarUnidadesBase('');
    $('#modalUnidades').css('display', 'flex').hide().fadeIn(150);
}

function closeModal() {
    $('#modalUnidades').fadeOut(150);
}

function editUnidad(data) {
    openModal();
    $('#modalTitle').text('Editar: ' + data.nombre);
    $('#form_id_unidad').val(data.id_unidad);
    $('#codigo').val(data.codigo).prop('readonly', true).addClass('readonly-input');
    $('#nombre').val(data.nombre);
    $('#simbolo').val(data.simbolo);
    $('#tipo_magnitud').val(data.tipo_magnitud || 'CANTIDAD');
    $('#conversion_a_base').val(data.conversion_a_base);
    cargarUnidadesBase(data.unidad_base_referencia || '');
    $('#decimales_permitidos').val(data.decimales_permitidos);
    $('#activo').prop('checked', !!data.activo);
}