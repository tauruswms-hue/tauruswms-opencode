// static/js/configuracion_db.js

document.addEventListener('DOMContentLoaded', function() {
    const testButton = document.getElementById('test-db-connection');
    const resultDiv = document.getElementById('db-test-result');
    const passwordField = document.getElementById('db_password');

    // Función para probar conexión a BD
    if (testButton) {
        testButton.addEventListener('click', function() {
            // Obtener valores del formulario
            const dbConfig = {
                host: document.getElementById('db_host').value,
                port: document.getElementById('db_port').value,
                database: document.getElementById('db_name').value,
                username: document.getElementById('db_user').value,
                charset: document.getElementById('db_charset').value
            };

            // Mostrar estado de prueba
            testButton.disabled = true;
            testButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Probando conexión...';
            resultDiv.innerHTML = '<div class="test-loading"><i class="fas fa-spinner fa-spin"></i> Probando conexión...</div>';
            resultDiv.className = 'db-test-result loading';

            // Enviar solicitud al servidor
            fetch('/test_db_connection', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(dbConfig)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    resultDiv.innerHTML = '<div class="test-success"><i class="fas fa-check-circle"></i> ' + data.message + '</div>';
                    resultDiv.className = 'db-test-result success';
                } else {
                    resultDiv.innerHTML = '<div class="test-error"><i class="fas fa-times-circle"></i> ' + data.message + '</div>';
                    resultDiv.className = 'db-test-result error';
                }
            })
            .catch(error => {
                resultDiv.innerHTML = '<div class="test-error"><i class="fas fa-exclamation-triangle"></i> Error de red: ' + error.message + '</div>';
                resultDiv.className = 'db-test-result error';
            })
            .finally(() => {
                testButton.disabled = false;
                testButton.innerHTML = '<i class="fas fa-play"></i> Probar Conexión Actual';
            });
        });
    }

    // Mostrar/ocultar contraseña con doble clic
    if (passwordField) {
        passwordField.addEventListener('dblclick', function() {
            this.type = this.type === 'password' ? 'text' : 'password';

            if (this.type === 'text') {
                // Crear tooltip temporal
                const tooltip = document.createElement('div');
                tooltip.className = 'flash flash-warning temp-tooltip';
                tooltip.innerHTML = '<i class="fas fa-clock"></i> La contraseña será ocultada en 5 segundos';
                tooltip.style.position = 'fixed';
                tooltip.style.top = '20px';
                tooltip.style.right = '20px';
                tooltip.style.zIndex = '9999';
                tooltip.style.animation = 'slideIn 0.3s ease';
                document.body.appendChild(tooltip);

                setTimeout(() => {
                    this.type = 'password';
                    tooltip.style.opacity = '0';
                    setTimeout(() => tooltip.remove(), 300);
                }, 5000);
            }
        });
    }
});