$(document).ready(function() {
    // Inicializar DataTable con idioma español
    $('#tablaRutas').DataTable({
        "language": {
            "url": "//cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json"
        },
        "pageLength": 10,
        "responsive": true
    });
});

/**
 * Abre el modal en modo "Crear"
 */
function openModalRuta() {
    $('#formRuta')[0].reset();
    $('#form_id_ruta').val('');
    $('#modalTitleRuta').html('<i class="fas fa-plus-circle"></i> Nueva Ruta');
    $('#modalRuta').css('display', 'flex').hide().fadeIn(200);
}

/**
 * Cierra el modal con efecto de desvanecimiento
 */
function closeModalRuta() {
    $('#modalRuta').fadeOut(200);
}

/**
 * Carga los datos en el modal en modo "Editar"
 * @param {Object} data - Objeto con la información de la ruta
 */
function editRuta(data) {
    openModalRuta();
    $('#modalTitleRuta').html('<i class="fas fa-edit"></i> Editar Ruta: ' + data.nombre_ruta);
    $('#form_id_ruta').val(data.id_ruta);
    $('#form_nombre_ruta').val(data.nombre_ruta);
    $('#form_descripcion').val(data.descripcion);
}

// Cerrar modal al hacer click fuera de la tarjeta
$(window).on('click', function(event) {
    if ($(event.target).is('#modalRuta')) {
        closeModalRuta();
    }
});