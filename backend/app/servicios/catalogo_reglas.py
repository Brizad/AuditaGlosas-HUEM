"""Catálogo de reglas configurable (HU-06).

El código de cada regla vive en `app/reglas/`. La tabla `reglas` guarda sus
datos descriptivos y el interruptor `activa`, que es lo que el usuario cambia
desde la pantalla «Catálogo de reglas».
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import Regla
from app.reglas import obtener_regla, reglas_registradas


def sincronizar_reglas(sesion: Session) -> int:
    """Pone la tabla `reglas` al día con las reglas que existen en el código.

    - Regla nueva en el código: se crea en la tabla, activa.
    - Regla que ya estaba: se actualizan nombre, grupo y descripción, pero se
      respeta si el usuario la tenía activa o inactiva.

    Devuelve cuántas reglas nuevas se crearon. Se ejecuta al arrancar el servidor.
    """
    nuevas = 0
    for regla in reglas_registradas():
        fila = sesion.get(Regla, regla.codigo)
        if fila is None:
            sesion.add(Regla(
                codigo=regla.codigo, nombre=regla.nombre, grupo=regla.grupo,
                descripcion=regla.descripcion, activa=True,
            ))
            nuevas += 1
        else:
            fila.nombre, fila.grupo, fila.descripcion = regla.nombre, regla.grupo, regla.descripcion
    sesion.commit()
    return nuevas


def listar_reglas(sesion: Session) -> list[Regla]:
    """Devuelve las reglas en el orden del catálogo: FA, TA, SO, AU."""
    filas = {fila.codigo: fila for fila in sesion.scalars(select(Regla))}
    return [filas[regla.codigo] for regla in reglas_registradas() if regla.codigo in filas]


def cambiar_estado_regla(sesion: Session, codigo: str, activa: bool) -> Regla | None:
    """Activa o desactiva una regla. Devuelve None si el código no existe."""
    fila = sesion.get(Regla, codigo)
    if fila is None or obtener_regla(codigo) is None:
        return None
    fila.activa = activa
    sesion.commit()
    return fila


def codigos_activos(sesion: Session) -> set[str]:
    """Códigos de las reglas que el usuario tiene encendidas."""
    return set(sesion.scalars(select(Regla.codigo).where(Regla.activa.is_(True))))
