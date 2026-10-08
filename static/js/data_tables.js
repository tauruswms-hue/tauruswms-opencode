/* data_tables.js — configuración centralizada de DataTables.
   Usar: initDataTable(selector, opciones) en vez de repetir la config.
   Requiere que jQuery y DataTables estén cargados antes. */

/* Textos de las grillas. Van acá y no en el es-ES.json del CDN de DataTables: así no dependen
   de un pedido a internet. Cada grilla los toma con  language: DataTablesEs  */
var DataTablesEs = {
    "processing":     "Procesando...",
    "lengthMenu":     "Mostrar _MENU_ registros",
    "zeroRecords":    "No se encontraron resultados",
    "emptyTable":     "Ningún dato disponible en esta tabla",
    "info":           "Mostrando _START_ a _END_ de _TOTAL_ registros",
    "infoEmpty":      "Mostrando 0 a 0 de 0 registros",
    "infoFiltered":   "(filtrado de _MAX_ registros totales)",
    "search":         "Buscar:",
    "loadingRecords": "Cargando...",
    "thousands":      ".",
    "decimal":        ",",
    "paginate": { "first": "Primero", "last": "Último", "next": "Siguiente", "previous": "Anterior" },
    "aria": {
        "sortAscending":  ": activar para ordenar la columna de manera ascendente",
        "sortDescending": ": activar para ordenar la columna de manera descendente"
    }
};

var DataTablesDefault = {
    "paging": false,
    "scrollY": "calc(100vh - 300px)",
    "scrollCollapse": true,
    "language": DataTablesEs
};

function initDataTable(selector, options) {
    var opts = $.extend({}, DataTablesDefault, options || {});
    return $(selector).DataTable(opts);
}
