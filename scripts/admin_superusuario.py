"""
admin_superusuario.py — Administración por consola de los usuarios del panel admin.

Menú interactivo para gestionar la tabla `admin_usuarios` de `taurus_admin`
(usuarios que ingresan a admin.py, puerto 5001). No toca los usuarios del WMS
(`taurus_admin.usuarios`); para esos ver `scripts/alta_usuario.py` o el panel admin.

Uso (desde cualquier directorio):
    python scripts/admin_superusuario.py [--config ruta.json]
    python -m scripts.admin_superusuario      # equivalente, desde la raíz
    superusuario-dist/superusuario.exe [--config ruta.json]   # ejecutable portable

Conexión (primera que aplique):
    1. --config <ruta.json>
    2. superusuario.json junto al ejecutable (o junto a este script)
    3. Solo ejecutando con Python: variables DB_ADMIN_* del .env de la raíz.
    El JSON tiene las claves engine (mysql|postgresql|sqlserver, default mysql),
    host, port, user, password, database y opcional charset; ver
    superusuario-dist/superusuario.example.json. Se conecta con
    `_get_admin_connection()` de modules/db_config.py.
    El ejecutable se construye con `python scripts/build_superusuario.py`.

Opciones del menú:
    1 — Crear / Actualizar usuario
        Si el username no existe lo crea (rol por defecto ADMIN). Si existe y
        está activo, lo actualiza: cualquier campo dejado en blanco (incluida
        la contraseña) mantiene su valor actual. Si existe y está inactivo,
        pide reactivarlo primero con la opción 3.
    2 — Dar de baja: baja lógica (`activo = FALSE`); no borra el registro.
    3 — Activar: revierte la baja (`activo = TRUE`).
    4 — Listar: todos los usuarios o filtrados por username/nombre/email (LIKE).
    5 — Salir (también Ctrl+C).

Validaciones:
    - Rol: solo SUPERADMIN o ADMIN (SUPERADMIN habilita parámetros de tenants,
      tokens de API e intercambio en el panel).
    - No permite dar de baja ni degradar al último SUPERADMIN activo (quedaría
      el panel sin nadie que pueda gestionar parámetros ni superusuarios).
    - Email opcional, con formato validado.
    - Contraseña según modules/passwords.py (mínimo PASSWORD_MIN_LEN), ingresada
      dos veces y oculta (getpass) cuando hay TTY.
    - Hash con werkzeug scrypt (salt de 32), igual que el login del panel.
    - Toda escritura pide confirmación S/N y hace commit inmediato; si la BD
      falla se hace rollback, se informa el error y el menú sigue.

Nota: herramienta de desarrollo/soporte, no forma parte de las apps.
"""
import argparse
import getpass
import json
import os
import re
import sys
from pathlib import Path

# Empaquetado con PyInstaller (superusuario.exe) los módulos vienen dentro del
# ejecutable; con Python se agrega la raíz del proyecto a sys.path para poder
# importar `modules` aunque se ejecute como `python scripts/admin_superusuario.py`.
CONGELADO = getattr(sys, 'frozen', False)
ROOT = Path(__file__).resolve().parent.parent
if not CONGELADO and str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from werkzeug.security import generate_password_hash

from modules.db_config import _get_admin_connection
from modules.passwords import PASSWORD_MIN_LEN, validar_password

ROLES_VALIDOS = ('SUPERADMIN', 'ADMIN')
COLUMNAS_USUARIO = "id, username, nombre, email, rol, activo"
CONFIG_NOMBRE = 'superusuario.json'
# Clave del JSON -> variable que lee modules/db_config.py
CONFIG_A_ENV = {
    'engine': 'DB_ADMIN_ENGINE',
    'host': 'DB_ADMIN_HOST',
    'port': 'DB_ADMIN_PORT',
    'user': 'DB_ADMIN_USER',
    'password': 'DB_ADMIN_PASSWORD',
    'database': 'DB_ADMIN_NAME',
    'charset': 'DB_CHAR_SET',
}
CONFIG_OBLIGATORIAS = ('host', 'user', 'password', 'database')
ENGINES_SOPORTADOS = ('mysql', 'postgresql', 'sqlserver')


