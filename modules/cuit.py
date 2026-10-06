"""Formato del CUIT: una sola regla para el panel admin y los maestros del WMS."""
import re

CUIT_FORMATO = '99-99999999-9'
CUIT_INVALIDO = f'CUIT inválido: debe tener el formato {CUIT_FORMATO}.'


def normalizar_cuit(valor):
    """CUIT en formato 99-99999999-9.

    Acepta el valor ya formateado o sus 11 dígitos sin guiones. Devuelve '' si
    está vacío (el CUIT es opcional) y None si no tiene un formato válido.
    Controla el formato, no el dígito verificador.
    """
    valor = str(valor or '').strip()
    if not valor:
        return ''
    if re.fullmatch(r'\d{11}', valor):
        return f'{valor[:2]}-{valor[2:10]}-{valor[10]}'
    return valor if re.fullmatch(r'\d{2}-\d{8}-\d', valor) else None


def cuit_para_guardar(valor):
    """CUIT listo para guardar: formateado, o None si está vacío. Lanza ValueError si es inválido."""
    cuit = normalizar_cuit(valor)
    if cuit is None:
        raise ValueError(CUIT_INVALIDO)
    return cuit or None


def cuit_para_mostrar(valor):
    """CUIT formateado para mostrar; si lo guardado no es un CUIT válido, se devuelve tal cual."""
    return normalizar_cuit(valor) or valor
