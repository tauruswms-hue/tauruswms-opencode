from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from datetime import datetime
from werkzeug.security import check_password_hash
from modules.db_config import get_db_connection, _get_admin_connection

omc_bp = Blueprint('omc', __name__)


def get_tenant_filter():
    return session.get('tenant_id')


def _generar_numero_omc(cursor):
    anio = datetime.now().year
    cursor.execute(
        "SELECT MAX(CAST(SUBSTRING_INDEX(numero, '-', -1) AS UNSIGNED)) AS max_seq "
        "FROM omc WHERE YEAR(fecha_creacion) = %s",
        (anio,)
    )
    seq = (cursor.fetchone()['max_seq'] or 0) + 1
    return f"OMC-{anio}-{seq:05d}"


def _crear_stock_saliendo(cursor, contenedor, id_ubicacion, usuario, ahora):
    cursor.execute("""
        UPDATE stockcontable
        SET StockSaliendo    = StockDisponible,
            StockDisponible  = 0,
            StockTotal       = 0,
            UltimoMovimiento = %s,
            UsuarioUltimoMov = %s
        WHERE IDContenedor = %s AND Ubicacion = %s AND StockDisponible > 0
    """, (ahora, usuario, contenedor, id_ubicacion))
    return cursor.rowcount


def _crear_stock_entrando(cursor, contenedor_origen, id_origen, id_destino,
                          usuario, ahora, contenedor_destino=None):
    contenedor_dest = contenedor_destino or contenedor_origen
    cursor.execute("""
        SELECT Material, Lote, TipoStock, StockSaliendo, FechaVencimiento
        FROM stockcontable
        WHERE IDContenedor = %s AND Ubicacion = %s AND StockSaliendo > 0
    """, (contenedor_origen, id_origen))
    registros = cursor.fetchall()
    for rec in registros:
        cursor.execute("""
            INSERT INTO stockcontable
                (Ubicacion, Material, Lote, TipoStock, IDContenedor,
                 StockTotal, StockDisponible, StockEntrando, StockSaliendo,
                 UltimaEntrada, UltimoMovimiento, FechaVencimiento, UsuarioUltimoMov)
            VALUES (%s, %s, %s, %s, %s, 0, 0, %s, 0, NULL, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                StockEntrando    = StockEntrando + VALUES(StockEntrando),
                UltimoMovimiento = VALUES(UltimoMovimiento),
                UsuarioUltimoMov = VALUES(UsuarioUltimoMov)
        """, (
            id_destino, rec['Material'], rec['Lote'], rec['TipoStock'], contenedor_dest,
            rec['StockSaliendo'], ahora, rec['FechaVencimiento'], usuario
        ))
    return len(registros)


def _get_contenedores_omc(cursor, id_omc):
    """Lista de contenedores de la OMC con info de ubicación origen."""
    cursor.execute("""
        SELECT oc.id, oc.id_contenedor, oc.id_contenedor_destino, oc.id_ubicacion_origen,
               u.codigo AS origen_codigo, u.descipcion AS origen_nombre
        FROM omc_contenedores oc
        JOIN ubicaciones u ON oc.id_ubicacion_origen = u.id
        WHERE oc.id_omc = %s
        ORDER BY oc.id
    """, (id_omc,))
    return cursor.fetchall()


