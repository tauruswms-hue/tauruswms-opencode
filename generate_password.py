import os
import sys
import pymysql
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
from pathlib import Path

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

ADMIN_DB_CONFIG = {
    'host': os.getenv('DB_ADMIN_HOST', os.getenv('DB_HOST')),
    'user': os.getenv('DB_ADMIN_USER', os.getenv('DB_USER')),
    'password': os.getenv('DB_ADMIN_PASSWORD', os.getenv('DB_PASSWORD')),
    'database': os.getenv('DB_ADMIN_NAME', 'taurus_admin'),
    'charset': os.getenv('DB_CHARSET', 'utf8mb4'),
    'port': int(os.getenv('DB_ADMIN_PORT', os.getenv('DB_PORT', 3306)))
}


def confirmar(prompt="Confirma la operación (S/N): "):
    resp = input(prompt).strip().lower()
    return resp == 's'


conn = pymysql.connect(**ADMIN_DB_CONFIG)
cursor = conn.cursor()

while True:
    try:
        print("\nSeleccione una opción:")
        print("  1 - Crear / Actualizar usuario")
        print("  2 - Dar de baja un usuario")
        print("  3 - Activar usuario")
        print("  4 - Salir")
        opcion = input("Opción: ").strip()

        if opcion == "4":
            break
        elif opcion == "2":
            try:
                username = input("Ingresa el nombre de usuario a dar de baja (Ctrl+C para cancelar): ").strip()
            except KeyboardInterrupt:
                print()
                continue

            cursor.execute("SELECT id, nombre, email, rol, activo FROM admin_usuarios WHERE username = %s", (username,))
            usuario = cursor.fetchone()

            if not usuario:
                print(f"\nEl usuario '{username}' no existe.")
            else:
                id_usuario, nombre, email, rol, activo = usuario
                estado = "activo" if activo else "inactivo"
                print(f"\nUsuario encontrado: {nombre} | {email} | {rol} | {estado}")
                if not activo:
                    print(f"El usuario '{username}' ya está dado de baja.")
                else:
                    print(f"\nResumen de la operación:")
                    print(f"  Usuario:   {username}")
                    print(f"  Nombre:    {nombre}")
                    print(f"  Acción:    Dar de baja")
                    try:
                        if not confirmar("¿Confirmar la baja del usuario? (S/N): "):
                            continue
                    except KeyboardInterrupt:
                        print()
                        continue
                    cursor.execute("UPDATE admin_usuarios SET activo = FALSE WHERE username = %s", (username,))
                    conn.commit()
                    print(f"Usuario '{username}' dado de baja exitosamente")
        elif opcion == "3":
            try:
                username = input("Ingresa el nombre de usuario a activar (Ctrl+C para cancelar): ").strip()
            except KeyboardInterrupt:
                print()
                continue

            cursor.execute("SELECT id, nombre, email, rol, activo FROM admin_usuarios WHERE username = %s", (username,))
            usuario = cursor.fetchone()

            if not usuario:
                print(f"\nEl usuario '{username}' no existe.")
            else:
                id_usuario, nombre, email, rol, activo = usuario
                if activo:
                    print(f"\nEl usuario '{username}' ya está activo.")
                else:
                    print(f"\nUsuario encontrado: {nombre} | {email} | {rol}")
                    try:
                        if not confirmar(f"¿Confirmar la activación del usuario '{username}'? (S/N): "):
                            continue
                    except KeyboardInterrupt:
                        print()
                        continue
                    cursor.execute("UPDATE admin_usuarios SET activo = TRUE WHERE username = %s", (username,))
                    conn.commit()
                    print(f"Usuario '{username}' activado exitosamente")
        elif opcion == "1":
            try:
                username = input("Ingresa el nombre de usuario (Ctrl+C para cancelar): ").strip()
            except KeyboardInterrupt:
                print()
                continue

            cursor.execute("SELECT id, nombre, email, rol, activo FROM admin_usuarios WHERE username = %s", (username,))
            usuario = cursor.fetchone()

            if usuario:
                id_usuario, nombre_actual, email_actual, rol_actual, activo = usuario
                estado = "activo" if activo else "inactivo"
                print(f"\nUsuario encontrado: {nombre_actual} | {email_actual} | {rol_actual} | {estado}")

                if not activo:
                    print(f"\nError: El usuario '{username}' está inactivo. Use la opción 3 (Activar usuario) para reactivarlo.")
                    continue

                try:
                    password = input("Ingresa la nueva contraseña (Ctrl+C para cancelar): ")
                except KeyboardInterrupt:
                    print()
                    continue
                password_hash = generate_password_hash(password, method="scrypt", salt_length=32)

                try:
                    nombre = input(f"Nombre completo [{nombre_actual}]: ").strip() or nombre_actual
                    email = input(f"Email [{email_actual}]: ").strip() or email_actual
                    rol = input(f"Rol (SUPERADMIN/ADMIN) [{rol_actual}]: ").strip().upper() or rol_actual
                except KeyboardInterrupt:
                    print()
                    continue

                print(f"\nResumen de la operación:")
                print(f"  Usuario:   {username}")
                print(f"  Nombre:    {nombre}")
                print(f"  Email:     {email}")
                print(f"  Rol:       {rol}")
                print(f"  Contraseña: {'*' * len(password)}")
                try:
                    if not confirmar():
                        continue
                except KeyboardInterrupt:
                    print()
                    continue

                cursor.execute("""
                    UPDATE admin_usuarios SET password_hash = %s, nombre = %s, email = %s, rol = %s WHERE username = %s
                """, (password_hash, nombre, email, rol, username))
                conn.commit()
                print(f"Usuario '{username}' actualizado exitosamente")
            else:
                print(f"\nEl usuario '{username}' no existe. Se creará uno nuevo.")
                try:
                    password = input("Ingresa la nueva contraseña (Ctrl+C para cancelar): ")
                except KeyboardInterrupt:
                    print()
                    continue
                password_hash = generate_password_hash(password, method="scrypt", salt_length=32)

                try:
                    nombre = input("Nombre completo: ").strip()
                    email = input("Email: ").strip()
                    rol = input("Rol (SUPERADMIN/ADMIN) [ADMIN]: ").strip().upper() or "ADMIN"
                except KeyboardInterrupt:
                    print()
                    continue

                print(f"\nResumen de la operación:")
                print(f"  Usuario:   {username}")
                print(f"  Nombre:    {nombre}")
                print(f"  Email:     {email}")
                print(f"  Rol:       {rol}")
                print(f"  Contraseña: {'*' * len(password)}")
                try:
                    if not confirmar():
                        continue
                except KeyboardInterrupt:
                    print()
                    continue

                cursor.execute("""
                    INSERT INTO admin_usuarios (username, password_hash, nombre, email, rol)
                    VALUES (%s, %s, %s, %s, %s)
                """, (username, password_hash, nombre, email, rol.upper()))
                conn.commit()
                print(f"Usuario '{username}' creado exitosamente")
        else:
            print("Opción inválida. Intente de nuevo.")
    except KeyboardInterrupt:
        print()
        break

cursor.close()
conn.close()