class Color:
    """Códigos ANSI para colorear la salida de consola."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    DIM = "\033[2m"


# --- Salida por consola ---

def limpiar_pantalla():
    os.system('cls' if os.name == 'nt' else 'clear')


CONEXION_DESC = ""  # destino de la conexión, lo completa main()


def mostrar_titulo():
    print(f"\n{Color.CYAN}{Color.BOLD}{'=' * 60}")
    print("  TAURUS WMS — Administración de Superusuarios")
    print(f"{'=' * 60}{Color.RESET}")
    if CONEXION_DESC:
        print(f"  {Color.DIM}BD: {CONEXION_DESC}{Color.RESET}")
    print()


def mostrar_encabezado(subtitulo):
    limpiar_pantalla()
    mostrar_titulo()
    print(f"  {Color.BOLD}— {subtitulo}{Color.RESET}\n")


def mostrar_menu():
    print(f"  {Color.BOLD}1{Color.RESET} — Crear / Actualizar usuario")
    print(f"  {Color.BOLD}2{Color.RESET} — Dar de baja un usuario")
    print(f"  {Color.BOLD}3{Color.RESET} — Activar usuario")
    print(f"  {Color.BOLD}4{Color.RESET} — Listar usuarios")
    print(f"  {Color.BOLD}5{Color.RESET} — Salir")
    print()


def exito(msg):
    print(f"\n  {Color.GREEN}{Color.BOLD}[OK]{Color.RESET} {msg}")


def error(msg):
    print(f"\n  {Color.RED}{Color.BOLD}[ERROR]{Color.RESET} {msg}")


def info(msg):
    print(f"\n  {Color.CYAN}[INFO]{Color.RESET} {msg}")


def advertencia(msg):
    print(f"\n  {Color.YELLOW}[AVISO]{Color.RESET} {msg}")


def pausa():
    input("\n  Enter para continuar...")


def mostrar_usuario(usuario):
    """Imprime la ficha de un registro de admin_usuarios (dict de DictCursor)."""
    estado = f"{Color.GREEN}Activo{Color.RESET}" if usuario['activo'] else f"{Color.RED}Inactivo{Color.RESET}"
    print(f"\n  {Color.DIM}ID:{Color.RESET}       {usuario['id']}")
    print(f"  {Color.DIM}Usuario:{Color.RESET}  {usuario['username']}")
    print(f"  {Color.DIM}Nombre:{Color.RESET}   {usuario['nombre']}")
    print(f"  {Color.DIM}Email:{Color.RESET}    {usuario['email'] or '—'}")
    print(f"  {Color.DIM}Rol:{Color.RESET}     {usuario['rol']}")
    print(f"  {Color.DIM}Estado:{Color.RESET}  {estado}")


def mostrar_resumen(username, nombre, email, rol, password):
    print(f"\n  {Color.BOLD}Resumen:{Color.RESET}")
    print(f"  Usuario:    {username}")
    print(f"  Nombre:     {nombre}")
    print(f"  Email:      {email or '—'}")
    print(f"  Rol:        {rol}")
    print(f"  Contraseña: {'(se cambia)' if password else '(sin cambios)'}")


def truncar(texto, max_len):
    """Recorta el texto a max_len caracteres terminando en '..' (para las columnas del listado)."""
    texto = str(texto) if texto else ""
    return texto[:max_len - 2] + ".." if len(texto) > max_len else texto


# --- Entrada por consola ---

def confirmar(prompt="  Confirma la operación (S/N): "):
    """Devuelve True solo si el usuario responde 's' (sin distinguir mayúsculas)."""
    return input(prompt).strip().lower() == 's'


def pedir_input(prompt, obligatorio=True):
    """Lee un valor de consola. Devuelve None si es obligatorio y está vacío."""
    valor = input(prompt).strip()
    if obligatorio and not valor:
        error("Este campo es obligatorio.")
        return None
    return valor


def _leer_password(prompt):
    return getpass.getpass(prompt) if sys.stdin.isatty() else input(prompt)


def pedir_password_nueva(obligatoria=True):
    """
    Pide la contraseña dos veces y la valida.

    Devuelve la contraseña, "" si no es obligatoria y se dejó en blanco
    (mantener la actual), o None si no es válida.
    """
    etiqueta = "Contraseña" if obligatoria else "Nueva contraseña (Enter = mantener actual)"
    password = _leer_password(f"  {etiqueta} (mín. {PASSWORD_MIN_LEN}): ")
    if not password and not obligatoria:
        return ""
    mensaje = validar_password(password)
    if mensaje:
        error(mensaje)
        return None
    if password != _leer_password("  Confirmar contraseña: "):
        error("Las contraseñas no coinciden.")
        return None
    return password


def pedir_email(actual=None):
    """Pide un email opcional. Devuelve el valor (o el actual si se deja en blanco) o None si es inválido."""
    sufijo = f" [{actual or ''}]" if actual is not None else ""
    email = pedir_input(f"  Email{sufijo}: ", obligatorio=False) or (actual or "")
    if email and not validar_email(email):
        error("Formato de email inválido.")
        return None
    return email


def pedir_rol(actual):
    """Pide el rol (default: actual). Devuelve el rol normalizado o None si es inválido."""
    rol = (pedir_input(f"  Rol ({'/'.join(ROLES_VALIDOS)}) [{actual}]: ", obligatorio=False) or actual).upper()
    if rol not in ROLES_VALIDOS:
        error(f"Rol inválido. Debe ser {' o '.join(ROLES_VALIDOS)}.")
        return None
    return rol


def validar_email(email):
    """True si el email está vacío (es opcional) o tiene formato válido."""
    if not email:
        return True
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))


# --- Acceso a datos ---

def buscar_usuario(cursor, username):
    cursor.execute(f"SELECT {COLUMNAS_USUARIO} FROM admin_usuarios WHERE username = %s", (username,))
    return cursor.fetchone()


def es_ultimo_superadmin(cursor, usuario):
    """True si `usuario` es el único SUPERADMIN activo."""
    if usuario['rol'] != 'SUPERADMIN' or not usuario['activo']:
        return False
    cursor.execute(
        "SELECT COUNT(*) AS total FROM admin_usuarios WHERE rol = 'SUPERADMIN' AND activo = TRUE AND id <> %s",
        (usuario['id'],)
    )
    return cursor.fetchone()['total'] == 0


def _hash(password):
    return generate_password_hash(password, method="scrypt", salt_length=32)


# --- Opciones del menú ---

def crear_o_actualizar(conn, cursor):
    mostrar_encabezado("Crear / Actualizar usuario")

    username = pedir_input("  Username: ")
    if username is None:
        return

    usuario = buscar_usuario(cursor, username)
    if usuario:
        _actualizar(conn, cursor, usuario)
    else:
        _crear(conn, cursor, username)


def _actualizar(conn, cursor, usuario):
    username = usuario['username']
    mostrar_usuario(usuario)
    if not usuario['activo']:
        error(f"El usuario '{username}' está inactivo. Use la opción 3 para reactivarlo.")
        return

    print(f"\n  {Color.YELLOW}Modo: Actualizar usuario existente{Color.RESET}")
    print("  (Dejar en blanco para mantener el valor actual)\n")

    password = pedir_password_nueva(obligatoria=False)
    if password is None:
        return
    nombre = pedir_input(f"  Nombre [{usuario['nombre']}]: ", obligatorio=False) or usuario['nombre']
    email = pedir_email(actual=usuario['email'])
    if email is None:
        return
    rol = pedir_rol(usuario['rol'])
    if rol is None:
        return

    if rol != 'SUPERADMIN' and es_ultimo_superadmin(cursor, usuario):
        error(f"'{username}' es el último SUPERADMIN activo; no se puede cambiar su rol.")
        return

    mostrar_resumen(username, nombre, email, rol, password)
    if not confirmar():
        info("Operación cancelada.")
        return

    if password:
        cursor.execute(
            "UPDATE admin_usuarios SET password_hash = %s, nombre = %s, email = %s, rol = %s WHERE id = %s",
            (_hash(password), nombre, email, rol, usuario['id'])
        )
    else:
        cursor.execute(
            "UPDATE admin_usuarios SET nombre = %s, email = %s, rol = %s WHERE id = %s",
            (nombre, email, rol, usuario['id'])
        )
    conn.commit()
    exito(f"Usuario '{username}' actualizado exitosamente")


def _crear(conn, cursor, username):
    info(f"El usuario '{username}' no existe. Se creará uno nuevo.\n")

    password = pedir_password_nueva(obligatoria=True)
    if password is None:
        return
    nombre = pedir_input("  Nombre completo: ")
    if nombre is None:
        return
    email = pedir_email()
    if email is None:
        return
    rol = pedir_rol('ADMIN')
    if rol is None:
        return

    mostrar_resumen(username, nombre, email, rol, password)
    if not confirmar():
        info("Operación cancelada.")
        return

    cursor.execute(
        "INSERT INTO admin_usuarios (username, password_hash, nombre, email, rol) VALUES (%s, %s, %s, %s, %s)",
        (username, _hash(password), nombre, email, rol)
    )
    conn.commit()
    exito(f"Usuario '{username}' creado exitosamente")


def cambiar_estado(conn, cursor, activar):
    accion = "Activar" if activar else "Dar de baja"
    mostrar_encabezado(f"{accion} usuario")

    username = pedir_input(f"  Username a {'activar' if activar else 'dar de baja'}: ")
    if username is None:
        return

    usuario = buscar_usuario(cursor, username)
    if not usuario:
        error(f"El usuario '{username}' no existe.")
        return
    if bool(usuario['activo']) == activar:
        advertencia(f"El usuario '{username}' ya está {'activo' if activar else 'dado de baja'}.")
        return

    mostrar_usuario(usuario)
    if not activar:
        if es_ultimo_superadmin(cursor, usuario):
            error(f"'{username}' es el último SUPERADMIN activo; no se puede dar de baja.")
            return
        print(f"\n  {Color.RED}Se desactivará el acceso de este usuario.{Color.RESET}")

    if not confirmar(f"  ¿Confirmar {'la activación' if activar else 'la baja'}? (S/N): "):
        info("Operación cancelada.")
        return

    cursor.execute("UPDATE admin_usuarios SET activo = %s WHERE id = %s", (activar, usuario['id']))
    conn.commit()
    exito(f"Usuario '{username}' {'activado' if activar else 'dado de baja'} exitosamente")


def listar(cursor):
    mostrar_encabezado("Listar usuarios")

    filtro = pedir_input("  Buscar (nombre, email o username, Enter para todos): ", obligatorio=False)

    sql = f"SELECT {COLUMNAS_USUARIO}, ultimo_acceso, created_at FROM admin_usuarios"
    params = ()
    if filtro:
        like = f"%{filtro}%"
        sql += " WHERE username LIKE %s OR nombre LIKE %s OR email LIKE %s"
        params = (like, like, like)
    cursor.execute(sql + " ORDER BY id", params)
    usuarios = cursor.fetchall()

    if not usuarios:
        advertencia("No se encontraron usuarios.")
        return

    cols = [
        ("ID", 5), ("Username", 18), ("Nombre", 25), ("Email", 28),
        ("Rol", 14), ("Estado", 10), ("Últ. acceso", 18), ("Creado", 18)
    ]
    header = "".join(f"{Color.BOLD}{c[0]:<{c[1]}}{Color.RESET}" for c in cols)
    print(f"\n  {header}")
    print(f"  {'-' * sum(c[1] for c in cols)}")

    for u in usuarios:
        if u['activo']:
            estado = f"{Color.GREEN}{'Activo':<10}{Color.RESET}"
        else:
            estado = f"{Color.RED}{'Inactivo':<10}{Color.RESET}"
        ultimo = str(u['ultimo_acceso'])[:16] if u['ultimo_acceso'] else "Nunca"
        creado = str(u['created_at'])[:16] if u['created_at'] else "N/A"
        row = (
            f"{u['id']:<5}"
            f"{truncar(u['username'], 18):<18}"
            f"{truncar(u['nombre'], 25):<25}"
            f"{truncar(u['email'], 28):<28}"
            f"{u['rol']:<14}"
            f"{estado}"
            f"{ultimo:<18}"
            f"{creado:<18}"
        )
        print(f"  {row}")

    activos = sum(1 for u in usuarios if u['activo'])
    inactivos = len(usuarios) - activos
    print(f"\n  {Color.DIM}Total: {len(usuarios)} usuario(s) — {Color.GREEN}{activos} activo(s){Color.RESET}"
          f"{Color.DIM}, {Color.RED}{inactivos} inactivo(s){Color.RESET}")


# --- Configuración de conexión ---

class ConfigError(Exception):
    pass


def _directorio_base():
    """Carpeta donde se busca superusuario.json: la del .exe o la de este script."""
    return Path(sys.executable).resolve().parent if CONGELADO else Path(__file__).resolve().parent


def cargar_config_json(ruta):
    """Valida el JSON de conexión y lo vuelca a las variables DB_ADMIN_* (pisa el .env)."""
    try:
        with open(ruta, encoding='utf-8-sig') as fh:
            datos = json.load(fh)
    except json.JSONDecodeError as e:
        raise ConfigError(f"{ruta} no es un JSON válido (línea {e.lineno}, columna {e.colno}): {e.msg}") from None
    except OSError as e:
        raise ConfigError(f"No se pudo leer {ruta}: {e.strerror}") from None

    if not isinstance(datos, dict):
        raise ConfigError(f"{ruta} debe contener un objeto JSON {{...}}")
    desconocidas = sorted(set(datos) - set(CONFIG_A_ENV))
    if desconocidas:
        raise ConfigError(f"Claves desconocidas en {ruta}: {', '.join(desconocidas)} "
                          f"(válidas: {', '.join(CONFIG_A_ENV)})")
    faltantes = [k for k in CONFIG_OBLIGATORIAS if datos.get(k) in (None, '')]
    if faltantes:
        raise ConfigError(f"Faltan claves obligatorias en {ruta}: {', '.join(faltantes)}")
    engine = str(datos.get('engine', 'mysql')).strip().lower()
    if engine not in ENGINES_SOPORTADOS:
        raise ConfigError(f"engine '{engine}' no soportado (usar: {', '.join(ENGINES_SOPORTADOS)})")
    if 'port' in datos and not str(datos['port']).isdigit():
        raise ConfigError(f"port debe ser numérico: {datos['port']!r}")

    datos['engine'] = engine
    # El JSON es la única fuente: se descartan DB_ADMIN_* que db_config haya
    # tomado de algún .env, para no mezclar (p. ej. un port de otro entorno).
    for var in CONFIG_A_ENV.values():
        os.environ.pop(var, None)
    for clave, valor in datos.items():
        os.environ[CONFIG_A_ENV[clave]] = str(valor)
    return datos


def resolver_config(ruta_cli=None):
    """Aplica la configuración de conexión y devuelve una descripción (sin password)."""
    ruta = Path(ruta_cli) if ruta_cli else _directorio_base() / CONFIG_NOMBRE
    if ruta_cli or ruta.exists():
        datos = cargar_config_json(ruta)
        return f"{datos['engine']}://{datos['user']}@{datos['host']}:{datos.get('port', 'default')}/{datos['database']} ({ruta.name})"
    if CONGELADO:
        raise ConfigError(
            f"No se encontró {CONFIG_NOMBRE} junto al ejecutable ({ruta.parent}).\n"
            f"  Copie superusuario.example.json como {CONFIG_NOMBRE} y complete las credenciales,\n"
            f"  o indique otro archivo con --config <ruta.json>."
        )
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ROOT / '.env')
    return (f"{os.getenv('DB_ADMIN_ENGINE', 'mysql')}://{os.getenv('DB_ADMIN_USER', '')}@"
            f"{os.getenv('DB_ADMIN_HOST', 'localhost')}/{os.getenv('DB_ADMIN_NAME', 'taurus_admin')} (.env)")


# --- Bucle principal: una sola conexión a taurus_admin para toda la sesión ---

def main(argv=None):
    parser = argparse.ArgumentParser(description="Administración de usuarios del panel admin de Taurus WMS")
    parser.add_argument('--config', help=f"JSON de conexión (default: {CONFIG_NOMBRE} junto al ejecutable)")
    args = parser.parse_args(argv)

    try:
        destino = resolver_config(args.config)
        conn = _get_admin_connection()
    except ConfigError as e:
        error(str(e))
        return 1
    except Exception as e:
        error(f"No se pudo conectar a la BD admin: {e}")
        return 1
    cursor = conn.cursor()
    global CONEXION_DESC
    CONEXION_DESC = destino

    acciones = {
        "1": lambda: crear_o_actualizar(conn, cursor),
        "2": lambda: cambiar_estado(conn, cursor, activar=False),
        "3": lambda: cambiar_estado(conn, cursor, activar=True),
        "4": lambda: listar(cursor),
    }

    limpiar_pantalla()
    try:
        while True:
            mostrar_titulo()
            mostrar_menu()
            opcion = input(f"  {Color.BOLD}Opción:{Color.RESET} ").strip()

            if opcion == "5":
                info("Hasta luego.")
                break
            accion = acciones.get(opcion)
            if accion is None:
                error("Opción inválida. Intente de nuevo.")
                pausa()
                continue

            try:
                accion()
            except KeyboardInterrupt:
                print()
                info("Operación cancelada.")
            except Exception as e:
                conn.rollback()
                error(f"Error de base de datos: {e}")
            pausa()
            limpiar_pantalla()
    except (KeyboardInterrupt, EOFError):
        print()
        info("Hasta luego.")
    finally:
        cursor.close()
        conn.close()
    return 0


if __name__ == "__main__":
    codigo = main()
    if CONGELADO and codigo:
        # Abierto con doble clic: que la consola no se cierre sin mostrar el error
        input("\n  Enter para salir...")
    sys.exit(codigo)
