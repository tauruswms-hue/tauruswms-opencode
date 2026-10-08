import re
from urllib.parse import urlparse

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from modules.batch_utils import (
    export_csv,
    export_json,
    export_xlsx,
    parse_file,
    plantilla_csv,
    plantilla_json,
    plantilla_xlsx,
)
from modules.context import get_tenant_filter
from modules.cuit import cuit_para_guardar, cuit_para_mostrar
from modules.db_config import get_db_connection
from modules.sql_dialect import execute_insert, is_duplicate_key_error

clientes_bp = Blueprint('clientes', __name__)

# Largo máximo de los textos del cliente (el de su columna)
_LARGOS = {'codigo': 100, 'razonsocial': 200, 'nombre_fantasia': 200, 'sitio_web': 255, 'email': 100,
           'direccion': 255, 'localidad': 100, 'provincia': 100, 'telefono': 50, 'contacto_nombre': 100}
_ROTULOS = {'codigo': 'Código', 'razonsocial': 'Razón Social', 'nombre_fantasia': 'Nombre de fantasía',
            'sitio_web': 'Sitio web', 'email': 'Mail principal', 'direccion': 'Domicilio', 'localidad': 'Localidad',
            'provincia': 'Provincia', 'telefono': 'Teléfono', 'contacto_nombre': 'Contacto'}
# Estados en los que un pedido ya no está en curso
_PEDIDO_TERMINADO = ('Despachado', 'Anulado')


def _texto(datos, campo, obligatorio=False):
    """Texto de un cliente: recortado, o None si está vacío. ValueError si falta o no entra en la columna."""
    valor = str(datos.get(campo) or '').strip()
    if obligatorio and not valor:
        raise ValueError(f'{_ROTULOS[campo]}: es obligatorio.')
    if len(valor) > _LARGOS[campo]:
        raise ValueError(f'{_ROTULOS[campo]}: admite hasta {_LARGOS[campo]} caracteres.')
    return valor or None


def _datos_del_cliente(datos):
    """Datos propios del cliente (formulario o fila importada), verificados. Lanza ValueError con el motivo."""
    return {
        'codigo': _texto(datos, 'codigo', obligatorio=True),
        'razonsocial': _texto(datos, 'razonsocial', obligatorio=True),
        'cuit': cuit_para_guardar(datos.get('cuit')),
        'direccion': _texto(datos, 'direccion'),
        'localidad': _texto(datos, 'localidad'),
        'provincia': _texto(datos, 'provincia'),
        'telefono': _texto(datos, 'telefono'),
        'email': _email(datos),
        'nombre_fantasia': _texto(datos, 'nombre_fantasia'),
        'sitio_web': _sitio_web(datos),
    }


def _codigo_en_uso(cursor, codigo, tenant_id, excluir_id=0):
    cursor.execute("""SELECT id_cliente FROM clientes
                      WHERE codigo = %s AND id_cliente <> %s AND (%s IS NULL OR tenant_id = %s)""",
                   (codigo, excluir_id, tenant_id, tenant_id))
    return cursor.fetchone() is not None


def _id_propio(cursor, tabla, columna_id, valor, tenant_id, rotulo):
    """ID de una ruta o transporte de la empresa, o None si no se indicó. ValueError si no existe."""
    valor = str(valor or '').strip()
    if not valor:
        return None
    if valor.isdigit():
        cursor.execute(f"SELECT {columna_id} FROM {tabla} WHERE {columna_id} = %s AND (%s IS NULL OR tenant_id = %s)",
                       (int(valor), tenant_id, tenant_id))
        if cursor.fetchone():
            return int(valor)
    raise ValueError(f'{rotulo}: no existe.')


def _email(datos):
    valor = _texto(datos, 'email')
    if valor and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', valor):
        raise ValueError('Mail principal: no tiene formato de dirección de correo.')
    return valor


def _sitio_web(datos):
    """Sitio web como dirección http(s). Si se escribe sin el protocolo (www.empresa.com) se completa con https://."""
    valor = _texto(datos, 'sitio_web')
    if not valor:
        return None
    if not re.match(r'^[a-z][a-z0-9+.-]*://', valor, re.I):
        valor = 'https://' + valor
    partes = urlparse(valor)
    if partes.scheme not in ('http', 'https') or '.' not in partes.netloc or ' ' in valor:
        raise ValueError('Sitio web: tiene que ser una dirección web, por ejemplo www.empresa.com.')
    if len(valor) > _LARGOS['sitio_web']:
        raise ValueError(f'Sitio web: admite hasta {_LARGOS["sitio_web"]} caracteres.')
    return valor


