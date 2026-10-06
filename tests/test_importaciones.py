"""Los CSV de prueba de Importaciones/ se tienen que poder importar tal cual están.

La carpeta trae un juego de archivos para cargar los maestros a mano desde las
pantallas (ver Importaciones/LEEME.txt). Este test los importa en orden y
verifica el resultado, así los archivos no quedan desactualizados cuando cambia
una importación. Al terminar borra solo lo que él mismo insertó.
"""

import csv
import io
from pathlib import Path

import pytest

from tests.conftest import requires_db

CARPETA = Path(__file__).resolve().parent.parent / 'Importaciones'

# Archivo, ruta de importación, tabla, columna que identifica cada fila (en el archivo y en la tabla)
MAESTROS = [
    ('01_unidades.csv', '/unidades/importar', 'unidades_medida', 'codigo'),
    ('02_categorias.csv', '/categorias/importar', 'categorias', 'codigo'),
    ('03_proveedores.csv', '/proveedores/importar', 'proveedores', 'codigo'),
    ('04_rutas.csv', '/rutas/importar', 'rutas', 'nombre_ruta'),
    ('05_transportes.csv', '/transportes/importar', 'transportes', 'codigo'),
    ('06_clientes.csv', '/clientes/importar', 'clientes', 'codigo'),
    ('07_materiales.csv', '/materiales/importar', 'materiales', 'codigo'),
    ('08_clases_pedido.csv', '/clases-pedido/importar', 'clases_pedido', 'nombre'),
]
CON_ERRORES = [
    ('unidades_con_errores.csv', '/unidades/importar', 'unidades_medida', 'codigo'),
    ('proveedores_con_errores.csv', '/proveedores/importar', 'proveedores', 'codigo'),
    ('clientes_con_errores.csv', '/clientes/importar', 'clientes', 'codigo'),
    ('materiales_con_errores.csv', '/materiales/importar', 'materiales', 'codigo'),
]


def _claves(ruta, columna):
    with open(ruta, encoding='utf-8-sig', newline='') as fh:
        return [fila[columna] for fila in csv.DictReader(fh) if fila[columna]]


def _existentes(cur, tabla, columna, tenant):
    cur.execute(f"SELECT {columna} AS clave FROM {tabla} WHERE tenant_id = %s", (tenant,))
    return {str(r['clave']) for r in cur.fetchall()}


@pytest.fixture
def base_limpia_al_final(usuario_wms):
    """Recuerda qué había antes en cada tabla y, al final, borra solo las filas nuevas de los archivos."""
    from modules.db_config import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    tenant = usuario_wms['tenant_id']
    previas = {(tabla, columna): _existentes(cur, tabla, columna, tenant)
               for _, _, tabla, columna in MAESTROS}
    conn.commit()
    yield conn
    conn.commit()
    # En orden inverso: primero lo que referencia a lo demás
    for carpeta, lista in ((CARPETA, MAESTROS), (CARPETA / 'con_errores', CON_ERRORES)):
        for archivo, _, tabla, columna in reversed(lista):
            for clave in _claves(carpeta / archivo, columna):
                if clave not in previas[(tabla, columna)]:
                    cur.execute(f"DELETE FROM {tabla} WHERE {columna} = %s AND tenant_id = %s", (clave, tenant))
    conn.commit()
    conn.close()


def _importar(client, ruta_archivo, url):
    r = client.post(url, data={'archivo': (io.BytesIO(ruta_archivo.read_bytes()), ruta_archivo.name)},
                    content_type='multipart/form-data')
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


