$(document).ready(function() {
    $('#tablaUbicaciones').DataTable({
        scrollY: "calc(100vh - 490px)",
        scrollX: true,
        scrollCollapse: true,
        pageLength: 15,
        language: {
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
                sFirst:    "Primero",
                sLast:     "Último",
                sNext:     "Siguiente",
                sPrevious: "Anterior"
            }
        }
    });
});

function openModal() {
    $('#formUbicaciones')[0].reset();
    $('#form_id').val('');
    $('#modalTitle').text('Nueva Ubicación');
    $('#form_codigo').prop('readonly', false);
    $('#form_entrada').prop('checked', true);
    $('#form_salida').prop('checked', true);
    $('#modalUbicaciones').css('display', 'flex').hide().fadeIn(150);
}

function closeModal() {
    $('#modalUbicaciones').fadeOut(150);
}

function editUbicacion(data) {
    openModal();
    $('#modalTitle').text('Editar: ' + data.codigo);
    $('#form_id').val(data.id);
    $('#form_codigo').val(data.codigo).prop('readonly', true);
    $('#form_descipcion').val(data.descipcion);
    $('#form_tipo').val(data.tipoubicacion);
    $('#form_zona').val(data.id_zona || '');
    $('#form_orden_picking').val(data.orden_picking ?? 0);
    $('#form_coorA').val(data.coordenadaA);
    $('#form_coorB').val(data.coordenadaB);
    $('#form_coorC').val(data.coordenadaC);
    $('#form_coorD').val(data.coordenadaD);
    $('#form_capacidad').val(data.capacidad_maxima);
    $('#form_entrada').prop('checked', data.disponible_entrada == 1);
    $('#form_salida').prop('checked', data.disponible_salida == 1);
}
