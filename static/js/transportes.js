$(document).ready(function() {
    $('#tablaTransportes').DataTable({
        "language": { "url": "//cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json" },
        "pageLength": 10
    });

    // Validación extra: Impedir letras en el campo CUIT
    $('#form_cuit').on('input', function() {
        this.value = this.value.replace(/[^0-9]/g, '');
    });
});

function agregarFilaRuta(idRuta = '', obs = '') {
    let options = '<option value="">Seleccione Ruta...</option>';
    listaRutasDB.forEach(r => {
        let selected = (r.id_ruta == idRuta) ? 'selected' : '';
        options += `<option value="${r.id_ruta}" ${selected}>${r.nombre_ruta}</option>`;
    });

    let fila = `
        <tr style="border-top: 1px solid #eee;">
            <td style="padding: 8px 5px;">
                <select name="rutas_ids[]" required style="width:100%; padding: 6px; border-radius:4px;">${options}</select>
            </td>
            <td style="padding: 8px 5px;">
                <textarea name="rutas_obs[]" rows="1" placeholder="Ej: Frecuencia semanal..." style="width:100%; padding: 6px; border-radius:4px; border:1px solid #ddd; height: 35px;">${obs}</textarea>
            </td>
            <td style="text-align: center;">
                <button type="button" onclick="$(this).closest('tr').remove()" style="color:#e74c3c; background:none; border:none; cursor:pointer; font-size: 1.1rem;">&times;</button>
            </td>
        </tr>`;
    $('#listaRutasCuerpo').append(fila);
}

function _poblarSelectMuelles(idSeleccionado) {
    const $sel = $('#form_id_muelle_salida');
    $sel.empty().append('<option value="">-- Sin muelle asignado --</option>');
    muelles.forEach(m => {
        const sel = (m.id == idSeleccionado) ? 'selected' : '';
        $sel.append(`<option value="${m.id}" ${sel}>${m.codigo} - ${m.descipcion}</option>`);
    });
}

function openModal() {
    $('#formTransportes')[0].reset();
    $('#form_id_transporte').val('');
    $('#listaRutasCuerpo').empty();
    $('#modalTitle').html('<i class="fas fa-plus"></i> Nuevo Transporte');
    _poblarSelectMuelles('');
    agregarFilaRuta();
    $('#modalTransportes').css('display', 'flex').hide().fadeIn(200);
}

function closeModal() {
    $('#modalTransportes').fadeOut(200);
}

function editTransporte(data) {
    openModal();
    $('#modalTitle').html('<i class="fas fa-edit"></i> Editar: ' + data.razonsocial);
    $('#form_id_transporte').val(data.id_transporte);
    $('#form_codigo').val(data.codigo);
    $('#form_razonsocial').val(data.razonsocial);
    $('#form_cuit').val(data.cuit);
    $('#form_telefono').val(data.telefono);
    $('#form_email').val(data.email);
    $('#form_activo').prop('checked', data.activo == 1);
    _poblarSelectMuelles(data.id_muelle_salida);

    let susRutas = relacionesExistentes.filter(r => r.id_transporte == data.id_transporte);
    $('#listaRutasCuerpo').empty();
    if(susRutas.length > 0) {
        susRutas.forEach(rel => agregarFilaRuta(rel.id_ruta, rel.observaciones || ''));
    } else {
        agregarFilaRuta();
    }
}