# ============================================================================
# LISTADO
# ============================================================================
@omc_bp.route('/omc')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT o.*,
                       ud.codigo    AS destino_codigo, ud.descipcion AS destino_nombre,
                       r.numero     AS recepcion_numero,
                       p.nro_pedido AS pedido_numero,
                       GROUP_CONCAT(oc.id_contenedor ORDER BY oc.id_contenedor SEPARATOR ', ') AS contenedores_lista,
                       COUNT(oc.id) AS num_contenedores,
                       CASE WHEN COUNT(oc.id) = 1 THEN MAX(uo.codigo)
                            ELSE CONCAT(COUNT(oc.id), ' ubicaciones')
                       END AS origen_display
                FROM omc o
                JOIN ubicaciones ud ON o.id_ubicacion_destino = ud.id
                LEFT JOIN recepciones_cabecera r ON o.id_recepcion = r.id_recepcion
                LEFT JOIN pedidos_cabecera p ON o.id_pedido = p.id_pedido
                LEFT JOIN omc_contenedores oc ON o.id_omc = oc.id_omc
                LEFT JOIN ubicaciones uo ON oc.id_ubicacion_origen = uo.id
                WHERE (%s IS NULL OR o.tenant_id = %s)
                GROUP BY o.id_omc
                ORDER BY o.id_omc DESC
            """, (tenant_id, tenant_id))
            omcs = cursor.fetchall()

            cursor.execute("""
                SELECT DISTINCT oc.id_contenedor 
                FROM omc_contenedores oc
                JOIN omc o ON oc.id_omc = o.id_omc
                WHERE (%s IS NULL OR o.tenant_id = %s)
                ORDER BY oc.id_contenedor
            """, (tenant_id, tenant_id))
            contenedores = [r['id_contenedor'] for r in cursor.fetchall()]

        conn_admin = _get_admin_connection()
        try:
            with conn_admin.cursor() as cursor_admin:
                cursor_admin.execute("SELECT dias_filtro_fechas FROM tenants WHERE id = %s", (tenant_id,))
                param = cursor_admin.fetchone()
                dias_filtro = param['dias_filtro_fechas'] if param else 30
        finally:
            conn_admin.close()

        return render_template('omc.html', omcs=omcs, contenedores=contenedores, dias_filtro=dias_filtro)
    finally:
        conn.close()


# ============================================================================
# NUEVA OMC — formulario
# ============================================================================
@omc_bp.route('/omc/nueva')
def nueva():
    return render_template('omc_nueva.html')


# ============================================================================
# GUARDAR NUEVA OMC (manual)
# ============================================================================
@omc_bp.route('/omc/guardar', methods=['POST'])
def guardar():
    d = request.form
    id_destino         = d.get('id_ubicacion_destino', '').strip()
    contenedor_destino = (d.get('id_contenedor_destino') or '').strip().upper() or None
    observaciones      = d.get('observaciones') or None

    contenedores_input = request.form.getlist('contenedores_origen[]')
    origenes_input     = request.form.getlist('origenes[]')

    if not id_destino:
        flash("Debe seleccionar una ubicación destino.", "warning")
        return redirect(url_for('omc.nueva'))

    id_destino = int(id_destino)

    # Build and validate pairs (contenedor, id_origen)
    pares = []
    seen = set()
    for i, cont in enumerate(contenedores_input):
        cont = cont.strip().upper()
        if not cont:
            continue
        if i >= len(origenes_input) or not origenes_input[i]:
            flash(f"El contenedor {cont} no tiene ubicación origen definida.", "warning")
            return redirect(url_for('omc.nueva'))
        if cont in seen:
            flash(f"El contenedor {cont} está duplicado.", "warning")
            return redirect(url_for('omc.nueva'))
        seen.add(cont)
        pares.append({'contenedor': cont, 'id_origen': int(origenes_input[i])})

    if not pares:
        flash("Debe agregar al menos un contenedor.", "warning")
        return redirect(url_for('omc.nueva'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            ahora   = datetime.now()
            usuario = session.get('nombre', 'sistema')

            # Validate each container
            for par in pares:
                contenedor = par['contenedor']
                id_origen  = par['id_origen']

                cursor.execute("""
                    SELECT SUM(StockDisponible) AS total_disp,
                           SUM(StockSaliendo)  AS total_sal,
                           SUM(StockEntrando)  AS total_ent
                    FROM stockcontable
                    WHERE IDContenedor = %s AND Ubicacion = %s
                """, (contenedor, id_origen))
                row = cursor.fetchone()
                if not row or not row['total_disp']:
                    flash(f"Contenedor {contenedor}: sin stock disponible en la ubicación seleccionada.", "warning")
                    return redirect(url_for('omc.nueva'))
                if row['total_sal'] or row['total_ent']:
                    flash(f"Contenedor {contenedor}: tiene movimientos pendientes.", "warning")
                    return redirect(url_for('omc.nueva'))

                # No pending OMC for this container+origin
                cursor.execute("""
                    SELECT o.id_omc, o.numero FROM omc o
                    JOIN omc_contenedores oc ON o.id_omc = oc.id_omc
                    WHERE oc.id_contenedor = %s AND oc.id_ubicacion_origen = %s AND o.estado = 'Pendiente'
                """, (contenedor, id_origen))
                existente = cursor.fetchone()
                if existente:
                    flash(f"Contenedor {contenedor}: ya existe la OMC {existente['numero']} pendiente.", "warning")
                    return redirect(url_for('omc.nueva'))

                if id_origen == id_destino and not contenedor_destino:
                    flash(f"Contenedor {contenedor}: origen y destino no pueden ser la misma ubicación.", "warning")
                    return redirect(url_for('omc.nueva'))

            # Validate destination container (if any)
            if contenedor_destino:
                cursor.execute("""
                    SELECT SUM(StockSaliendo) AS total_sal, SUM(StockEntrando) AS total_ent
                    FROM stockcontable WHERE IDContenedor = %s
                """, (contenedor_destino,))
                row_dest = cursor.fetchone()
                if row_dest and (row_dest['total_sal'] or row_dest['total_ent']):
                    flash(f"El contenedor destino {contenedor_destino} tiene movimientos pendientes.", "warning")
                    return redirect(url_for('omc.nueva'))

            numero = _generar_numero_omc(cursor)

            # Stock operations per container
            for par in pares:
                _crear_stock_saliendo(cursor, par['contenedor'], par['id_origen'], usuario, ahora)
                _crear_stock_entrando(cursor, par['contenedor'], par['id_origen'], id_destino,
                                      usuario, ahora, contenedor_destino)

            # Create OMC header (id_contenedor / id_ubicacion_origen now NULL for manual OMCs)
            tenant_id = get_tenant_filter()
            cursor.execute("""
                INSERT INTO omc
                    (numero, id_contenedor, id_ubicacion_origen,
                     id_contenedor_destino, id_ubicacion_destino,
                     id_recepcion, estado, observaciones, usuario_creacion, fecha_creacion, tenant_id)
                VALUES (%s, NULL, NULL, %s, %s, NULL, 'Pendiente', %s, %s, %s, %s)
            """, (numero, contenedor_destino, id_destino, observaciones, usuario, ahora, tenant_id))
            id_omc = cursor.lastrowid

            # Insert omc_contenedores rows
            for par in pares:
                cursor.execute("""
                    INSERT INTO omc_contenedores
                        (id_omc, id_contenedor, id_contenedor_destino, id_ubicacion_origen, tenant_id)
                    VALUES (%s, %s, %s, %s, %s)
                """, (id_omc, par['contenedor'], contenedor_destino, par['id_origen'], tenant_id))

            conn.commit()
            flash(f"OMC {numero} creada con {len(pares)} contenedor(es).", "success")
            return redirect(url_for('omc.ver', id_omc=id_omc))

    except Exception as e:
        conn.rollback()
        flash(f"Error al crear la OMC: {str(e)}", "danger")
        return redirect(url_for('omc.nueva'))
    finally:
        conn.close()


# ============================================================================
# VER OMC
# ============================================================================
@omc_bp.route('/omc/ver/<int:id_omc>')
def ver(id_omc):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT o.*,
                       ud.codigo    AS destino_codigo, ud.descipcion AS destino_nombre,
                       r.numero     AS recepcion_numero,
                       p.nro_pedido AS pedido_numero
                FROM omc o
                JOIN ubicaciones ud ON o.id_ubicacion_destino = ud.id
                LEFT JOIN recepciones_cabecera r ON o.id_recepcion = r.id_recepcion
                LEFT JOIN pedidos_cabecera p ON o.id_pedido = p.id_pedido
                WHERE o.id_omc = %s AND (%s IS NULL OR o.tenant_id = %s)
            """, (id_omc, tenant_id, tenant_id))
            omc = cursor.fetchone()

            if not omc:
                flash("OMC no encontrada.", "danger")
                return redirect(url_for('omc.listar'))

            contenedores = _get_contenedores_omc(cursor, id_omc)

            # Stock en origen — per container at its origin location
            stock_origen = []
            for cont in contenedores:
                cursor.execute("""
                    SELECT sc.*, m.codigo AS mat_codigo, m.nombre AS mat_nombre,
                           u.codigo AS ubi_codigo,
                           %s AS contenedor_id
                    FROM stockcontable sc
                    JOIN materiales m ON sc.Material = m.id
                    JOIN ubicaciones u ON sc.Ubicacion = u.id
                    WHERE sc.IDContenedor = %s AND sc.Ubicacion = %s
                    ORDER BY m.codigo
                """, (cont['id_contenedor'], cont['id_contenedor'], cont['id_ubicacion_origen']))
                stock_origen.extend(cursor.fetchall())

            # Stock en destino — all containers at the destination location
            cont_dests = list({c.get('id_contenedor_destino') or c['id_contenedor'] for c in contenedores})
            stock_destino = []
            if cont_dests:
                ph = ','.join(['%s'] * len(cont_dests))
                cursor.execute(f"""
                    SELECT sc.*, m.codigo AS mat_codigo, m.nombre AS mat_nombre,
                           u.codigo AS ubi_codigo
                    FROM stockcontable sc
                    JOIN materiales m ON sc.Material = m.id
                    JOIN ubicaciones u ON sc.Ubicacion = u.id
                    WHERE sc.IDContenedor IN ({ph}) AND sc.Ubicacion = %s
                    ORDER BY sc.IDContenedor, m.codigo
                """, tuple(cont_dests) + (omc['id_ubicacion_destino'],))
                stock_destino = cursor.fetchall()

            cursor.execute("SELECT id, codigo, descipcion AS nombre FROM ubicaciones WHERE (%s IS NULL OR tenant_id = %s) ORDER BY codigo", (tenant_id, tenant_id))
            ubicaciones = cursor.fetchall()

        es_admin = session.get('rol', '').upper() == 'ADMIN'
        return render_template('omc_ver.html',
                               omc=omc,
                               contenedores=contenedores,
                               stock_origen=stock_origen,
                               stock_destino=stock_destino,
                               ubicaciones=ubicaciones,
                               es_admin=es_admin)
    finally:
        conn.close()


