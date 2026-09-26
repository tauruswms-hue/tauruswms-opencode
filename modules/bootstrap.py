"""Bootstrap compartido por las dos apps Flask (app.py y admin.py).

Evita duplicar en cada app: chequeo de secretos por defecto, hardening de
sesión y handlers de error 404/403/500.
"""

import datetime

# Secretos/passwords de desarrollo cuyo uso en production debe bloquearse.
DEFAULT_SECRETS = (
    'taurus-wms-secret-2024-dev', 'taurus-admin-secret-2024-dev',
    'taurus-wms-salt-2024', 'Admin@2024!', 'Taurus_2001', 'dev-fallback',
)


def check_default_secrets(app_env, secret_vars, logger, label=''):
    """Fuerza el cambio de secretos/passwords por defecto en production.

    `secret_vars` es una lista de tuplas (nombre_var, valor). En production
    lanza RuntimeError; en otros entornos solo loguea un warning.
    """
    encontrados = [f'{k}={v}' for k, v in secret_vars if v and v in DEFAULT_SECRETS]
    if not encontrados:
        return
    mensaje = ('Se detectaron credenciales/secretos por defecto. Cambiarlos '
               'antes de producción: ' + ', '.join(encontrados))
    if app_env == 'production':
        raise RuntimeError(mensaje)
    logger.warning('[SEGURIDAD] %s', mensaje)


def harden_session_config(app, app_env):
    """Aplica el hardening de cookies de sesión."""
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = (app_env == 'production')
    app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=8)


def register_error_handlers(app, logger, template='error.html'):
    """Registra handlers globales de error con una plantilla por app."""
    app_name = app.name or ''

    @app.errorhandler(404)
    def not_found(_e):
        logger.warning('%s 404 Not Found: %s', app_name, request_path())
        return render_error(template, 404, 'Página no encontrada',
                            'La URL solicitada no existe o fue movida.')

    @app.errorhandler(403)
    def forbidden(_e):
        logger.warning('%s 403 Forbidden: %s', app_name, request_path())
        return render_error(template, 403, 'Acceso denegado',
                            'No tiene permisos para acceder a este recurso.')

    from flask_wtf.csrf import CSRFError

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        # Token CSRF ausente/vencido: casi siempre la sesión expiró o la cookie
        # fue reemplazada. Mantiene el 400 pero explica qué hacer.
        logger.warning('%s CSRF rechazado en %s: %s', app_name, request_path(), e.description)
        mensaje = 'La sesión expiró o el formulario quedó vencido'
        detalle = ('Los cambios no se guardaron. Recargue la página (o vuelva a '
                   'iniciar sesión) e intente nuevamente.')
        if wants_json():
            from flask import jsonify
            return jsonify(success=False, error=f'{mensaje}. {detalle}'), 400
        return render_error(template, 400, mensaje, detalle)

    @app.errorhandler(500)
    def internal_error(e):
        logger.error('%s 500 Error en %s: %s', app_name, request_path(), e, exc_info=True)
        return render_error(template, 500, 'Error interno del servidor',
                            'Ocurrió un error inesperado. Contacte al administrador.')


def request_path():
    from flask import request
    return request.path


def wants_json():
    """True si el request es AJAX/JSON (fetch con JSON o X-Requested-With)."""
    from flask import request
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    return best == 'application/json' and request.accept_mimetypes[best] > request.accept_mimetypes['text/html']


def render_error(template, codigo, mensaje, detalle):
    from flask import render_template
    return render_template(template, codigo=codigo, mensaje=mensaje, detalle=detalle), codigo
