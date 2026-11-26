// static/js/configuracion_db.js — prueba de conexión con feedback accesible.

document.addEventListener('DOMContentLoaded', function () {
    const testButton = document.getElementById('test-db-connection');
    const resultDiv = document.getElementById('db-test-result');

    function mostrarResultado(tipo, mensaje) {
        if (!resultDiv) return;
        resultDiv.innerHTML = '';
        const elemento = document.createElement('div');
        elemento.className = 'test-' + tipo;
        const icono = document.createElement('i');
        icono.className = 'fas ' + (tipo === 'success' ? 'fa-check-circle' :
            tipo === 'loading' ? 'fa-spinner fa-spin' : 'fa-triangle-exclamation');
        icono.setAttribute('aria-hidden', 'true');
        elemento.appendChild(icono);
        elemento.appendChild(document.createTextNode(' ' + (mensaje || '')));
        resultDiv.appendChild(elemento);
        resultDiv.className = 'db-test-result ' + tipo;
    }

    if (!testButton || !resultDiv) return;

    testButton.addEventListener('click', function () {
        const dbConfig = {
            host: document.getElementById('db_host').value,
            port: document.getElementById('db_port').value,
            database: document.getElementById('db_name').value,
            username: document.getElementById('db_user').value,
            charset: document.getElementById('db_charset').value
        };

        const restaurar = window.TaurusUI
            ? window.TaurusUI.setBusy(testButton, 'Probando conexión…')
            : function () {
                testButton.disabled = false;
                testButton.innerHTML = '<i class="fas fa-play"></i> Probar Conexión Actual';
            };
        testButton.disabled = true;
        mostrarResultado('loading', 'Probando conexión…');

        fetch('/test_db_connection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dbConfig)
        })
            .then(respuesta => respuesta.json())
            .then(data => mostrarResultado(data.success ? 'success' : 'error', data.message))
            .catch(error => mostrarResultado('error', 'Error de red: ' + error.message))
            .finally(restaurar);
    });
});