# ============================================================================
# CONFIRMAR OMC
# ============================================================================
@omc_bp.route('/omc/confirmar/<int:id_omc>', methods=['POST'])
def confirmar(id_omc):
    tenant_id = get_tenant_filter()
    if session.get('rol', '').upper() != 'ADMIN':
        flash("Solo un administrador puede confirmar una OMC.", "danger")
        return redirect(url_for('omc.ver', id_omc=id_omc))

    password = request.form.get('password_admin', '')
    if not password:
        flash("Debe ingresar la contraseña de administrador.", "warning")
        return redirect(url_for('omc.ver', id_omc=id_omc))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT password_hash FROM usuarios WHERE id = %s AND activo = 1",
                (session.get('user_id'),)
            )
            user = cursor.fetchone()
            if not user or not check_password_hash(user['password_hash'], password):
                flash("Contraseña incorrecta.", "danger")
                return redirect(url_for('omc.ver', id_omc=id_omc))

            cursor.execute(
                "SELECT * FROM omc WHERE id_omc = %s AND estado = 'Pendiente' AND (%s IS NULL OR tenant_id = %s)",
                (id_omc, tenant_id, tenant_id)
            )
            omc = cursor.fetchone()
            if not omc:
                flash("La OMC no existe o no está en estado Pendiente.", "danger")
                return redirect(url_for('omc.listar'))

            ahora    = datetime.now()
            usuario  = session.get('nombre', 'sistema')
            contenedores = _get_contenedores_omc(cursor, id_omc)

            # Capturar materiales para Cantidad_preparada ANTES de mover el stock
            materiales_confirmados = []
            if omc.get('id_pedido'):
                for cont in contenedores:
                    cont_dest = cont.get('id_contenedor_destino') or cont['id_contenedor']
                    cursor.execute("""
                        SELECT Material, StockEntrando AS cantidad
                        FROM stockcontable
                        WHERE IDContenedor = %s AND Ubicacion = %s AND StockEntrando > 0
                    """, (cont_dest, omc['id_ubicacion_destino']))
                    materiales_confirmados.extend(cursor.fetchall())

            filas = 0
            for cont in contenedores:
                cont_dest = cont.get('id_contenedor_destino') or cont['id_contenedor']

                # Eliminar contenedor de la ubicación origen
                cursor.execute("""
                    DELETE FROM stockcontable
                    WHERE IDContenedor = %s AND Ubicacion = %s
                """, (cont['id_contenedor'], cont['id_ubicacion_origen']))

                # Convertir StockEntrando en disponible en destino
                cursor.execute("""
                    UPDATE stockcontable
                    SET StockTotal       = StockTotal       + StockEntrando,
                        StockDisponible  = StockDisponible  + StockEntrando,
                        StockEntrando    = 0,
                        UltimaEntrada    = %s,
                        UltimoMovimiento = %s,
                        UsuarioUltimoMov = %s
                    WHERE IDContenedor = %s AND Ubicacion = %s AND StockEntrando > 0
                """, (ahora, ahora, usuario, cont_dest, omc['id_ubicacion_destino']))
                filas += cursor.rowcount

            # Actualizar estado OMC
            cursor.execute("""
                UPDATE omc
                SET estado = 'Confirmada', fecha_confirmacion = %s, usuario_confirmacion = %s
                WHERE id_omc = %s
            """, (ahora, usuario, id_omc))

            # Si vino de una recepción
            if omc['id_recepcion']:
                cursor.execute("""
                    UPDATE recepciones_cabecera
                    SET estado = 'Confirmada'
                    WHERE id_recepcion = %s AND estado = 'Cerrada'
                """, (omc['id_recepcion'],))

            # Si vino de un pedido: actualizar Cantidad_preparada y verificar si está completo
            if omc.get('id_pedido'):
                for mat in materiales_confirmados:
                    cursor.execute("""
                        UPDATE pedidos_detalle
                        SET Cantidad_preparada = Cantidad_preparada + %s
                        WHERE id_pedido = %s AND id_material = %s
                    """, (mat['cantidad'], omc['id_pedido'], mat['Material']))

                cursor.execute("""
                    SELECT COUNT(*) AS total,
                           SUM(CASE WHEN estado = 'Confirmada' THEN 1 ELSE 0 END) AS confirmadas
                    FROM omc
                    WHERE id_pedido = %s AND estado != 'Anulada'
                """, (omc['id_pedido'],))
                counts = cursor.fetchone()
                if counts and counts['total'] > 0 and counts['total'] == counts['confirmadas']:
                    cursor.execute("""
                        UPDATE pedidos_cabecera SET estado = 'Preparado'
                        WHERE id_pedido = %s AND estado NOT IN ('Preparado', 'Despachado', 'Anulado')
                    """, (omc['id_pedido'],))

            conn.commit()
            flash(f"OMC {omc['numero']} confirmada. {filas} registro(s) de stock pasaron a Disponible.", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Error al confirmar la OMC: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('omc.ver', id_omc=id_omc))


