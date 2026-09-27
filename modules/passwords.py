"""Política de contraseñas compartida por el panel admin y los scripts de usuarios."""

PASSWORD_MIN_LEN = 8


def validar_password(password):
    """Devuelve None si la contraseña es válida, o el mensaje de error a mostrar."""
    if not password:
        return "La contraseña no puede estar vacía."
    if len(password) < PASSWORD_MIN_LEN:
        return f"La contraseña debe tener al menos {PASSWORD_MIN_LEN} caracteres."
    if password.strip() != password:
        return "La contraseña no puede empezar ni terminar con espacios."
    return None
