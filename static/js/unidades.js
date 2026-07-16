$(document).ready(function() {
    $('#tablaUnidades').DataTable({
        "pageLength": 15,
        "language": { "url": "//cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json" }
    });
});

function openModal() {
    $('#formUnidades')[0].reset();
    $('#form_id_unidad').val('0');
    $('#modalTitle').text('Nueva Unidad');
    $('#codigo').prop('readonly', false).removeClass('readonly-input');
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
    $('#tipo_magnitud').val(data.tipo_magnitud);
    $('#conversion_a_base').val(data.conversion_a_base);
    $('#unidad_base_referencia').val(data.unidad_base_referencia);
    $('#decimales_permitidos').val(data.decimales_permitidos);
    $('#activo').prop('checked', data.activo == 1);
}