# ============================================================================
# MODIFICAR OMC — solo cambia destino y observaciones
# ============================================================================
@omc_bp.route('/omc/modificar/<int:id_omc>', methods=['POST'])
def modificar(id_omc):
    tenant_id = get_tenant_filter()
    d = request.form
    new_destino   = d.get('id_ubicacion_destino')
    observaciones = d.get('observaciones') or None

    if not new_destino:
        flash("Debe indicar la ubicación destino.", "warning")
        return redirect(url_for('omc.ver', id_omc=id_omc))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM omc WHERE id_omc = %s AND estado = 'Pendiente' AND (%s IS NULL OR tenant_id = %s)",
                (id_omc, tenant_id, tenant_id)
            )
            omc = cursor.fetchone()
            if not omc:
                flash("La OMC no existe o no está en estado Pendiente.", "danger")
                return redirect(url_for('omc.listar'))

            old_destino     = omc['id_ubicacion_destino']
            new_destino_int = int(new_destino)
            ahora           = datetime.now()
            usuario         = session.get('nombre', 'sistema')
            contenedores    = _get_contenedores_omc(cursor, id_omc)

            for cont in contenedores:
                cont_dest = cont.get('id_contenedor_destino') or cont['id_contenedor']

                # Eliminar StockEntrando en destino actual
                cursor.execute("""
                    UPDATE stockcontable
                    SET StockEntrando = 0, UltimoMovimiento = %s, UsuarioUltimoMov = %s
                    WHERE IDContenedor = %s AND Ubicacion = %s AND StockEntrando > 0
                """, (ahora, usuario, cont_dest, old_destino))

                # Crear StockEntrando en nuevo destino
                _crear_stock_entrando(cursor, cont['id_contenedor'], cont['id_ubicacion_origen'],
                                      new_destino_int, usuario, ahora,
                                      cont.get('id_contenedor_destino'))

            cursor.execute("""
                UPDATE omc
                SET id_ubicacion_destino = %s, observaciones = %s
                WHERE id_omc = %s
            """, (new_destino_int, observaciones, id_omc))

            conn.commit()
            flash(f"OMC {omc['numero']} modificada correctamente.", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Error al modificar la OMC: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('omc.ver', id_omc=id_omc))