# --- Contactos del cliente -------------------------------------------------
# Un cliente puede tener varios contactos (tabla cliente_contactos). La columna
# clientes.contacto_nombre se conserva con el nombre del primero, para la
# exportación y el Intercambio, que manejan un solo contacto.
_CONTACTO_CAMPOS = (('nombre', 'Nombre', 100), ('apellido', 'Apellido', 100),
                    ('departamento', 'Departamento o sección', 100), ('rol', 'Rol', 100),
                    ('telefono', 'Teléfono', 50), ('email', 'Mail', 100))


def _contactos_del_formulario(form):
    """Contactos cargados en el formulario, verificados. Las filas totalmente vacías se ignoran."""
    listas = {campo: form.getlist(f'contacto_{campo}[]') for campo, _, _ in _CONTACTO_CAMPOS}
    contactos = []
    for i in range(max((len(v) for v in listas.values()), default=0)):
        c = {campo: (listas[campo][i].strip() if i < len(listas[campo]) else '') for campo, _, _ in _CONTACTO_CAMPOS}
        if not any(c.values()):
            continue
        rotulo_fila = f'Contacto {len(contactos) + 1}'
        if not c['nombre']:
            raise ValueError(f'{rotulo_fila}: falta el nombre.')
        for campo, rotulo, largo in _CONTACTO_CAMPOS:
            if len(c[campo]) > largo:
                raise ValueError(f'{rotulo_fila}: {rotulo.lower()} admite hasta {largo} caracteres.')
        if c['email'] and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', c['email']):
            raise ValueError(f'{rotulo_fila}: el mail no tiene formato de dirección de correo.')
        contactos.append({k: (v or None) for k, v in c.items()})
    return contactos


def _nombre_completo(contacto):
    return ' '.join(p for p in (contacto.get('nombre'), contacto.get('apellido')) if p)[:100]


