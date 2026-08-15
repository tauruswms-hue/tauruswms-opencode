import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

from modules.db_config import _get_admin_connection

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    DIM = "\033[2m"


def limpiar_pantalla():
    os.system('cls' if os.name == 'nt' else 'clear')


def mostrar_titulo():
    print(f"\n{Color.CYAN}{Color.BOLD}{'=' * 60}")
    print("  TAURUS WMS — Administración de Superusuarios")
    print(f"{'=' * 60}{Color.RESET}\n")


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


def confirmar(prompt="  Confirma la operación (S/N): "):
    resp = input(prompt).strip().lower()
    return resp == 's'


def pedir_input(prompt, obligatorio=True):
    try:
        valor = input(prompt).strip()
        if obligatorio and not valor:
            error("Este campo es obligatorio.")
            return None
        return valor
    except KeyboardInterrupt:
        print()
        return None


def pedir_password(prompt="  Contraseña: "):
    import getpass
    try:
        pw = getpass.getpass(prompt) if sys.stdin.isatty() else input(prompt)
    except (KeyboardInterrupt, getpass.GetPassWarning, OSError):
        print()
        return None
    if not pw:
        error("La contraseña no puede estar vacía.")
        return None
    return pw


def validar_email(email):
    if not email:
        return True
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))


def truncar(texto, max_len):
    texto = str(texto) if texto else ""
    return texto[:max_len - 2] + ".." if len(texto) > max_len else texto


def mostrar_usuario(usuario):
    estado = f"{Color.GREEN}Activo{Color.RESET}" if usuario['activo'] else f"{Color.RED}Inactivo{Color.RESET}"
    print(f"\n  {Color.DIM}ID:{Color.RESET}       {usuario['id']}")
    print(f"  {Color.DIM}Usuario:{Color.RESET}  {usuario['username']}")
    print(f"  {Color.DIM}Nombre:{Color.RESET}   {usuario['nombre']}")
    print(f"  {Color.DIM}Email:{Color.RESET}    {usuario['email'] or '—'}")
    print(f"  {Color.DIM}Rol:{Color.RESET}     {usuario['rol']}")
    print(f"  {Color.DIM}Estado:{Color.RESET}  {estado}")


conn = _get_admin_connection()
cursor = conn.cursor()

limpiar_pantalla()

