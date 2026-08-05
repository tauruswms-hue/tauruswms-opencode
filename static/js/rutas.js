$(document).ready(function() {
    // Inicializar DataTable con idioma español
    $('#tablaRutas').DataTable({
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