def _guardar_contactos(cursor, id_cliente, contactos, tenant_id):
    """Reemplaza los contactos del cliente por los dados."""
    cursor.execute("DELETE FROM cliente_contactos WHERE id_cliente = %s", (id_cliente,))
    for c in contactos:
        cursor.execute("""INSERT INTO cliente_contactos
                              (id_cliente, nombre, apellido, departamento, rol, telefono, email, tenant_id)
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                       (id_cliente, c['nombre'], c.get('apellido'), c.get('departamento'), c.get('rol'),
                        c.get('telefono'), c.get('email'), tenant_id))


def _activo(valor, por_defecto=True):
    """Estado del cliente: True = Activo. Acepta 1/0 (lista Estado) y on (casilla, formularios anteriores)."""
    valor = str(valor if valor is not None else '').strip().lower()
    if not valor:
        return por_defecto
    return valor in ('1', 'on', 'true', 'si', 'sí', 'yes')


@clientes_bp.route('/clientes')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT c.*, r.nombre_ruta, t.razonsocial as nombre_transporte,
                       (SELECT COUNT(*) FROM pedidos_cabecera p WHERE p.id_cliente = c.id_cliente) AS pedidos
                FROM clientes c
                LEFT JOIN rutas r ON c.id_ruta = r.id_ruta
                LEFT JOIN transportes t ON c.id_transporte_predeterminado = t.id_transporte
                WHERE (%s IS NULL OR c.tenant_id = %s)
                ORDER BY c.razonsocial ASC
            """
            cursor.execute(sql, (tenant_id, tenant_id))
            clientes = [dict(c) for c in cursor.fetchall()]
            for c in clientes:
                # Los CUIT cargados antes sin guiones se muestran y editan ya formateados
                c['cuit'] = cuit_para_mostrar(c.get('cuit'))

            cursor.execute("SELECT * FROM rutas WHERE (%s IS NULL OR tenant_id = %s) ORDER BY nombre_ruta", (tenant_id, tenant_id))
            rutas = cursor.fetchall()

            # Activos, más los inactivos que algún cliente ya tiene como habitual (para no quitárselo al editarlo)
            cursor.execute("""
                SELECT id_transporte, razonsocial, activo FROM transportes
                WHERE (%s IS NULL OR tenant_id = %s)
                  AND (activo = 1 OR id_transporte IN (SELECT id_transporte_predeterminado FROM clientes
                                                       WHERE id_transporte_predeterminado IS NOT NULL
                                                         AND (%s IS NULL OR tenant_id = %s)))
                ORDER BY razonsocial
            """, (tenant_id, tenant_id, tenant_id, tenant_id))
            transportes_all = cursor.fetchall()

            cursor.execute("SELECT id_transporte, id_ruta FROM transporte_rutas WHERE (%s IS NULL OR tenant_id = %s)", (tenant_id, tenant_id))
            rel_transp_rutas = cursor.fetchall()

            cursor.execute("""SELECT id_cliente, nombre, apellido, departamento, rol, telefono, email
                              FROM cliente_contactos WHERE (%s IS NULL OR tenant_id = %s) ORDER BY id""",
                           (tenant_id, tenant_id))
            contactos = cursor.fetchall()
            por_cliente = {}
            for ct in contactos:
                por_cliente.setdefault(ct['id_cliente'], []).append(ct)
            for c in clientes:
                propios = por_cliente.get(c['id_cliente'], [])
                c['contactos_cantidad'] = len(propios)
                c['contacto_principal'] = _nombre_completo(propios[0]) if propios else ''
                c['contacto_principal_rol'] = (propios[0].get('rol') or '') if propios else ''

        return render_template('clientes.html',
                               clientes=clientes,
                               rutas=rutas,
                               transportes_all=transportes_all,
                               rel_transp_rutas=rel_transp_rutas,
                               contactos=contactos)
    finally:
        conn.close()


@clientes_bp.route('/clientes/guardar', methods=['POST'])
def guardar():
    d = request.form
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        # Sin id o vacío: es un alta
        try:
            c_id = int((d.get('id_cliente') or '0').strip() or 0)
        except ValueError:
            raise ValueError('El cliente que se intenta modificar no existe.') from None
        datos = _datos_del_cliente(d)
        contactos = _contactos_del_formulario(request.form)

        with conn.cursor() as cursor:
            anterior = None
            if c_id:
                cursor.execute("SELECT activo FROM clientes WHERE id_cliente = %s AND (%s IS NULL OR tenant_id = %s)",
                               (c_id, tenant_id, tenant_id))
                anterior = cursor.fetchone()
                if not anterior:
                    raise ValueError('El cliente que se intenta modificar no existe.')
            if _codigo_en_uso(cursor, datos['codigo'], tenant_id, excluir_id=c_id):
                raise ValueError(f'Ya existe un cliente con el código "{datos["codigo"]}".')
            # Un cliente nuevo nace activo; al editar sin el dato se conserva el estado
            activo_val = _activo(d.get('activo'), por_defecto=bool(anterior['activo']) if anterior else True)
            params = (
                datos['codigo'],
                datos['razonsocial'],
                datos['cuit'],
                datos['direccion'],
                datos['localidad'],
                datos['provincia'],
                datos['telefono'],
                datos['email'],
                _nombre_completo(contactos[0]) if contactos else None,
                _id_propio(cursor, 'rutas', 'id_ruta', d.get('id_ruta'), tenant_id, 'Ruta de entrega'),
                _id_propio(cursor, 'transportes', 'id_transporte', d.get('id_transporte_predeterminado'), tenant_id,
                           'Transporte habitual'),
                activo_val,
                datos['nombre_fantasia'],
                datos['sitio_web'],
            )

            if c_id:
                sql = """UPDATE clientes SET codigo=%s, razonsocial=%s, cuit=%s,
                         direccion=%s, localidad=%s, provincia=%s, telefono=%s,
                         email=%s, contacto_nombre=%s, id_ruta=%s,
                         id_transporte_predeterminado=%s, activo=%s,
                         nombre_fantasia=%s, sitio_web=%s
                         WHERE id_cliente=%s"""
                cursor.execute(sql, (*params, c_id))
                id_cliente = c_id
            else:
                sql = """INSERT INTO clientes (codigo, razonsocial, cuit, direccion,
                         localidad, provincia, telefono, email, contacto_nombre,
                         id_ruta, id_transporte_predeterminado, activo,
                         nombre_fantasia, sitio_web, tenant_id)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                id_cliente = execute_insert(cursor, sql, (*params, tenant_id), id_col='id_cliente')

            _guardar_contactos(cursor, id_cliente, contactos, tenant_id)
            conn.commit()
            flash("Cliente guardado correctamente", "success")
    except ValueError as e:
        conn.rollback()
        flash(str(e), "danger")
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash("Ya existe un cliente con ese código.", "danger")
        else:
            flash(f"Error al guardar el cliente: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('clientes.listar'))


@clientes_bp.route('/clientes/eliminar/<int:id_cliente>', methods=['POST'])
def eliminar(id_cliente):
    """Inactiva el cliente (no se borra: sus pedidos lo conservan)."""
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT razonsocial, activo FROM clientes WHERE id_cliente = %s AND (%s IS NULL OR tenant_id = %s)",
                           (id_cliente, tenant_id, tenant_id))
            cliente = cursor.fetchone()
            if not cliente:
                flash("Cliente no encontrado.", "warning")
                return redirect(url_for('clientes.listar'))
            if not cliente['activo']:
                flash(f'El cliente "{cliente["razonsocial"]}" ya estaba inactivo.', "info")
                return redirect(url_for('clientes.listar'))

            cursor.execute("UPDATE clientes SET activo = %s WHERE id_cliente = %s", (False, id_cliente))
            cursor.execute("SELECT COUNT(*) AS n FROM pedidos_cabecera WHERE id_cliente = %s AND estado NOT IN (%s, %s)",
                           (id_cliente, *_PEDIDO_TERMINADO))
            en_curso = cursor.fetchone()['n']
            conn.commit()

            mensaje = f'El cliente "{cliente["razonsocial"]}" quedó inactivo: ya no se ofrece al cargar pedidos.'
            if en_curso:
                mensaje += (' Tiene 1 pedido sin despachar, que sigue su curso.' if en_curso == 1 else
                            f' Tiene {en_curso} pedidos sin despachar, que siguen su curso.')
            flash(mensaje + ' Se puede reactivar desde su edición.', "warning" if en_curso else "success")
    except Exception as e:
        conn.rollback()
        flash(f"No se pudo inactivar el cliente: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('clientes.listar'))



# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS_EXPORT = ['codigo', 'razonsocial', 'nombre_fantasia', 'cuit', 'direccion', 'localidad', 'provincia',
                  'telefono', 'email', 'sitio_web', 'contacto_nombre',
                  'id_ruta', 'nombre_ruta', 'id_transporte_predeterminado', 'nombre_transporte',
                  'activo']
_CAMPOS_IMPORT = ['codigo', 'razonsocial', 'nombre_fantasia', 'cuit', 'direccion', 'localidad', 'provincia',
                  'telefono', 'email', 'sitio_web', 'contacto_nombre',
                  'id_ruta', 'id_transporte_predeterminado', 'activo']
_EJEMPLO_IMPORT = ['CLI001', 'Cliente de Ejemplo S.A.', 'El Ejemplo', '20-87654321-0',
                   'Av. Corrientes 1234', 'Buenos Aires', 'Buenos Aires',
                   '011-5555-6666', 'cliente@ejemplo.com', 'www.ejemplo.com', 'Juan Pérez',
                   '', '', '1']   # sin ruta ni transporte: los del ejemplo tendrían que existir para poder importarlo


def _resolver_ruta(cursor, ref, tenant_id):
    """ID de la ruta indicada por su nombre (o por su ID); None si no se indicó. ValueError si no existe."""
    if not ref:
        return None
    cursor.execute(
        "SELECT id_ruta FROM rutas WHERE nombre_ruta = %s AND (%s IS NULL OR tenant_id = %s)",
        (ref, tenant_id, tenant_id))
    row = cursor.fetchone()
    if row:
        return row['id_ruta']
    try:
        return _id_propio(cursor, 'rutas', 'id_ruta', ref, tenant_id, 'Ruta')
    except ValueError:
        raise ValueError(f'Ruta "{ref}": no existe.') from None


def _resolver_transporte(cursor, ref, tenant_id):
    """ID del transporte indicado por su código (o por su ID); None si no se indicó. ValueError si no existe."""
    if not ref:
        return None
    cursor.execute(
        "SELECT id_transporte FROM transportes WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)",
        (ref, tenant_id, tenant_id))
    row = cursor.fetchone()
    if row:
        return row['id_transporte']
    try:
        return _id_propio(cursor, 'transportes', 'id_transporte', ref, tenant_id, 'Transporte')
    except ValueError:
        raise ValueError(f'Transporte "{ref}": no existe.') from None


@clientes_bp.route('/clientes/importar', methods=['POST'])
def importar():
    tenant_id = get_tenant_filter()
    file = request.files.get('archivo')
    if not file or not file.filename:
        return jsonify({'error': 'No se proporcionó archivo'}), 400
    try:
        rows = parse_file(file, request.form.get('hoja'))
    except Exception as e:
        return jsonify({'error': f'Error al leer el archivo: {e!s}'}), 400

    insertados, actualizados, omitidos, errores = 0, 0, [], []
    conn = get_db_connection()
    try:
        for i, row in enumerate(rows, 1):
            codigo = str(row.get('codigo', '') or '').strip()
            razon = str(row.get('razonsocial', '') or '').strip()
            if not codigo or not razon:
                errores.append({'fila': i, 'codigo': codigo or '(vacío)',
                                'razon': 'Código y Razón Social son obligatorios'})
                continue
            try:
                with conn.cursor() as cursor:
                    id_ruta = _resolver_ruta(cursor, str(row.get('id_ruta', '') or '').strip(), tenant_id)
                    id_transporte = _resolver_transporte(cursor, str(row.get('id_transporte_predeterminado', '') or '').strip(), tenant_id)
                    cursor.execute("SELECT id_cliente FROM clientes WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)", (codigo, tenant_id, tenant_id))
                    existing = cursor.fetchone()
                    if existing:
                        # De un cliente existente solo se cambia la ruta o el transporte que el archivo
                        # trae con dato: una columna ausente o vacía no le quita el que tiene
                        cambios = {col: valor for col, valor in (('id_ruta', id_ruta),
                                                                 ('id_transporte_predeterminado', id_transporte))
                                   if valor is not None}
                        if not cambios:
                            omitidos.append(codigo)
                            continue
                        cursor.execute(f"UPDATE clientes SET {', '.join(f'{col} = %s' for col in cambios)} WHERE id_cliente = %s",
                                       (*cambios.values(), existing['id_cliente']))
                        actualizados += 1
                        continue
                    datos = _datos_del_cliente(row)
                    contacto = _texto(row, 'contacto_nombre')
                    id_nuevo = execute_insert(cursor, """
                        INSERT INTO clientes
                            (codigo, razonsocial, cuit, direccion, localidad, provincia,
                             telefono, email, contacto_nombre,
                             id_ruta, id_transporte_predeterminado, activo,
                             nombre_fantasia, sitio_web, tenant_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        datos['codigo'], datos['razonsocial'],
                        datos['cuit'],
                        datos['direccion'],
                        datos['localidad'],
                        datos['provincia'],
                        datos['telefono'],
                        datos['email'],
                        contacto,
                        id_ruta,
                        id_transporte,
                        _activo(row.get('activo')),
                        datos['nombre_fantasia'],
                        datos['sitio_web'],
                        tenant_id
                    ), id_col='id_cliente')
                    if contacto:
                        # La importación trae un solo contacto: queda como el primero del cliente
                        _guardar_contactos(cursor, id_nuevo, [{'nombre': contacto}], tenant_id)
                    insertados += 1
            except Exception as e:
                errores.append({'fila': i, 'codigo': codigo, 'razon': str(e)})
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
    return jsonify({'insertados': insertados, 'actualizados': actualizados,
                    'omitidos': omitidos, 'errores': errores})


