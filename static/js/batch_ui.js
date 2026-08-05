/**
 * batch_ui.js — Funciones compartidas de importación/exportación batch.
 * Usadas por: ubicaciones, proveedores, clientes, stockcontable (y materiales).
 */

function openModalImportar() {
    $('#importarArchivo').val('');
    _hideSelectorHoja();
    $('#importarResultado').hide().html('');
    $('#btnEjecutarImportar').prop('disabled', false).html('<i class="fas fa-upload"></i> Importar');
    $('#modalImportar').css('display', 'flex').hide().fadeIn(150);
}

function closeModalImportar() {
    $('#modalImportar').fadeOut(150);
}

// Al elegir un archivo XLSX, consulta sus pestañas para permitir elegir cuál importar.
// Si el archivo tiene una sola pestaña, se asume esa (no se muestra selector).
$(function() {
    $(document).on('change', '#importarArchivo', function() {
        var file = this.files && this.files[0];
        if (!file || !/\.xlsx$/i.test(file.name)) {
            _hideSelectorHoja();
            return;
        }
        var fd = new FormData();
        fd.append('archivo', file);
        $.ajax({
            url: '/api/xlsx_sheetnames',
            type: 'POST',
            data: fd,
            processData: false,
            contentType: false,
            success: function(resp) {
                var hojas = resp.hojas || [];
                if (hojas.length > 1) {
                    _mostrarSelectorHoja(hojas);
                } else {
                    _hideSelectorHoja();
                }
            },
            error: function() {
                _hideSelectorHoja();
            }
        });
    });
});

function _mostrarSelectorHoja(hojas) {
    var cont = $('#importarHojaCont');
    if (!cont.length) {
        var inputDiv = $('#importarArchivo').closest('div');
        inputDiv.after(
            '<div id="importarHojaCont" style="margin-bottom:14px;">' +
                '<label style="font-size:0.88rem; font-weight:bold; color:#555; display:block; margin-bottom:8px;">' +
                '<i class="fas fa-table"></i> Hoja a importar</label>' +
                '<select id="importarHoja" style="width:100%; padding:9px; border:1px solid #bdc3c7; border-radius:6px; box-sizing:border-box; font-size:0.9rem; background:#fff;"></select>' +
                '<small style="color:#888; display:block; margin-top:4px;">El archivo contiene varias hojas. Elegí cuál tiene los datos a importar.</small>' +
            '</div>'
        );
        cont = $('#importarHojaCont');
    }
    var sel = $('#importarHoja').empty();
    hojas.forEach(function(h) { sel.append('<option value="' + h + '">' + h + '</option>'); });
    cont.show();
}

function _hideSelectorHoja() {
    $('#importarHojaCont').hide();
}

function _hojaSeleccionada() {
    var sel = $('#importarHoja');
    if (sel.length && sel.is(':visible') && sel.val()) {
        return sel.val();
    }
    return null;
}

/**
 * @param {string} url  Ruta POST del módulo, ej: '/ubicaciones/importar'
 */
function ejecutarImportar(url) {
    var fileInput = document.getElementById('importarArchivo');
    if (!fileInput || !fileInput.files.length) {
        alert('Seleccioná un archivo antes de importar.');
        return;
    }

    var formData = new FormData();
    formData.append('archivo', fileInput.files[0]);
    var hoja = _hojaSeleccionada();
    if (hoja) {
        formData.append('hoja', hoja);
    }

    $('#btnEjecutarImportar').prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Procesando...');
    $('#importarResultado').hide().html('');

    $.ajax({
        url: url,
        type: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        success: function(resp) {
            _mostrarResultadoBatch(resp);
        },
        error: function(xhr) {
            var msg = (xhr.responseJSON && xhr.responseJSON.error) ? xhr.responseJSON.error : 'Error desconocido';
            $('#importarResultado').html(
                '<div style="background:#fde8e8; border:1px solid #f5c6cb; border-radius:6px; padding:14px; color:#c0392b;">' +
                '<i class="fas fa-exclamation-triangle"></i> <strong>Error:</strong> ' + msg + '</div>'
            ).show();
        },
        complete: function() {
            $('#btnEjecutarImportar').prop('disabled', false).html('<i class="fas fa-upload"></i> Importar');
        }
    });
}

