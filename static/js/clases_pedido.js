$(document).ready(function() {
    $('#tablaClasesPedido').DataTable({
        "pageLength": 10,
        "language": { "url": "//cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json" }
    });
});

function openModalClase() {
    $('#formClasesPedido')[0].reset();
    $('#form_id_clase').val('');
    $('#modalClaseTitle').text('Nueva Clase de Pedido');
    $('#modalClasesPedido').css('display', 'flex').hide().fadeIn(150);
}

function closeModalClase() { $('#modalClasesPedido').fadeOut(150); }

function editClase(data) {
    openModalClase();
    $('#modalClaseTitle').text('Editar: ' + data.nombre);
    $('#form_id_clase').val(data.id_clase);
    $('#form_clase_nombre').val(data.nombre);
    $('#form_clase_activo').prop('checked', data.activo == 1);
}
