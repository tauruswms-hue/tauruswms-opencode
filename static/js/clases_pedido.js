function openModalClase() {
    $('#formClasesPedido')[0].reset();
    $('#form_id_clase').val('');
    $('#form_clase_activo').val('1');   // una clase nueva se propone Activa
    $('#modalClaseTitle').text('Nueva Clase de Pedido');
    $('#modalClasesPedido').css('display', 'flex').hide().fadeIn(150);
}

function closeModalClase() { $('#modalClasesPedido').fadeOut(150); }

function editClase(data) {
    openModalClase();
    $('#modalClaseTitle').text('Editar: ' + data.nombre);
    $('#form_id_clase').val(data.id_clase);
    $('#form_clase_nombre').val(data.nombre);
    $('#form_clase_activo').val(data.activo ? '1' : '0');
}
