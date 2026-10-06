/**
 * cuit.js — Formato del CUIT (99-99999999-9) en los formularios del WMS.
 * Lo carga base.html. Un campo con el atributo data-cuit agrega los guiones
 * solo mientras se escribe; la regla del servidor está en modules/cuit.py.
 */
function formatCuit(input) {
    if (!input) return;
    var d = input.value.replace(/[^0-9]/g, '').substring(0, 11);
    input.value = d.length > 10 ? d.substring(0, 2) + '-' + d.substring(2, 10) + '-' + d.substring(10)
        : d.length > 2 ? d.substring(0, 2) + '-' + d.substring(2) : d;
}

$(document).on('input', 'input[data-cuit]', function() { formatCuit(this); });
