"""
alta_usuario.py — GUI (tkinter) para dar de alta usuarios del WMS.

Inserta en `taurus_admin.usuarios`, la tabla que usa el login del WMS (app.py),
asignando tenant y rol (roles activos de `taurus_admin.roles`). Para usuarios
del panel admin ver `scripts/admin_superusuario.py`.

Uso: python scripts/alta_usuario.py   (lee DB_ADMIN_* del .env de la raíz)
"""
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import StringVar, messagebox, ttk

# Raíz del proyecto en sys.path para poder importar `modules` aunque el script
# se ejecute como `python scripts/alta_usuario.py`.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# El .env de la raíz se carga antes que db_config (que solo mira el cwd).
load_dotenv(dotenv_path=ROOT / '.env')

from modules.db_config import _get_admin_connection


class CrearUsuarioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Crear Nuevo Usuario")
        self.root.geometry("500x650")
        self.root.resizable(False, False)

        # Configurar estilos
        self.setup_styles()

        # Variables para los campos
        self.usuario_var = StringVar()
        self.email_var = StringVar()
        self.nombre_var = StringVar()
        self.rol_var = StringVar()
        self.tenant_var = StringVar()
        self.clave_var = StringVar()
        self.clave2_var = StringVar()

        # Cargar configuración de BD
        self.cargar_config_bd()

        # Crear la interfaz
        self.crear_interfaz()

        # Estado inicial del botón (HABILITADO por defecto)
        self.crear_btn.config(state='normal')

    def setup_styles(self):
        """Configurar estilos de la interfaz"""
        style = ttk.Style()
        style.theme_use('clam')

        # Configurar colores
        self.bg_color = "#f0f0f0"
        self.primary_color = "#4CAF50"
        self.error_color = "#f44336"
        self.success_color = "#4CAF50"

        self.root.configure(bg=self.bg_color)

    def cargar_config_bd(self):
        """Cargar tenants y roles activos desde taurus_admin"""
        self.tenants = {}
        self.roles = []
        try:
            conn = _get_admin_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id, codigo, nombre FROM tenants WHERE activo = 1 ORDER BY nombre")
                self.tenants = {f"{t['nombre']} ({t['codigo']})": t['id'] for t in cursor.fetchall()}
                cursor.execute("SELECT nombre FROM roles WHERE activo = 1 ORDER BY nombre")
                self.roles = [r['nombre'] for r in cursor.fetchall()]
                cursor.close()
            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer tenants/roles de taurus_admin:\n{e!s}")

    def crear_interfaz(self):
        """Crear todos los elementos de la interfaz"""

        # Frame principal con padding
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Título
        titulo = ttk.Label(main_frame, text="🔐 CREAR NUEVO USUARIO",
                           font=('Helvetica', 16, 'bold'))
        titulo.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # Separador
        ttk.Separator(main_frame, orient='horizontal').grid(row=1, column=0, columnspan=2, sticky='ew', pady=(0, 20))

        # Fila 2: Nombre de usuario
        ttk.Label(main_frame, text="👤 Nombre de usuario:", font=('Helvetica', 10)).grid(row=2, column=0, sticky=tk.W,
                                                                                        pady=5)
        self.usuario_entry = ttk.Entry(main_frame, textvariable=self.usuario_var, width=30, font=('Helvetica', 10))
        self.usuario_entry.grid(row=2, column=1, sticky=tk.W, pady=5, padx=(10, 0))

        # Fila 3: Email
        ttk.Label(main_frame, text="📧 Email:", font=('Helvetica', 10)).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(main_frame, textvariable=self.email_var, width=30, font=('Helvetica', 10))
        self.email_entry.grid(row=3, column=1, sticky=tk.W, pady=5, padx=(10, 0))

        # Fila 4: Nombre completo
        ttk.Label(main_frame, text="📝 Nombre completo:", font=('Helvetica', 10)).grid(row=4, column=0, sticky=tk.W,
                                                                                      pady=5)
        self.nombre_entry = ttk.Entry(main_frame, textvariable=self.nombre_var, width=30, font=('Helvetica', 10))
        self.nombre_entry.grid(row=4, column=1, sticky=tk.W, pady=5, padx=(10, 0))

        # Fila 5: Contraseña
        ttk.Label(main_frame, text="🔑 Contraseña:", font=('Helvetica', 10)).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.clave_entry = ttk.Entry(main_frame, textvariable=self.clave_var, width=30, font=('Helvetica', 10),
                                     show="•")
        self.clave_entry.grid(row=5, column=1, sticky=tk.W, pady=5, padx=(10, 0))

        # Fila 6: Confirmar contraseña
        ttk.Label(main_frame, text="🔑 Confirmar contraseña:", font=('Helvetica', 10)).grid(row=6, column=0, sticky=tk.W,
                                                                                           pady=5)
        self.clave2_entry = ttk.Entry(main_frame, textvariable=self.clave2_var, width=30, font=('Helvetica', 10),
                                      show="•")
        self.clave2_entry.grid(row=6, column=1, sticky=tk.W, pady=5, padx=(10, 0))

        # Fila 7: Rol
        ttk.Label(main_frame, text="👑 Rol:", font=('Helvetica', 10)).grid(row=7, column=0, sticky=tk.W, pady=5)

        # Frame para radio buttons de rol
        rol_frame = ttk.Frame(main_frame)
        rol_frame.grid(row=7, column=1, sticky=tk.W, pady=5, padx=(10, 0))

        # Roles de taurus_admin.roles (los mismos que asigna el panel admin)
        self.rol_combo = ttk.Combobox(rol_frame, textvariable=self.rol_var, values=self.roles,
                                      state='readonly', width=27)
        self.rol_combo.grid(row=0, column=0)

        # Fila 8: Tenant
        ttk.Label(main_frame, text="🏢 Tenant:", font=('Helvetica', 10)).grid(row=8, column=0, sticky=tk.W, pady=5)
        self.tenant_combo = ttk.Combobox(main_frame, textvariable=self.tenant_var, values=list(self.tenants),
                                         state='readonly', width=27)
        self.tenant_combo.grid(row=8, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        self.seleccionar_defaults()

        # Separador
        ttk.Separator(main_frame, orient='horizontal').grid(row=9, column=0, columnspan=2, sticky='ew', pady=20)

        # Fila 10: Botones
        botones_frame = ttk.Frame(main_frame)
        botones_frame.grid(row=10, column=0, columnspan=2, pady=10)

        self.crear_btn = ttk.Button(botones_frame, text="✅ Crear Usuario",
                                    command=self.crear_usuario, width=20)
        self.crear_btn.grid(row=0, column=0, padx=5)

        ttk.Button(botones_frame, text="🧹 Limpiar",
                   command=self.limpiar_campos, width=15).grid(row=0, column=1, padx=5)

        ttk.Button(botones_frame, text="❌ Cancelar",
                   command=self.root.quit, width=15).grid(row=0, column=2, padx=5)

        # Fila 9: Estado
        self.estado_label = ttk.Label(main_frame, text="", font=('Helvetica', 9))
        self.estado_label.grid(row=11, column=0, columnspan=2, pady=(20, 0))

        # Configurar grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)

        # Bind tecla Enter para crear usuario
        self.root.bind('<Return>', lambda e: self.crear_usuario())

        # SOLUCIÓN: No usar trace para deshabilitar automáticamente
        # En su lugar, usamos trace SOLO para mostrar advertencias, no para deshabilitar
        self.usuario_var.trace('w', lambda *args: self.mostrar_advertencias())
        self.email_var.trace('w', lambda *args: self.mostrar_advertencias())
        self.clave_var.trace('w', lambda *args: self.mostrar_advertencias())
        self.clave2_var.trace('w', lambda *args: self.mostrar_advertencias())

    def seleccionar_defaults(self):
        """Preselecciona OPERADOR (o el primer rol) y el tenant si hay uno solo"""
        self.rol_var.set('OPERADOR' if 'OPERADOR' in self.roles else (self.roles[0] if self.roles else ''))
        self.tenant_var.set(next(iter(self.tenants)) if len(self.tenants) == 1 else '')

    def validar_email(self, email):
        """Validar formato de email"""
        if not email:
            return False
        patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(patron, email) is not None

    def mostrar_advertencias(self):
        """Mostrar advertencias pero NO deshabilitar el botón"""
        usuario = self.usuario_var.get().strip()
        email = self.email_var.get().strip()
        clave = self.clave_var.get()
        clave2 = self.clave2_var.get()

        mensajes_advertencia = []

        if not usuario:
            mensajes_advertencia.append("• Usuario requerido")

        if not email:
            mensajes_advertencia.append("• Email requerido")
        elif not self.validar_email(email):
            mensajes_advertencia.append("• Email inválido")

        if not clave:
            mensajes_advertencia.append("• Contraseña requerida")
        elif len(clave) < 6:
            mensajes_advertencia.append("• Mínimo 6 caracteres")

        if clave and clave2 and clave != clave2:
            mensajes_advertencia.append("• Contraseñas no coinciden")

        # Actualizar label de estado con advertencias (sin deshabilitar el botón)
        if mensajes_advertencia:
            self.estado_label.config(
                text="⚠️ Completar:\n" + "\n".join(mensajes_advertencia[:3]),
                foreground="orange"
            )
        else:
            self.estado_label.config(text="✅ Todos los campos válidos", foreground="green")

    def limpiar_campos(self):
        """Limpiar todos los campos del formulario"""
        self.usuario_var.set("")
        self.email_var.set("")
        self.nombre_var.set("")
        self.seleccionar_defaults()
        self.clave_var.set("")
        self.clave2_var.set("")
        self.usuario_entry.focus()
        self.estado_label.config(text="")
        # Mantener el botón habilitado
        self.crear_btn.config(state='normal')

    def crear_usuario_bd(self, usuario, clave, mail, nombre, rol, tenant_id):
        """Crear usuario en taurus_admin.usuarios (tabla del login del WMS)"""
        try:
            conn = _get_admin_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM usuarios WHERE username = %s", (usuario,))
                if cursor.fetchone():
                    return False, f"El nombre de usuario '{usuario}' ya existe"

                cursor.execute("""
                    INSERT INTO usuarios (username, password_hash, nombre, email, rol, tenant_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (usuario, generate_password_hash(clave), nombre, mail, rol, tenant_id))
                conn.commit()
                cursor.close()
            finally:
                conn.close()

            return True, "Usuario creado exitosamente"

        except Exception as e:
            return False, f"Error al crear usuario: {e!s}"

    def crear_usuario(self):
        """Procesar la creación del usuario"""

        # Obtener y limpiar datos
        usuario = self.usuario_var.get().strip()
        mail = self.email_var.get().strip()
        nombre = self.nombre_var.get().strip()
        if not nombre:
            nombre = usuario
        clave = self.clave_var.get()
        clave2 = self.clave2_var.get()
        rol = self.rol_var.get()
        tenant_nombre = self.tenant_var.get()
        tenant_id = self.tenants.get(tenant_nombre)

        # Validaciones CON MENSAJES DE ERROR
        if not usuario:
            messagebox.showerror("Error", "El nombre de usuario es obligatorio")
            self.usuario_entry.focus()
            return

        if not mail:
            messagebox.showerror("Error", "El email es obligatorio")
            self.email_entry.focus()
            return

        if not self.validar_email(mail):
            messagebox.showerror("Error", "El email no tiene un formato válido")
            self.email_entry.focus()
            return

        if not clave:
            messagebox.showerror("Error", "La contraseña es obligatoria")
            self.clave_entry.focus()
            return

        if len(clave) < 6:
            messagebox.showerror("Error", "La contraseña debe tener al menos 6 caracteres")
            self.clave_entry.focus()
            return

        if clave != clave2:
            messagebox.showerror("Error", "Las contraseñas no coinciden")
            self.clave2_entry.focus()
            return

        if not rol:
            messagebox.showerror("Error", "Debe seleccionar un rol")
            return

        if not tenant_id:
            messagebox.showerror("Error", "Debe seleccionar un tenant")
            return

        # Confirmar creación
        confirmar = messagebox.askyesno(
            "Confirmar",
            f"¿Estás seguro de crear el usuario?\n\n"
            f"Usuario: {usuario}\n"
            f"Email: {mail}\n"
            f"Nombre: {nombre}\n"
            f"Rol: {rol}\n"
            f"Tenant: {tenant_nombre}"
        )

        if confirmar:
            # Deshabilitar botón durante la operación
            self.crear_btn.config(state='disabled')
            self.estado_label.config(text="⏳ Creando usuario...", foreground="blue")
            self.root.update()

            # Crear usuario
            success, mensaje = self.crear_usuario_bd(usuario, clave, mail, nombre, rol, tenant_id)

            if success:
                self.estado_label.config(text="✅ " + mensaje, foreground="green")
                messagebox.showinfo("Éxito", mensaje)

                # Preguntar si desea crear otro usuario
                if messagebox.askyesno("Continuar", "¿Deseas crear otro usuario?"):
                    self.limpiar_campos()
                    # Asegurar que el botón esté habilitado
                    self.crear_btn.config(state='normal')
                else:
                    self.root.quit()
            else:
                self.estado_label.config(text="❌ " + mensaje, foreground="red")
                messagebox.showerror("Error", mensaje)
                # Rehabilitar botón en caso de error
                self.crear_btn.config(state='normal')


def main():
    """Función principal para ejecutar la aplicación"""
    root = tk.Tk()
    CrearUsuarioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()