function _mostrarResultadoBatch(resp) {
    var hayErrores  = resp.errores  && resp.errores.length  > 0;
    var hayOmitidos = resp.omitidos && resp.omitidos.length > 0;
    var hayActualizados = resp.actualizados > 0;
    var bgColor     = hayErrores ? '#fff3cd' : '#d4edda';
    var border      = hayErrores ? '#ffc107' : '#28a745';
    var icon        = hayErrores ? 'fa-exclamation-triangle' : 'fa-check-circle';
    var iconColor   = hayErrores ? '#856404' : '#155724';

    var html = '<div style="background:' + bgColor + '; border:1px solid ' + border + '; border-radius:6px; padding:14px; margin-bottom:12px;">' +
        '<p style="margin:0 0 6px; font-weight:bold; color:' + iconColor + ';"><i class="fas ' + icon + '"></i> Resultado de la importación</p>' +
        '<ul style="margin:0; padding-left:18px; font-size:0.9rem; color:#333;">' +
        '<li><strong>' + resp.insertados + '</strong> registro(s) importado(s) correctamente</li>' +
        (hayActualizados ? '<li><strong>' + resp.actualizados + '</strong> registro(s) actualizado(s)</li>' : '') +
        '<li><strong>' + (resp.omitidos ? resp.omitidos.length : 0) + '</strong> omitido(s) por duplicado</li>' +
        '<li><strong>' + (resp.errores  ? resp.errores.length  : 0) + '</strong> error(es)</li>' +
        '</ul></div>';

    if (hayOmitidos) {
        html += '<div style="background:#fff3cd; border:1px solid #ffc107; border-radius:6px; padding:10px 14px; margin-bottom:10px; font-size:0.85rem;">' +
            '<p style="margin:0 0 4px; font-weight:bold; color:#856404;"><i class="fas fa-ban"></i> Omitidos (ya existen)</p>' +
            '<p style="margin:0; color:#555; word-break:break-all;">' + resp.omitidos.join(', ') + '</p></div>';
    }

    if (hayErrores) {
        html += '<div style="background:#fde8e8; border:1px solid #f5c6cb; border-radius:6px; padding:10px 14px; margin-bottom:10px; font-size:0.85rem;">' +
            '<p style="margin:0 0 6px; font-weight:bold; color:#c0392b;"><i class="fas fa-times-circle"></i> Errores</p>' +
            '<table style="width:100%; border-collapse:collapse; font-size:0.82rem;">' +
            '<thead><tr style="background:#f8d7da;"><th style="padding:4px 8px; text-align:left;">Fila</th><th style="padding:4px 8px; text-align:left;">Código</th><th style="padding:4px 8px; text-align:left;">Razón</th></tr></thead><tbody>';
        resp.errores.forEach(function(e) {
            html += '<tr><td style="padding:3px 8px;">' + e.fila + '</td>' +
                    '<td style="padding:3px 8px;"><code>' + e.codigo + '</code></td>' +
                    '<td style="padding:3px 8px;">' + e.razon + '</td></tr>';
        });
        html += '</tbody></table></div>';
    }

    if (resp.insertados > 0) {
        html += '<div style="text-align:right; margin-top:4px;">' +
            '<button onclick="location.reload()" style="background:#27ae60; color:white; border:none; padding:8px 16px; border-radius:4px; cursor:pointer; font-size:0.88rem;">' +
            '<i class="fas fa-sync-alt"></i> Actualizar tabla</button></div>';
    }

    $('#importarResultado').html(html).show();
}

function toggleDropdownExportar(e) {
    e.stopPropagation();
    var dd = document.getElementById('dropdownExportar');
    if (dd) dd.style.display = dd.style.display === 'none' ? 'block' : 'none';
}

document.addEventListener('click', function() {
    var dd = document.getElementById('dropdownExportar');
    if (dd) dd.style.display = 'none';
});
