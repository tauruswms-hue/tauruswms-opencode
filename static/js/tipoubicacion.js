$(document).ready(function() {
    $('#tablaTipos').DataTable({
        "pageLength": 10,
        "language": DataTablesEs
    });
});

function openModal() {
    $('#formTipos')[0].reset();
    $('#form_id').val('');
    $('#form_soporte_picking').prop('checked', false);
    $('#form_operacion').val('');
    $('#modalTitle').text('Nuevo Tipo');
    $('#modalTipos').css('display', 'flex').hide().fadeIn(150);
}

function closeModal() {
    $('#modalTipos').fadeOut(150);
}

function editTipo(data) {
    openModal();
    $('#modalTitle').text('Editar: ' + data.descripcion);
    $('#form_id').val(data.id);
    $('#form_descipcion').val(data.descripcion);
    $('#form_soporte_picking').prop('checked', data.soporte_picking == 1);
    $('#form_operacion').val(data.operacion || '');
}
