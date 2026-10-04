import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, redirect, url_for
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash

from modules.admin import admin_bp, admin_limiter
from modules.bootstrap import (
    check_default_secrets,
    harden_session_config,
    passwords_bd,
    register_error_handlers,
)
from modules.db_config import _get_admin_connection
from modules.sql_dialect import insert_ignore_sql

logger = logging.getLogger(__name__)

app = Flask(__name__)

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

APP_ENV = os.getenv('APP_ENV', 'development').strip().lower()

_ADMIN_SECRET_KEY = os.getenv('ADMIN_SECRET_KEY')
if not _ADMIN_SECRET_KEY:
    raise RuntimeError("Falta ADMIN_SECRET_KEY en .env (ver .env.example)")
app.secret_key = _ADMIN_SECRET_KEY
# Cookie propia: el WMS (:5000) usa 'session' en el mismo host y la pisaría
# (las cookies no distinguen puerto), invalidando la sesión y el token CSRF.
app.config['SESSION_COOKIE_NAME'] = 'taurus_admin_session'
app.register_blueprint(admin_bp)

csrf = CSRFProtect(app)

admin_limiter.init_app(app)

check_default_secrets(APP_ENV, [
    ('ADMIN_SECRET_KEY', os.getenv('ADMIN_SECRET_KEY')),
    ('SECRET_KEY', os.getenv('SECRET_KEY')),
    ('SECRET_SALT', os.getenv('SECRET_SALT')),
    *passwords_bd(APP_ENV, logger),
], logger)

harden_session_config(app, APP_ENV)

register_error_handlers(app, logger, template='admin_error.html')


@app.route('/')
def home():
    """La UI del panel vive en /admin; redirige la raíz para no mostrar 404."""
    return redirect(url_for('admin.index'))


def init_admin_db():
    """Crea el usuario inicial 'admin' solo si admin_usuarios está vacía (primer arranque).

    Si ya hay usuarios no hace nada: así un 'admin' renombrado o dado de baja no
    reaparece con la contraseña por defecto. En production nunca siembra: el
    primer superusuario se crea con superusuario-dist/superusuario.exe (o
    scripts/admin_superusuario.py).
    """
    try:
        conn = _get_admin_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) AS total FROM admin_usuarios")
        if cursor.fetchone()['total'] == 0:
            if APP_ENV == 'production':
                logger.warning(
                    "admin_usuarios está vacía y APP_ENV=production: no se crea el usuario "
                    "por defecto. Cree un SUPERADMIN con superusuario-dist/superusuario.exe"
                )
            else:
                cols = ['username', 'password_hash', 'nombre', 'email', 'rol']
                sql = insert_ignore_sql('admin_usuarios', cols)
                cursor.execute(sql, (
                    'admin', generate_password_hash('Admin@2024!'),
                    'Administrador', 'admin@taurus.local', 'SUPERADMIN'
                ))
                logger.info("Usuario inicial 'admin' creado (cambie la contraseña)")

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error("Error al inicializar BD admin: %s", e)
        return False


if __name__ == '__main__':
    init_admin_db()

    logger.info("=" * 50)
    logger.info("TAURUS WMS - PANEL DE ADMINISTRACION")
    logger.info("=" * 50)
    logger.info("URL http://localhost:5001/admin")
    logger.info("Usuario: admin")
    logger.info("CAMBIE LA CONTRASEÑA TRAS EL PRIMER INGRESO")
    logger.info("=" * 50)

    app.run(debug=True, host='0.0.0.0', port=5001)
