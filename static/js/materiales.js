function validarEAN(barcode) {
    if (!barcode || barcode.trim() === '') return { valido: true };
    barcode = barcode.trim();
    if (!/^\d{8}$/.test(barcode) && !/^\d{13}$/.test(barcode)) {
        return { valido: false, error: 'El código de barras debe tener 8 (EAN-8) o 13 (EAN-13) dígitos numéricos.' };
    }
    var esEAN8 = barcode.length === 8;
    var digitos = barcode.split('').map(Number);
    var suma = 0;
    for (var i = 0; i < digitos.length - 1; i++) {
        suma += digitos[i] * (esEAN8 ? (i % 2 === 0 ? 3 : 1) : (i % 2 === 0 ? 1 : 3));
    }
    var checkCalculado = (10 - (suma % 10)) % 10;
    if (checkCalculado !== digitos[digitos.length - 1]) {
        return { valido: false, error: 'El código de barras tiene un dígito verificador inválido.' };
    }
    return { valido: true };
}

$(document).ready(function() {
    $('.mat-tab-btn').on('click', function() {
        var idTab = $(this).data('tab');
        $('.mat-tab-btn').removeClass('active');
        $('.mat-tab-panel').removeClass('active');
        $(this).addClass('active');
        $('#' + idTab).addClass('active');
    });

    $('#tablaMateriales').DataTable({
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

    $('#formMateriales').on('submit', function(e) {
        var barcode = $('#form_codigo_barras').val();
        var resultado = validarEAN(barcode);
        if (!resultado.valido) {
            e.preventDefault();
            alert(resultado.error);
            $('#form_codigo_barras').focus();
            return;
        }

        var gtinUsados = [];
        var cantidadesUsadas = [];
        var warningCantidades = [];

        $('input[name="pres_barcodes[]"]').each(function() {
            var gtin = $(this).val();
            if (gtin && gtin.trim()) {
                if (gtinUsados.indexOf(gtin.trim()) !== -1) {
                    e.preventDefault();
                    alert('Hay GTIN-14 duplicados en las presentaciones.');
                    $(this).focus();
                    return;
                }
                gtinUsados.push(gtin.trim());
                var res = validarGTIN14(gtin.trim());
                if (!res.valido) {
                    e.preventDefault();
                    alert(res.error);
                    $(this).focus();
                    return;
                }
            }
        });

        $('input[name="pres_cantidades[]"]').each(function(idx) {
            var cant = parseFloat($(this).val());
            var nombre = $(this).closest('tr').find('input[name="pres_nombres[]"]').val() || 'Presentación ' + (idx + 1);
            if (!isNaN(cant)) {
                if (cantidadesUsadas.indexOf(cant) !== -1) {
                    warningCantidades.push('"' + nombre + '" tiene ' + cant + ' unidades, igual que otra presentación.');
                } else {
                    cantidadesUsadas.push(cant);
                }
            }
        });

        if (warningCantidades.length > 0) {
            var confirmar = confirm('ADVERTENCIA: Hay presentaciones con la misma cantidad de unidades:\n\n' + warningCantidades.join('\n') + '\n\n¿Desea continuar de todas formas?');
            if (!confirmar) {
                e.preventDefault();
            }
        }
    });
});

function agregarFilaProveedor(idProv = '', codigoProv = '', esHabitual = 0) {
    let options = '<option value="">Seleccionar...</option>';
    listaProveedoresDB.forEach(p => {
        let selected = (p.id == idProv) ? 'selected' : '';
        options += `<option value="${p.id}" ${selected}>${p.razonsocial}</option>`;
    });

    let checked = esHabitual ? 'checked' : '';
    let fila = `
        <tr>
            <td style="padding: 5px;"><select name="prov_ids[]" required style="width:100%; padding: 5px; border:1px solid #ddd; border-radius:4px;">${options}</select></td>
            <td style="padding: 5px;"><input type="text" name="prov_codigos[]" value="${codigoProv}" style="width:100%; padding: 5px; border:1px solid #ddd; border-radius:4px;"></td>
            <td style="padding: 5px; text-align:center;">
                <input type="radio" name="prov_habitual" value="_idx_" ${checked} title="Marcar como habitual" style="cursor:pointer; accent-color:#f39c12; width:16px; height:16px;">
            </td>
            <td style="padding: 5px; text-align:center;"><button type="button" class="btn-icon delete" onclick="$(this).closest('tr').remove()" style="color: #e74c3c; background:none; border:none; cursor:pointer;"><i class="fas fa-times"></i></button></td>
        </tr>`;

    let tbody = $('#listaProveedoresCuerpo');
    let idx = tbody.find('tr').length;
    fila = fila.replace('value="_idx_"', `value="${idx}"`);
    tbody.append(fila);
    // re-index all radio values
    reindexHabitual();
}

function reindexHabitual() {
    $('#listaProveedoresCuerpo tr').each(function(i) {
        $(this).find('input[name="prov_habitual"]').val(i);
    });
}

// ─── GTIN-14 ─────────────────────────────────────────────────────────────────
// Genera un GTIN-14 a partir de un EAN-13 y un dígito indicador (1-8).
// Pesos 3,1,3,1,... de derecha a izquierda sobre los primeros 13 dígitos.
function calcularGTIN14(ean13, indicador) {
    indicador = indicador || 1;
    if (!ean13 || ean13.length !== 13 || !/^\d{13}$/.test(ean13)) return '';
    var base = String(indicador) + ean13.substring(0, 12);
    var sum = 0;
    for (var i = 0; i < 13; i++) {
        var posFromRight = 13 - i;
        var peso = posFromRight % 2 === 0 ? 1 : 3;
        sum += parseInt(base[i]) * peso;
    }
    var check = (10 - (sum % 10)) % 10;
    return base + check;
}

function validarGTIN14(barcode) {
    if (!barcode || barcode.trim() === '') return { valido: true };
    barcode = barcode.trim();
    if (!/^\d{14}$/.test(barcode)) {
        return { valido: false, error: 'El GTIN-14 debe tener exactamente 14 dígitos numéricos.' };
    }
    var digitos = barcode.split('').map(Number);
    var sum = 0;
    for (var i = 0; i < 13; i++) {
        var posFromRight = 13 - i;
        var peso = posFromRight % 2 === 0 ? 1 : 3;
        sum += digitos[i] * peso;
    }
    var checkCalculado = (10 - (sum % 10)) % 10;
    if (checkCalculado !== digitos[13]) {
        return { valido: false, error: 'El GTIN-14 tiene un dígito verificador inválido.' };
    }
    return { valido: true };
}

// ─── PRESENTACIONES ───────────────────────────────────────────────────────────
function agregarFilaPresentacion(nombre, codigoBarras, cantidadUnidades, indicador, pesoBruto, pesoNeto) {
    nombre = nombre || '';
    codigoBarras = codigoBarras || '';
    cantidadUnidades = cantidadUnidades || 1;
    indicador = indicador || 1;
    pesoBruto = pesoBruto || '';
    var pesoNetoMaterial = parseFloat($('#form_peso_neto').val()) || 0;
    pesoNeto = pesoNeto || (pesoNetoMaterial * cantidadUnidades).toFixed(3);

    var indicadorOptions = '';
    for (var i = 1; i <= 8; i++) {
        var selected = (i === indicador) ? 'selected' : '';
        indicadorOptions += '<option value="' + i + '" ' + selected + '>' + i + '</option>';
    }

    var fila = `
        <tr>
            <td style="padding:5px;">
                <input type="text" name="pres_nombres[]" value="${nombre}" placeholder="Ej: Caja x12"
                       required style="width:100%; padding:5px; border:1px solid #ddd; border-radius:4px;">
            </td>
            <td style="padding:5px; display:flex; gap:4px; align-items:center;">
                <select name="pres_indicadores[]" title="Indicador GTIN (nivel de embalaje)" 
                        style="padding:5px; border:1px solid #ddd; border-radius:4px; width:50px;">
                    ${indicadorOptions}
                </select>
                <input type="text" name="pres_barcodes[]" value="${codigoBarras}" maxlength="14"
                       placeholder="GTIN-14"
                       style="flex:1; padding:5px; border:1px solid #ddd; border-radius:4px;">
                <button type="button" title="Generar GTIN-14 desde EAN-13 del material"
                        onclick="autoGTIN14(this)"
                        style="white-space:nowrap; background:#16a085; color:white; border:none; padding:5px 7px; border-radius:4px; cursor:pointer; font-size:0.75rem;">
                    <i class="fas fa-magic"></i>
                </button>
            </td>
            <td style="padding:5px;">
                <input type="number" name="pres_cantidades[]" value="${cantidadUnidades}" min="0.001" step="0.001"
                       style="width:100%; padding:5px; border:1px solid #ddd; border-radius:4px; text-align:right;"
                       onchange="actualizarPesoNetoPresentacion(this)">
            </td>
            <td style="padding:5px;">
                <input type="number" name="pres_pesos_brutos[]" value="${pesoBruto}" step="0.001" min="0"
                       placeholder="0.000" style="width:100%; padding:5px; border:1px solid #ddd; border-radius:4px; text-align:right;">
            </td>
            <td style="padding:5px;">
                <input type="number" name="pres_pesos_netos[]" value="${pesoNeto}" step="0.001" min="0"
                       placeholder="0.000" style="width:100%; padding:5px; border:1px solid #ddd; border-radius:4px; text-align:right;">
            </td>
            <td style="padding:5px; text-align:center;">
                <button type="button" onclick="$(this).closest('tr').remove()"
                        style="color:#e74c3c; background:none; border:none; cursor:pointer;">
                    <i class="fas fa-times"></i>
                </button>
            </td>
        </tr>`;
    $('#listaPresentacionesCuerpo').append(fila);
}

function actualizarPesoNetoPresentacion(inputCantidad) {
    var tr = $(inputCantidad).closest('tr');
    var cantidad = parseFloat($(inputCantidad).val()) || 0;
    var pesoNetoMaterial = parseFloat($('#form_peso_neto').val()) || 0;
    var nuevoPesoNeto = (pesoNetoMaterial * cantidad).toFixed(3);
    tr.find('input[name="pres_pesos_netos[]"]').val(nuevoPesoNeto);
}

function autoGTIN14(btn) {
    var ean13 = $('#form_codigo_barras').val().trim();
    if (!ean13 || ean13.length !== 13) {
        alert('Ingrese primero el EAN-13 del material (13 dígitos) en el campo "Código de Barras".');
        return;
    }
    var indicador = $(btn).closest('td').find('select[name="pres_indicadores[]"]').val() || 1;
    var gtin14 = calcularGTIN14(ean13, parseInt(indicador));
    $(btn).closest('td').find('input[name="pres_barcodes[]"]').val(gtin14);
}

// ─── MODAL ────────────────────────────────────────────────────────────────────
function openModal() {
    $('#formMateriales')[0].reset();
    $('#form_id_material').val('');
    $('#form_peso_bruto').val('');
    $('#form_peso_neto').val('');
    $('#listaProveedoresCuerpo').empty();
    $('#listaPresentacionesCuerpo').empty();
    $('#modalTitle').text('Nuevo Material');
    var $selMetodo = $('#form_metodo_picking');
    if ($selMetodo.length) {
        var valorDefault = typeof metodoPickingDefault !== 'undefined' && metodoPickingDefault ? metodoPickingDefault : 'libre';
        if (!$selMetodo.find('option[value="' + valorDefault + '"]').length) {
            valorDefault = $selMetodo.find('option').first().val();
        }
        $selMetodo.val(valorDefault);
    }
    agregarFilaProveedor();
    $('#modalMateriales').css('display', 'flex').hide().fadeIn(150);
}

function closeModal() { $('#modalMateriales').fadeOut(150); }

function editMaterial(data) {
    openModal();
    $('#modalTitle').text('Editar: ' + data.nombre);

    $('#form_id_material').val(data.id);
    $('#form_codigo').val(data.codigo);
    $('#form_nombre').val(data.nombre);
    $('#form_desc').val(data.descripcion);
    $('#form_codigo_barras').val(data.codigo_barras || '');
    $('#form_categoria').val(data.categoria_id);
    $('#form_unidad').val(data.unidad_medida_id);
    $('#form_stock_min').val(data.stock_minimo);
    $('#form_stock_max').val(data.stock_maximo);
    $('#form_peso_bruto').val(data.peso_bruto || '');
    $('#form_peso_neto').val(data.peso_neto || '');
    $('input[name="trazabilidad"][value="' + (data.trazabilidad || 'ninguna') + '"]').prop('checked', true);
    var $selMetodo = $('#form_metodo_picking');
    if ($selMetodo.length) {
        $selMetodo.val(data.metodo_picking || 'libre');
        if (!$selMetodo.val()) $selMetodo.val($selMetodo.find('option').first().val());
    }

    let misProvs = relacionesExistentes.filter(r => r.id_material == data.id);

    $('#listaProveedoresCuerpo').empty();
    if(misProvs.length > 0) {
        misProvs.forEach(rel => {
            agregarFilaProveedor(rel.id_proveedor, rel.codigo_referencia_prov, rel.es_habitual);
        });
    } else {
        agregarFilaProveedor();
    }

    let misPres = presentacionesExistentes.filter(p => p.id_material == data.id);
    $('#listaPresentacionesCuerpo').empty();
    misPres.forEach(p => {
        var indicador = 1;
        if (p.codigo_barras && p.codigo_barras.length === 14 && /^\d{14}$/.test(p.codigo_barras)) {
            indicador = parseInt(p.codigo_barras.charAt(0));
            if (indicador < 1 || indicador > 8) indicador = 1;
        }
        agregarFilaPresentacion(p.nombre, p.codigo_barras || '', p.cantidad_unidades, indicador, p.peso_bruto || '', p.peso_neto || '');
    });
}

// toggleDropdownExportar y funciones de importación viven en batch_ui.js
