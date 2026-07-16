$(document).ready(function() {
    $('#tablaCategorias').DataTable({
        "pageLength": 10,
        "language": { "url": "//cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json" }
    });
});

function openModal() {
    $('#formCategorias')[0].reset();
    $('#form_id_cat').val('');
    $('#modalTitle').text('Nueva Categoría');
    $('#modalCategorias').css('display', 'flex').hide().fadeIn(150);
}

function closeModal() { $('#modalCategorias').fadeOut(150); }

function editCategoria(data) {
    openModal();
    $('#modalTitle').text('Editar: ' + data.nombre);
    $('#form_id_cat').val(data.id_categoria);
    $('#form_codigo').val(data.codigo);
    $('#form_nombre').val(data.nombre);
    $('#form_desc').val(data.descripcion);
    $('#form_activo').prop('checked', data.activo == 1);
}