# ============================================================================
# ANULAR OMC
# ============================================================================
@omc_bp.route('/omc/anular/<int:id_omc>', methods=['POST'])
def anular(id_omc):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM omc WHERE id_omc = %s AND estado = 'Pendiente' AND (%s IS NULL OR tenant_id = %s)",
                (id_omc, tenant_id, tenant_id)
            )
            omc = cursor.fetchone()
            if not omc:
                flash("La OMC no existe o no está en estado Pendiente.", "danger")
                return redirect(url_for('omc.listar'))

            ahora        = datetime.now()
            usuario      = session.get('nombre', 'sistema')
            contenedores = _get_contenedores_omc(cursor, id_omc)

            for cont in contenedores:
                cont_dest = cont.get('id_contenedor_destino') or cont['id_contenedor']

                # Eliminar StockEntrando en destino
                cursor.execute("""
                    UPDATE stockcontable
                    SET StockEntrando    = 0,
                        UltimoMovimiento = %s,
                        UsuarioUltimoMov = %s
                    WHERE IDContenedor = %s AND Ubicacion = %s AND StockEntrando > 0
                """, (ahora, usuario, cont_dest, omc['id_ubicacion_destino']))

                # Convertir StockSaliendo en disponible en origen
                cursor.execute("""
                    UPDATE stockcontable
                    SET StockTotal       = StockTotal       + StockSaliendo,
                        StockDisponible  = StockDisponible  + StockSaliendo,
                        StockSaliendo    = 0,
                        UltimaEntrada    = %s,
                        UltimoMovimiento = %s,
                        UsuarioUltimoMov = %s
                    WHERE IDContenedor = %s AND Ubicacion = %s AND StockSaliendo > 0
                """, (ahora, ahora, usuario, cont['id_contenedor'], cont['id_ubicacion_origen']))

            # Si vino de una recepción (no hace nada extra)
            if omc['id_recepcion']:
                pass

            # Si vino de un pedido, anular el pedido
            if omc.get('id_pedido'):
                cursor.execute("""
                    UPDATE pedidos_cabecera
                    SET estado = 'Anulado'
                    WHERE id_pedido = %s AND estado NOT IN ('Despachado', 'Anulado')
                """, (omc['id_pedido'],))

            cursor.execute("""
                UPDATE omc
                SET estado = 'Anulada', fecha_anulacion = %s, usuario_anulacion = %s
                WHERE id_omc = %s
            """, (ahora, usuario, id_omc))

            conn.commit()
            flash(f"OMC {omc['numero']} anulada. Stock liberado en todos los orígenes.", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Error al anular la OMC: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('omc.ver', id_omc=id_omc))