@requires_db
def test_los_csv_de_prueba_se_importan_sin_errores(logged_client, base_limpia_al_final, usuario_wms):
    conn, tenant = base_limpia_al_final, usuario_wms['tenant_id']
    for archivo, url, _tabla, columna in MAESTROS:
        filas = _claves(CARPETA / archivo, columna)
        resultado = _importar(logged_client, CARPETA / archivo, url)
        assert resultado['errores'] == [], f'{archivo}: {resultado["errores"]}'
        # Cada fila se inserta, o se omite/actualiza si ya existía en la base de pruebas
        procesadas = resultado['insertados'] + len(resultado['omitidos']) + resultado.get('actualizados', 0)
        assert procesadas == len(filas), f'{archivo}: {resultado}'

    # Lo importado queda vinculado entre sí: las referencias por código se resolvieron
    conn.commit()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.codigo_alternativo, m.codigo_proveedor, m.stock_reposicion, m.volumen, m.activo,
               c.codigo AS categoria, u.codigo AS unidad, uv.codigo AS unidad_volumen, p.codigo AS proveedor
        FROM materiales m
        LEFT JOIN categorias c ON c.id_categoria = m.categoria_id
        LEFT JOIN unidades_medida u ON u.id_unidad = m.unidad_medida_id
        LEFT JOIN unidades_medida uv ON uv.id_unidad = m.volumen_unidad_id
        LEFT JOIN material_proveedor mp ON mp.id_material = m.id AND mp.es_habitual = 1
        LEFT JOIN proveedores p ON p.id = mp.id_proveedor
        WHERE m.codigo = 'PIN-LAT-20' AND m.tenant_id = %s
    """, (tenant,))
    latex = cur.fetchone()
    assert (latex['categoria'], latex['unidad'], latex['unidad_volumen'], latex['proveedor']) == ('PIN', 'UN', 'L', 'PROV003')
    assert (latex['codigo_alternativo'], latex['codigo_proveedor']) == ('LAT-INT-20', 'PL-2001')
    assert float(latex['stock_reposicion']) == 20 and float(latex['volumen']) == 20 and latex['activo']

    cur.execute("SELECT codigo_alternativo, codigo_proveedor FROM materiales WHERE codigo = 'ARA-PLA-14' AND tenant_id = %s", (tenant,))
    assert cur.fetchone() == {'codigo_alternativo': 'ARA-PLA-14', 'codigo_proveedor': 'ARA-PLA-14'}   # por defecto, el código

    cur.execute("SELECT unidad_base_referencia, conversion_a_base FROM unidades_medida WHERE codigo = 'MM' AND tenant_id = %s", (tenant,))
    mm = cur.fetchone()
    assert mm['unidad_base_referencia'] == 'M' and float(mm['conversion_a_base']) == 0.001

    cur.execute("""SELECT c.nombre_fantasia, c.sitio_web, c.cuit, c.activo, r.nombre_ruta, t.codigo AS transporte,
                          (SELECT COUNT(*) FROM cliente_contactos cc WHERE cc.id_cliente = c.id_cliente) AS contactos
                   FROM clientes c
                   LEFT JOIN rutas r ON r.id_ruta = c.id_ruta
                   LEFT JOIN transportes t ON t.id_transporte = c.id_transporte_predeterminado
                   WHERE c.codigo = 'CLI002' AND c.tenant_id = %s""", (tenant,))
    cliente = cur.fetchone()
    assert cliente['cuit'] == '30-70987654-3'                    # venía sin guiones
    assert (cliente['nombre_ruta'], cliente['transporte'], cliente['contactos']) == ('Zona Norte', 'TRA003', 1)

    cur.execute("SELECT nombre, activo FROM clases_pedido WHERE nombre IN ('Urgente', 'Exportación') AND tenant_id = %s ORDER BY nombre", (tenant,))
    assert [(c['nombre'], bool(c['activo'])) for c in cur.fetchall()] == [('Exportación', False), ('Urgente', True)]

    cur.execute("SELECT cuit, CHAR_LENGTH(direccion) AS largo FROM proveedores WHERE codigo = 'PROV005' AND tenant_id = %s", (tenant,))
    assert cur.fetchone()['largo'] > 255                         # la dirección ampliada


@requires_db
def test_los_csv_con_errores_muestran_las_validaciones(logged_client, base_limpia_al_final):
    esperado = {
        'unidades_con_errores.csv': (1, 6, ['Unidad base: no existe', 'es de otra magnitud', 'Tipo de magnitud',
                                           'mayor que cero', 'entre 0 y 4', 'obligatorios']),
        'proveedores_con_errores.csv': (1, 4, ['CUIT inválido', 'CUIT inválido', 'Dirección', 'obligatorios']),
        'clientes_con_errores.csv': (1, 3, ['CUIT inválido', 'Mail principal', 'Sitio web']),
        'materiales_con_errores.csv': (1, 8, ['dígito verificador', 'categoria_id', 'no puede ser mayor que el stock máximo',
                                             'mínimo no puede ser mayor', 'falta indicar la unidad', 'tiene que ser una imagen',
                                             'id_proveedor_habitual', 'obligatorios']),
    }
    for archivo, url, _tabla, _columna in CON_ERRORES:
        insertados, errores, textos = esperado[archivo]
        resultado = _importar(logged_client, CARPETA / 'con_errores' / archivo, url)
        razones = [e['razon'] for e in resultado['errores']]
        assert resultado['insertados'] == insertados and len(razones) == errores, f'{archivo}: {resultado}'
        for texto, razon in zip(textos, razones, strict=True):
            assert texto in razon, f'{archivo}: se esperaba "{texto}" en "{razon}"'
