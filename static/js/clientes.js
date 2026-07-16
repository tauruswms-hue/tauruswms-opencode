$(document).ready(function() {
    $('#tablaClientes').DataTable({
        "scrollY": "calc(100vh - 390px)",
        "scrollX": true,
        "scrollCollapse": true,
        "pageLength": 25,
        "lengthMenu": [[10, 25, 50, 100], [10, 25, 50, 100]],
        "pagingType": "full_numbers",
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

function filtrarTransportes(idRuta, selectedTransporteId = null) {
    const $selectTransp = $('#form_id_transporte');
    $selectTransp.empty().append('<option value="">-- Seleccionar Transporte --</option>');

    if (!idRuta) return;

    const idsValidos = relTransporteRutas
        .filter(rel => rel.id_ruta == idRuta)
        .map(rel => rel.id_transporte);

    transportesDB.forEach(t => {
        if (idsValidos.includes(t.id_transporte)) {
            let selected = (t.id_transporte == selectedTransporteId) ? 'selected' : '';
            $selectTransp.append(`<option value="${t.id_transporte}" ${selected}>${t.razonsocial}</option>`);
        }
    });
}

function openModalCliente() {
    $('#formCliente')[0].reset();
    $('#form_id_cliente').val('');
    $('#form_activo').prop('checked', true); // Por defecto activo
    $('#form_id_transporte').empty().append('<option value="">-- Seleccione una ruta --</option>');
    $('#modalCliente').css('display', 'flex');
}

function closeModalCliente() { $('#modalCliente').hide(); }

function editCliente(data) {
    openModalCliente();
    $('#form_id_cliente').val(data.id_cliente);
    $('#form_codigo').val(data.codigo);
    $('#form_razonsocial').val(data.razonsocial);
    $('#form_cuit').val(data.cuit);
    $('#form_telefono').val(data.telefono);
    $('#form_email').val(data.email);
    $('#form_direccion').val(data.direccion);
    $('#form_localidad').val(data.localidad);
    $('#form_provincia').val(data.provincia);
    $('#form_activo').prop('checked', data.activo == 1);

    $('#form_id_ruta').val(data.id_ruta);
    filtrarTransportes(data.id_ruta, data.id_transporte_predeterminado);
}