while True:
    try:
        mostrar_titulo()
        mostrar_menu()
        opcion = input(f"  {Color.BOLD}Opción:{Color.RESET} ").strip()

        if opcion == "5":
            info("Hasta luego.")
            break

        elif opcion == "1":
            limpiar_pantalla()
            mostrar_titulo()
            print(f"  {Color.BOLD}— Crear / Actualizar usuario{Color.RESET}\n")

            username = pedir_input("  Username: ")
            if username is None:
                continue

            cursor.execute("SELECT id, username, nombre, email, rol, activo FROM admin_usuarios WHERE username = %s", (username,))
            usuario = cursor.fetchone()

            if usuario:
                mostrar_usuario(usuario)
                if not usuario['activo']:
                    error(f"El usuario '{username}' está inactivo. Use la opción 3 para reactivarlo.")
                    input("\n  Enter para continuar...")
                    continue

                print(f"\n  {Color.YELLOW}Modo: Actualizar usuario existente{Color.RESET}")
                print("  (Dejar en blanco para mantener el valor actual)\n")

                password = pedir_password("  Nueva contraseña: ")
                if password is None:
                    continue
                password2 = pedir_password("  Confirmar contraseña: ")
                if password2 is None:
                    continue
                if password != password2:
                    error("Las contraseñas no coinciden.")
                    input("\n  Enter para continuar...")
                    continue

                nombre = pedir_input(f"  Nombre [{usuario['nombre']}]: ", obligatorio=False) or usuario['nombre']
                email = pedir_input(f"  Email [{usuario['email'] or ''}]: ", obligatorio=False) or usuario['email']

                if email and not validar_email(email):
                    error("Formato de email inválido.")
                    input("\n  Enter para continuar...")
                    continue

                rol = pedir_input(f"  Rol (SUPERADMIN/ADMIN) [{usuario['rol']}]: ", obligatorio=False) or usuario['rol']
                rol = rol.upper()
                if rol not in ('SUPERADMIN', 'ADMIN'):
                    error("Rol inválido. Debe ser SUPERADMIN o ADMIN.")
                    input("\n  Enter para continuar...")
                    continue

                print(f"\n  {Color.BOLD}Resumen:{Color.RESET}")
                print(f"  Usuario:    {username}")
                print(f"  Nombre:     {nombre}")
                print(f"  Email:      {email or '—'}")
                print(f"  Rol:        {rol}")
                print(f"  Contraseña: {'*' * len(password)}")

                if not confirmar():
                    continue

                password_hash = generate_password_hash(password, method="scrypt", salt_length=32)
                cursor.execute("""
                    UPDATE admin_usuarios SET password_hash = %s, nombre = %s, email = %s, rol = %s WHERE username = %s
                """, (password_hash, nombre, email, rol, username))
                conn.commit()
                exito(f"Usuario '{username}' actualizado exitosamente")
            else:
                info(f"El usuario '{username}' no existe. Se creará uno nuevo.\n")

                password = pedir_password("  Contraseña: ")
                if password is None:
                    continue
                password2 = pedir_password("  Confirmar contraseña: ")
                if password2 is None:
                    continue
                if password != password2:
                    error("Las contraseñas no coinciden.")
                    input("\n  Enter para continuar...")
                    continue

                nombre = pedir_input("  Nombre completo: ")
                if nombre is None:
                    continue

                email = pedir_input("  Email: ", obligatorio=False) or ""
                if email and not validar_email(email):
                    error("Formato de email inválido.")
                    input("\n  Enter para continuar...")
                    continue

                rol = pedir_input("  Rol (SUPERADMIN/ADMIN) [ADMIN]: ", obligatorio=False) or "ADMIN"
                rol = rol.upper()
                if rol not in ('SUPERADMIN', 'ADMIN'):
                    error("Rol inválido. Debe ser SUPERADMIN o ADMIN.")
                    input("\n  Enter para continuar...")
                    continue

                print(f"\n  {Color.BOLD}Resumen:{Color.RESET}")
                print(f"  Usuario:    {username}")
                print(f"  Nombre:     {nombre}")
                print(f"  Email:      {email or '—'}")
                print(f"  Rol:        {rol}")
                print(f"  Contraseña: {'*' * len(password)}")

                if not confirmar():
                    continue

                password_hash = generate_password_hash(password, method="scrypt", salt_length=32)
                cursor.execute("""
                    INSERT INTO admin_usuarios (username, password_hash, nombre, email, rol)
                    VALUES (%s, %s, %s, %s, %s)
                """, (username, password_hash, nombre, email, rol))
                conn.commit()
                exito(f"Usuario '{username}' creado exitosamente")

            input("\n  Enter para continuar...")
            limpiar_pantalla()

        elif opcion == "2":
            limpiar_pantalla()
            mostrar_titulo()
            print(f"  {Color.BOLD}— Dar de baja usuario{Color.RESET}\n")

            username = pedir_input("  Username a dar de baja: ")
            if username is None:
                continue

            cursor.execute("SELECT id, username, nombre, email, rol, activo FROM admin_usuarios WHERE username = %s", (username,))
            usuario = cursor.fetchone()

            if not usuario:
                error(f"El usuario '{username}' no existe.")
            elif not usuario['activo']:
                advertencia(f"El usuario '{username}' ya está dado de baja.")
            else:
                mostrar_usuario(usuario)
                print(f"\n  {Color.RED}Se desactivará el acceso de este usuario.{Color.RESET}")
                if confirmar("  ¿Confirmar la baja? (S/N): "):
                    cursor.execute("UPDATE admin_usuarios SET activo = FALSE WHERE username = %s", (username,))
                    conn.commit()
                    exito(f"Usuario '{username}' dado de baja exitosamente")
                else:
                    info("Operación cancelada.")

            input("\n  Enter para continuar...")
            limpiar_pantalla()

        elif opcion == "3":
            limpiar_pantalla()
            mostrar_titulo()
            print(f"  {Color.BOLD}— Activar usuario{Color.RESET}\n")

            username = pedir_input("  Username a activar: ")
            if username is None:
                continue

            cursor.execute("SELECT id, username, nombre, email, rol, activo FROM admin_usuarios WHERE username = %s", (username,))
            usuario = cursor.fetchone()

            if not usuario:
                error(f"El usuario '{username}' no existe.")
            elif usuario['activo']:
                advertencia(f"El usuario '{username}' ya está activo.")
            else:
                mostrar_usuario(usuario)
                if confirmar("  ¿Confirmar la activación? (S/N): "):
                    cursor.execute("UPDATE admin_usuarios SET activo = TRUE WHERE username = %s", (username,))
                    conn.commit()
                    exito(f"Usuario '{username}' activado exitosamente")
                else:
                    info("Operación cancelada.")

            input("\n  Enter para continuar...")
            limpiar_pantalla()

        elif opcion == "4":
            limpiar_pantalla()
            mostrar_titulo()
            print(f"  {Color.BOLD}— Listar usuarios{Color.RESET}\n")

            filtro = pedir_input("  Buscar (nombre, email o username, Enter para todos): ", obligatorio=False)

            if filtro:
                like = f"%{filtro}%"
                cursor.execute("""
                    SELECT id, username, nombre, email, rol, activo, ultimo_acceso, created_at
                    FROM admin_usuarios
                    WHERE username LIKE %s OR nombre LIKE %s OR email LIKE %s
                    ORDER BY id
                """, (like, like, like))
            else:
                cursor.execute("""
                    SELECT id, username, nombre, email, rol, activo, ultimo_acceso, created_at
                    FROM admin_usuarios ORDER BY id
                """)
            usuarios = cursor.fetchall()

            if not usuarios:
                advertencia("No se encontraron usuarios.")
            else:
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
                print(f"\n  {Color.DIM}Total: {len(usuarios)} usuario(s) — {Color.GREEN}{activos} activo(s){Color.RESET}{Color.DIM}, {Color.RED}{inactivos} inactivo(s){Color.RESET}{Color.DIM}{Color.RESET}")

            input("\n  Enter para continuar...")
            limpiar_pantalla()

        else:
            error("Opción inválida. Intente de nuevo.")
            input("\n  Enter para continuar...")

    except KeyboardInterrupt:
        print()
        info("Hasta luego.")
        break

cursor.close()
conn.close()
