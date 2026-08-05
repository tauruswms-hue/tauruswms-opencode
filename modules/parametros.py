from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import json
from modules.db_config import _get_admin_connection, get_db_connection

parametros_bp = Blueprint('parametros', __name__)


@parametros_bp.route('/parametros')
def parametros():
    """Muestra la página de configuración con los datos actuales del tenant del usuario"""
    tenant_id = session.get('tenant_id')
    
    if not tenant_id:
        flash("No se encontró el tenant del usuario", "warning")
        config = {
            'nombredelalmacen': '',
            'razonsocial': '',
            'metodosdepicking': 'fifo',
            'metodo_picking_default': 'libre',
            'bajostock': 0,
            'dias_filtro_fechas': 30,
        }
        return render_template('parametros.html', config=config)
    
    conn = _get_admin_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT nombredelalmacen, metodosdepicking, metodo_picking_default,
                       bajostock, dias_filtro_fechas
                FROM tenants WHERE id = %s
            """, (tenant_id,))
            row = cursor.fetchone()

            if not row:
                config = {
                    'nombredelalmacen': '',
                    'razonsocial': '',
                    'metodosdepicking': 'fifo',
                    'metodo_picking_default': 'libre',
                    'bajostock': 0,
                    'dias_filtro_fechas': 30,
                }
            else:
                metodos = row.get('metodosdepicking')
                if metodos:
                    try:
                        metodos = json.loads(metodos)
                    except:
                        metodos = 'fifo'
                else:
                    metodos = 'fifo'

                config = {
                    'nombredelalmacen': row.get('nombredelalmacen') or '',
                    'metodosdepicking': metodos,
                    'metodo_picking_default': row.get('metodo_picking_default') or 'libre',
                    'bajostock': row.get('bajostock') or 0,
                    'dias_filtro_fechas': row.get('dias_filtro_fechas') or 30,
                }

        return render_template('parametros.html', config=config)
    finally:
        conn.close()


@parametros_bp.route('/actualizar_parametros', methods=['POST'])
def actualizar():
    """Actualiza los parámetros en la base de datos para el tenant del usuario"""
    tenant_id = session.get('tenant_id')
    
    if not tenant_id:
        flash("No se encontró el tenant del usuario", "danger")
        return redirect(url_for('parametros.parametros'))
    
    d = request.form
    conn = _get_admin_connection()

    try:
        with conn.cursor() as cursor:
            metodos = d.getlist('metodosdepicking')
            if not metodos:
                metodos = ['fifo']
            picking_json = json.dumps(metodos)

            metodo_default = (d.get('metodo_picking_default') or '').strip().lower()
            if metodo_default not in metodos:
                metodo_default = metodos[0]

            cursor.execute("""
                UPDATE tenants SET
                    nombredelalmacen = %s,
                    metodosdepicking = %s,
                    metodo_picking_default = %s,
                    bajostock = %s,
                    dias_filtro_fechas = %s
                WHERE id = %s
            """, (
                d.get('nombredelalmacen', ''),
                picking_json,
                metodo_default,
                float(d.get('bajostock') or 0),
                int(d.get('dias_filtro_fechas') or 30),
                tenant_id
            ))
            conn.commit()
            flash("Configuración guardada correctamente", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error al guardar: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('parametros.parametros'))