@clientes_bp.route('/clientes/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT c.codigo, c.razonsocial, c.nombre_fantasia, c.cuit, c.direccion, c.localidad, c.provincia,
                       c.telefono, c.email, c.sitio_web, c.contacto_nombre,
                       c.id_ruta, r.nombre_ruta,
                       c.id_transporte_predeterminado, t.codigo AS codigo_transporte,
                       t.razonsocial AS nombre_transporte, c.activo
                FROM clientes c
                LEFT JOIN rutas r ON c.id_ruta = r.id_ruta
                LEFT JOIN transportes t ON c.id_transporte_predeterminado = t.id_transporte
                WHERE (%s IS NULL OR c.tenant_id = %s)
                ORDER BY c.razonsocial
            """, (tenant_id, tenant_id))
            rows = [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()
    for r in rows:
        # La ruta va por su nombre y el transporte por su código, que es como los lee la importación:
        # los ID internos cambian de un servidor a otro y el archivo no se podía reimportar
        r['id_ruta'] = r['nombre_ruta'] or r['id_ruta']
        r['id_transporte_predeterminado'] = r.pop('codigo_transporte') or r['id_transporte_predeterminado']

    if formato == 'csv':
        return export_csv(rows, _CAMPOS_EXPORT, 'clientes.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS_EXPORT, 'clientes.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS_EXPORT, 'clientes.xlsx')
    return 'Formato no válido', 400


@clientes_bp.route('/clientes/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_clientes.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_clientes.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_clientes.xlsx')
    return 'Formato no válido', 400
