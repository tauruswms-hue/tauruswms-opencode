$(document).ready(function() {
    $('#tablaCategorias').DataTable({
        "paging": false,                    // todas las filas en el cuerpo; el scroll lo maneja la grilla
        "scrollY": "calc(100vh - 300px)",   // cuerpo con scroll vertical; el header queda fijo
        "scrollCollapse": true,
        "language": DataTablesEs
    });
});

function openModal() {
    $('#formCategorias')[0].reset();
    $('#form_id_cat').val('');
    $('#form_activo').val('1');   // una categoría nueva se propone Activa
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
    $('#form_activo').val(data.activo ? '1' : '0');
}