"""Política de contraseñas compartida (modules/passwords.py)."""

import pytest

from modules.passwords import PASSWORD_MIN_LEN, validar_password


@pytest.mark.parametrize('password', ['', None, 'a' * (PASSWORD_MIN_LEN - 1), ' Clave1234', 'Clave1234 '])
def test_passwords_invalidas(password):
    assert validar_password(password)


@pytest.mark.parametrize('password', ['a' * PASSWORD_MIN_LEN, 'Admin@2024!', 'con espacio en medio'])
def test_passwords_validas(password):
    assert validar_password(password) is None
