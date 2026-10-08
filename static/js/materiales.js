// Escapa un valor para insertarlo en HTML (texto o atributo). Sin esto, una comilla
// en un nombre o código corta el campo al editar y se pierde al guardar.
function esc(valor) {
    return String(valor === null || valor === undefined ? '' : valor)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Número sin ceros de relleno: "100.000" -> "100", "0.500" -> "0.5", vacío -> "".
function numeroLimpio(valor) {
    if (valor === null || valor === undefined || valor === '') return '';
    var n = parseFloat(valor);
    return isNaN(n) ? '' : String(n);
}

// Códigos alternativo y del proveedor: por defecto valen lo mismo que el código del
// material. Mientras no se los cambie a mano, acompañan lo que se escribe en Código.
var codigoPrevio = '';
function seguirCodigo() {
    var codigo = $('#form_codigo').val();
    ['#form_codigo_alternativo', '#form_codigo_proveedor'].forEach(function(campo) {
        var actual = $(campo).val();
        if (actual === '' || actual === codigoPrevio) $(campo).val(codigo);
    });
    codigoPrevio = codigo;
}
$(document).on('input', '#form_codigo', seguirCodigo);

// ─── Imagen del producto ─────────────────────────────────────────────────────
// Una dirección web se puede mostrar al instante. Una ruta del servidor o de red
// la tiene que leer el servidor: se ve recién cuando el material está guardado.
var imagenGuardada = { id: null, ruta: '' };

function actualizarVistaImagen() {
    var ruta = ($('#form_imagen_ruta').val() || '').trim();
    var $vista = $('#imagen_vista'), $aviso = $('#imagen_aviso');
    var origen = '';
    $aviso.text('');
    if (/^https?:\/\//i.test(ruta)) {
        origen = ruta;
    } else if (ruta && imagenGuardada.id && ruta === imagenGuardada.ruta) {
        origen = '/materiales/imagen/' + imagenGuardada.id + '?v=' + encodeURIComponent(ruta);
    } else if (ruta) {
        $aviso.text('La vista previa de una ruta del servidor o de red aparece después de guardar.');
    }
    if (!origen) { $vista.hide(); return; }
    $('#imagen_vista_img').off('error').on('error', function() {
        $vista.hide();
        $aviso.text('No se pudo cargar la imagen: revisar que la ruta exista y que el servidor pueda leerla.');
    }).attr('src', origen);
    $vista.attr('href', origen).show();
}
$(document).on('change blur', '#form_imagen_ruta', actualizarVistaImagen);

// Muestra una pestaña del formulario
function mostrarPestana(idTab) {
    $('.mat-tab-btn').removeClass('active');
    $('.mat-tab-panel').removeClass('active');
    $('.mat-tab-btn[data-tab="' + idTab + '"]').addClass('active');
    $('#' + idTab).addClass('active');
}

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
    $('.mat-tab-btn').on('click', function() { mostrarPestana($(this).data('tab')); });

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

        var proveedoresUsados = [];
        var proveedorRepetido = false;
        $('select[name="prov_ids[]"]').each(function() {
            var id = $(this).val();
            if (!id) return;
            if (proveedoresUsados.indexOf(id) !== -1) proveedorRepetido = true;
            proveedoresUsados.push(id);
        });
        if (proveedorRepetido) {
            e.preventDefault();
            alert('Hay un proveedor repetido en la lista de proveedores.');
            return;
        }

        // El volumen se carga con su unidad
        if (parseFloat($('#form_volumen').val()) > 0 && !$('#form_volumen_unidad').val()) {
            e.preventDefault();
            mostrarPestana('tab-mat-stock');
            alert('Indique la unidad de medida del volumen.');
            $('#form_volumen_unidad').focus();
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
        options += `<option value="${esc(p.id)}" ${selected}>${esc(p.razonsocial)}</option>`;
    });

    let checked = esHabitual ? 'checked' : '';
    let fila = `
        <tr>
            <td><select name="prov_ids[]" required>${options}</select></td>
            <td><input type="text" name="prov_codigos[]" value="${esc(codigoProv)}" maxlength="100"></td>
            <td class="centro">
                <input type="radio" name="prov_habitual" value="_idx_" ${checked} title="Marcar como habitual" style="cursor:pointer; accent-color:#f39c12; width:16px; height:16px;">
            </td>
            <td class="centro"><button type="button" class="mat-quitar" title="Quitar" onclick="$(this).closest('tr').remove(); reindexHabitual();"><i class="fas fa-times"></i></button></td>
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
    pesoNeto = pesoNeto || (pesoNetoMaterial ? (pesoNetoMaterial * cantidadUnidades).toFixed(3) : '');

    var indicadorOptions = '';
    for (var i = 1; i <= 8; i++) {
        var selected = (i === indicador) ? 'selected' : '';
        indicadorOptions += '<option value="' + i + '" ' + selected + '>' + i + '</option>';
    }

    var fila = `
        <tr>
            <td><input type="text" name="pres_nombres[]" value="${esc(nombre)}" placeholder="Ej: Caja x12" required maxlength="100"></td>
            <td>
                <div class="mat-gtin">
                    <select name="pres_indicadores[]" title="Indicador GTIN (nivel de embalaje)">${indicadorOptions}</select>
                    <input type="text" name="pres_barcodes[]" value="${esc(codigoBarras)}" maxlength="14" inputmode="numeric" placeholder="14 dígitos">
                    <button type="button" title="Generar el GTIN-14 a partir del EAN-13 del material" onclick="autoGTIN14(this)"><i class="fas fa-magic"></i></button>
                </div>
            </td>
            <td><input type="number" class="num" name="pres_cantidades[]" value="${esc(numeroLimpio(cantidadUnidades))}" min="0.001" step="0.001" onchange="actualizarPesoNetoPresentacion(this)"></td>
            <td><input type="number" class="num" name="pres_pesos_brutos[]" value="${esc(numeroLimpio(pesoBruto))}" step="0.001" min="0" placeholder="0"></td>
            <td><input type="number" class="num" name="pres_pesos_netos[]" value="${esc(numeroLimpio(pesoNeto))}" step="0.001" min="0" placeholder="0"></td>
            <td class="centro"><button type="button" class="mat-quitar" title="Quitar" onclick="$(this).closest('tr').remove()"><i class="fas fa-times"></i></button></td>
        </tr>`;
    $('#listaPresentacionesCuerpo').append(fila);
}

function actualizarPesoNetoPresentacion(inputCantidad) {
    var tr = $(inputCantidad).closest('tr');
    var cantidad = parseFloat($(inputCantidad).val()) || 0;
    var pesoNetoMaterial = parseFloat($('#form_peso_neto').val()) || 0;
    if (!pesoNetoMaterial) return;   // sin peso neto del material no hay nada que calcular
    var nuevoPesoNeto = numeroLimpio((pesoNetoMaterial * cantidad).toFixed(3));
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
// Las categorías inactivas no se ofrecen, salvo la que el material ya tiene (para no quitársela al editar)
function mostrarCategoriasInactivas(idCategoriaDelMaterial) {
    $('#form_categoria option[data-inactiva]').each(function() {
        var oculta = this.value != idCategoriaDelMaterial;
        $(this).prop('hidden', oculta).prop('disabled', oculta);
    });
}

function openModal() {
    mostrarCategoriasInactivas(null);
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
    mostrarPestana('tab-mat-ident');
    codigoPrevio = '';
    imagenGuardada = { id: null, ruta: '' };
    actualizarVistaImagen();
    $('#aviso_metodo_picking').hide().text('');
    $('#form_activo').val('1');   // un material nuevo se propone Activo
    $('#modalMateriales').css('display', 'flex').hide().fadeIn(150);
}

function closeModal() { $('#modalMateriales').fadeOut(150); }

function editMaterial(data) {
    openModal();
    $('#modalTitle').text('Editar: ' + data.nombre);

    $('#form_id_material').val(data.id);
    $('#form_activo').val(data.activo ? '1' : '0');
    $('#form_codigo').val(data.codigo);
    $('#form_nombre').val(data.nombre);
    $('#form_desc').val(data.descripcion);
    $('#form_codigo_barras').val(data.codigo_barras || '');
    // Sin valor guardado (materiales anteriores), se muestra el código del material
    $('#form_codigo_alternativo').val(data.codigo_alternativo || data.codigo);
    $('#form_codigo_proveedor').val(data.codigo_proveedor || data.codigo);
    codigoPrevio = data.codigo;
    $('#form_volumen').val(numeroLimpio(data.volumen));
    $('#form_volumen_unidad').val(data.volumen_unidad_id || '');
    $('#form_imagen_ruta').val(data.imagen_ruta || '');
    imagenGuardada = { id: data.id, ruta: data.imagen_ruta || '' };
    actualizarVistaImagen();
    mostrarCategoriasInactivas(data.categoria_id);
    $('#form_categoria').val(data.categoria_id);
    $('#form_unidad').val(data.unidad_medida_id);
    $('#form_stock_min').val(numeroLimpio(data.stock_minimo) || '0');
    $('#form_stock_max').val(numeroLimpio(data.stock_maximo) || '0');
    $('#form_stock_repo').val(numeroLimpio(data.stock_reposicion) || '0');
    $('#form_peso_bruto').val(numeroLimpio(data.peso_bruto));
    $('#form_peso_neto').val(numeroLimpio(data.peso_neto));
    $('input[name="trazabilidad"][value="' + (data.trazabilidad || 'ninguna') + '"]').prop('checked', true);
    var $selMetodo = $('#form_metodo_picking');
    if ($selMetodo.length) {
        var guardado = data.metodo_picking || 'libre';
        $selMetodo.val(guardado);
        if (!$selMetodo.val()) {
            // El método que tenía el material ya no está habilitado para la empresa:
            // se propone el método por defecto y se avisa, para que el cambio no pase inadvertido.
            $selMetodo.val(metodoPickingDefault);
            if (!$selMetodo.val()) $selMetodo.val($selMetodo.find('option').first().val());
            $('#aviso_metodo_picking').text('Este material tenía el método "' + (metodosPickingLabels[guardado] || guardado) +
                '", que no está habilitado para la empresa. Al guardar quedará con el método seleccionado.').show();
        }
    }

    let misProvs = relacionesExistentes.filter(r => r.id_material == data.id);

    $('#listaProveedoresCuerpo').empty();
    misProvs.forEach(rel => {
        agregarFilaProveedor(rel.id_proveedor, rel.codigo_referencia_prov || '', rel.es_habitual);
    });

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

// ─── DISTRIBUCIÓN ─────────────────────────────────────────────────────────────
// Stock del material en cada posición (ubicación + contenedor + lote + tipo de stock).
function cerrarDistribucion() { $('#modalDistribucion').fadeOut(150); }

function verDistribucion(idMaterial) {
    $('#distMaterial').text('');
    $('#distResumen').empty();
    $('#distTabla').hide();
    $('#distMensaje').text('Consultando el stock…').show();
    $('#modalDistribucion').css('display', 'flex').hide().fadeIn(150);

    $.getJSON('/materiales/distribucion/' + idMaterial)
        .done(function(datos) {
            var unidad = datos.material.unidad ? ' ' + datos.material.unidad : '';
            $('#distMaterial').text(datos.material.codigo + ' — ' + datos.material.nombre);
            if (!datos.posiciones.length) {
                $('#distMensaje').text('Este material no tiene stock en ninguna posición.').show();
                return;
            }
            var cuerpo = datos.posiciones.map(function(p) {
                return '<tr>' +
                    '<td><strong>' + esc(p.ubicacion) + '</strong>' +
                        (p.ubicacion_descripcion ? '<div class="dist-sub">' + esc(p.ubicacion_descripcion) + '</div>' : '') + '</td>' +
                    '<td>' + esc(p.zona || '—') + (p.tipo_ubicacion ? '<div class="dist-sub">' + esc(p.tipo_ubicacion) + '</div>' : '') + '</td>' +
                    '<td>' + esc(p.contenedor || '—') + '</td>' +
                    '<td>' + esc(p.lote || '—') + '</td>' +
                    '<td>' + esc(p.tipo_stock || '—') + '</td>' +
                    '<td>' + esc(p.vencimiento || '—') + '</td>' +
                    '<td class="num"><strong>' + numeroLimpio(p.total) + '</strong></td>' +
                    '<td class="num">' + numeroLimpio(p.disponible) + '</td>' +
                    '<td class="num">' + numeroLimpio(p.entrando) + '</td>' +
                    '<td class="num">' + numeroLimpio(p.saliendo) + '</td>' +
                    '</tr>';
            }).join('');
            $('#distCuerpo').html(cuerpo);
            $('#distTotTotal').text(numeroLimpio(datos.totales.total) + unidad);
            $('#distTotDisponible').text(numeroLimpio(datos.totales.disponible) + unidad);
            $('#distTotEntrando').text(numeroLimpio(datos.totales.entrando) + unidad);
            $('#distTotSaliendo').text(numeroLimpio(datos.totales.saliendo) + unidad);
            $('#distResumen').html(
                '<span><strong>' + numeroLimpio(datos.totales.total) + esc(unidad) + '</strong> en total</span>' +
                '<span><strong>' + numeroLimpio(datos.totales.disponible) + esc(unidad) + '</strong> disponible</span>' +
                '<span><strong>' + datos.ubicaciones + '</strong> ' + (datos.ubicaciones === 1 ? 'ubicación' : 'ubicaciones') + '</span>' +
                '<span><strong>' + datos.posiciones.length + '</strong> ' + (datos.posiciones.length === 1 ? 'posición' : 'posiciones') + '</span>');
            $('#distMensaje').hide();
            $('#distTabla').show();
        })
        .fail(function(xhr) {
            var motivo = (xhr.responseJSON && xhr.responseJSON.error) || 'No se pudo consultar el stock.';
            $('#distMensaje').text(motivo).show();
        });
}
