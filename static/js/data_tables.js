/* data_tables.js — configuración centralizada de DataTables.
   Usar: initDataTable(selector, opciones) en vez de repetir la config.
   Requiere que jQuery y DataTables estén cargados antes. */
var DataTablesDefault = {
    "paging": false,
    "scrollY": "calc(100vh - 300px)",
    "scrollCollapse": true,
    "language": { "url": "//cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json" }
};

function initDataTable(selector, options) {
    var opts = $.extend({}, DataTablesDefault, options || {});
    return $(selector).DataTable(opts);
}