# ============================================================================
# AJAX: Buscar contenedores disponibles (origen)
# ============================================================================
@omc_bp.route('/omc/buscar_contenedores')
def buscar_contenedores():
    tenant_id = get_tenant_filter()
    q      = request.args.get('q',    '').strip()
    ubi    = request.args.get('ubi',  '').strip()
    tipo   = request.args.get('tipo', '').strip()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT sc.IDContenedor,
                       u.id              AS ubicacion_id,
                       u.codigo          AS ubicacion_codigo,
                       u.descipcion      AS ubicacion_nombre,
                       tu.id             AS tipo_id,
                       tu.descipción     AS tipo_nombre,
                       SUM(sc.StockDisponible) AS total_disponible
                FROM stockcontable sc
                JOIN ubicaciones u    ON sc.Ubicacion    = u.id
                JOIN tipoubicacion tu ON u.tipoubicacion = tu.id
                WHERE sc.IDContenedor LIKE %s
                  AND (%s IS NULL OR sc.tenant_id = %s)
            """
            params = [f'%{q}%', tenant_id, tenant_id]
            if ubi:
                sql += " AND (u.codigo LIKE %s OR u.descipcion LIKE %s)"
                params += [f'%{ubi}%', f'%{ubi}%']
            if tipo:
                sql += " AND tu.id = %s"
                params.append(int(tipo))
            sql += """
                GROUP BY sc.IDContenedor, sc.Ubicacion, u.id, u.codigo, u.descipcion, tu.id, tu.descipción
                HAVING SUM(sc.StockDisponible) > 0
                   AND SUM(sc.StockSaliendo)   = 0
                   AND SUM(sc.StockEntrando)   = 0
                ORDER BY u.codigo, sc.IDContenedor
                LIMIT 30
            """
            cursor.execute(sql, params)
            return jsonify(cursor.fetchall())
    finally:
        conn.close()


# ============================================================================
# AJAX: Tipos de ubicación (para filtros)
# ============================================================================
@omc_bp.route('/omc/tipos_ubicacion')
def tipos_ubicacion():
    picking = request.args.get('picking', '').strip()
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT id, descipción AS nombre FROM tipoubicacion WHERE (%s IS NULL OR tenant_id = %s)"
            params = [tenant_id, tenant_id]
            if picking == '1':
                sql += " AND soporte_picking = 1"
            sql += " ORDER BY descipción"
            cursor.execute(sql, params)
            return jsonify(cursor.fetchall())
    finally:
        conn.close()


# ============================================================================
# AJAX: Buscar contenedores destino
# ============================================================================
@omc_bp.route('/omc/buscar_contenedores_destino')
def buscar_contenedores_destino():
    q       = request.args.get('q', '').strip()
    excluir = request.args.get('excluir', '').strip().upper()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            like = f'%{q}%'
            cursor.execute("""
                SELECT sc.IDContenedor,
                       u.id           AS ubicacion_id,
                       u.codigo       AS ubicacion_codigo,
                       u.descipcion   AS ubicacion_nombre,
                       SUM(sc.StockDisponible) AS total_disponible
                FROM stockcontable sc
                JOIN ubicaciones u ON sc.Ubicacion = u.id
                WHERE sc.IDContenedor LIKE %s
                  AND sc.IDContenedor != %s
                GROUP BY sc.IDContenedor, sc.Ubicacion, u.id, u.codigo, u.descipcion
                HAVING SUM(sc.StockSaliendo) = 0
                   AND SUM(sc.StockEntrando) = 0
                ORDER BY sc.IDContenedor
                LIMIT 20
            """, (like, excluir or ''))
            return jsonify(cursor.fetchall())
    finally:
        conn.close()


# ============================================================================
# AJAX: Buscar ubicaciones
# ============================================================================
@omc_bp.route('/omc/buscar_ubicaciones')
def buscar_ubicaciones():
    tenant_id = get_tenant_filter()
    q       = request.args.get('q',       '').strip()
    picking = request.args.get('picking', '').strip()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            like = f'%{q}%'
            sql = """
                SELECT u.id, u.codigo, u.descipcion AS nombre, t.`descipción` AS tipo
                FROM ubicaciones u
                JOIN tipoubicacion t ON u.tipoubicacion = t.id
                WHERE (u.codigo LIKE %s OR u.descipcion LIKE %s)
                  AND (%s IS NULL OR u.tenant_id = %s)
            """
            params = [like, like, tenant_id, tenant_id]
            if picking == '1':
                sql += " AND t.soporte_picking = 1"
            sql += " ORDER BY u.codigo LIMIT 20"
            cursor.execute(sql, params)
            return jsonify(cursor.fetchall())
    finally:
        conn.close()
