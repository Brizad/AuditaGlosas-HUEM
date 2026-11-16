"""Registro de reglas: la lista de todas las reglas que el motor puede aplicar.

Cada regla se anota sola con el decorador `@registrar`. Así, agregar una regla
nueva no obliga a tocar el motor ni la API.
"""
from app.reglas.base import GRUPOS, ReglaBase

# código de la regla -> objeto de la regla
_REGISTRO: dict[str, ReglaBase] = {}


def registrar(clase: type[ReglaBase]) -> type[ReglaBase]:
    """Decorador que agrega una regla al registro.

    Revisa que la regla esté bien definida para detectar errores apenas arranca
    el servidor y no cuando ya se está validando un lote.
    """
    regla = clase()
    if not (regla.codigo and regla.nombre and regla.descripcion):
        raise ValueError(f"La regla {clase.__name__} debe tener código, nombre y descripción.")
    if regla.grupo not in GRUPOS:
        raise ValueError(f"La regla {regla.codigo} tiene un grupo desconocido: «{regla.grupo}».")
    if regla.codigo in _REGISTRO:
        raise ValueError(f"Ya existe una regla con el código {regla.codigo}.")
    _REGISTRO[regla.codigo] = regla
    return clase


def reglas_registradas() -> list[ReglaBase]:
    """Devuelve todas las reglas, ordenadas por grupo (FA, TA, SO, AU) y por código."""
    orden_grupos = list(GRUPOS)
    return sorted(_REGISTRO.values(), key=lambda regla: (orden_grupos.index(regla.grupo), regla.codigo))


def obtener_regla(codigo: str) -> ReglaBase | None:
    """Busca una regla por su código."""
    return _REGISTRO.get(codigo)
