from modules.db_config import get_db_connection
import os
import tkinter as tk
from tkinter import ttk, messagebox, StringVar
from pathlib import Path
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
import re


class CrearUsuarioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Crear Nuevo Usuario")
        self.root.geometry("500x600")
        self.root.resizable(False, False)

        # Configurar estilos
        self.setup_styles()

        # Variables para los campos
        self.usuario_var = StringVar()
        self.email_var = StringVar()
        self.nombre_var = StringVar()
        self.rol_var = StringVar(value="USER")
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
        """Cargar configuración de base de datos"""
        env_path = Path('.') / '.env'
        load_dotenv(dotenv_path=env_path)

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

        roles = [("Admin", "admin"), ("Supervisor", "supervisor"), ("Operador", "operador")]
        for i, (text, value) in enumerate(roles):
            ttk.Radiobutton(rol_frame, text=text, value=value,
                            variable=self.rol_var).grid(row=0, column=i, padx=5)

        # Separador
        ttk.Separator(main_frame, orient='horizontal').grid(row=8, column=0, columnspan=2, sticky='ew', pady=20)

        # Fila 8: Botones
        botones_frame = ttk.Frame(main_frame)
        botones_frame.grid(row=9, column=0, columnspan=2, pady=10)

        self.crear_btn = ttk.Button(botones_frame, text="✅ Crear Usuario",
                                    command=self.crear_usuario, width=20)
        self.crear_btn.grid(row=0, column=0, padx=5)

        ttk.Button(botones_frame, text="🧹 Limpiar",
                   command=self.limpiar_campos, width=15).grid(row=0, column=1, padx=5)

        ttk.Button(botones_frame, text="❌ Cancelar",
                   command=self.root.quit, width=15).grid(row=0, column=2, padx=5)

        # Fila 9: Estado
        self.estado_label = ttk.Label(main_frame, text="", font=('Helvetica', 9))
        self.estado_label.grid(row=10, column=0, columnspan=2, pady=(20, 0))

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
        self.rol_var.set("USER")
        self.clave_var.set("")
        self.clave2_var.set("")
        self.usuario_entry.focus()
        self.estado_label.config(text="")
        # Mantener el botón habilitado
        self.crear_btn.config(state='normal')

    def crear_usuario_bd(self, usuario, clave, mail, nombre, rol):
        """Crear usuario en la base de datos"""
        try:
            from modules.sql_dialect import insert_ignore_sql, is_duplicate_key_error
            conn = get_db_connection()
            cursor = conn.cursor()

            password_hash = generate_password_hash(clave)

            cols = ['username', 'email', 'password_hash', 'nombre', 'rol']
            sql = insert_ignore_sql('usuarios', cols)
            cursor.execute(sql, (usuario, mail, password_hash, nombre, rol))

            conn.commit()
            cursor.close()
            conn.close()

            return True, "Usuario creado exitosamente"

        except Exception as e:
            if is_duplicate_key_error(e):
                return False, f"El nombre de usuario '{usuario}' o email '{mail}' ya existe"
            return False, f"Error al crear usuario: {str(e)}"

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

        # Confirmar creación
        confirmar = messagebox.askyesno(
            "Confirmar",
            f"¿Estás seguro de crear el usuario?\n\n"
            f"Usuario: {usuario}\n"
            f"Email: {mail}\n"
            f"Nombre: {nombre}\n"
            f"Rol: {rol}"
        )

        if confirmar:
            # Deshabilitar botón durante la operación
            self.crear_btn.config(state='disabled')
            self.estado_label.config(text="⏳ Creando usuario...", foreground="blue")
            self.root.update()

            # Crear usuario
            success, mensaje = self.crear_usuario_bd(usuario, clave, mail, nombre, rol)

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
    app = CrearUsuarioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()