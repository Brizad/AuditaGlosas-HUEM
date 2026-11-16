"""Endpoints del catálogo de reglas: listar, activar y desactivar (HU-06)."""
from fastapi import APIRouter, HTTPException

from app.respuestas import Mensaje, ReglaSalida
from app.rutas.comunes import SesionBD, regla_a_salida
from app.servicios.catalogo_reglas import cambiar_estado_regla, listar_reglas

enrutador = APIRouter(prefix="/api/reglas", tags=["Catálogo de reglas"])

NO_EXISTE = {404: {"model": Mensaje, "description": "La regla no existe."}}


def _cambiar(sesion, codigo: str, activa: bool) -> ReglaSalida:
    regla = cambiar_estado_regla(sesion, codigo.upper(), activa)
    if regla is None:
        raise HTTPException(status_code=404, detail=f"No existe la regla {codigo}.")
    return regla_a_salida(regla)


@enrutador.get("", response_model=list[ReglaSalida], summary="Listar las reglas")
def listar(sesion: SesionBD):
    """Todas las reglas con su grupo de causal (Res. 2284 de 2023) y si están activas."""
    return [regla_a_salida(regla) for regla in listar_reglas(sesion)]


@enrutador.post("/{codigo}/activar", response_model=ReglaSalida, responses=NO_EXISTE, summary="Activar una regla")
def activar(codigo: str, sesion: SesionBD):
    """La regla vuelve a aplicarse en las próximas validaciones."""
    return _cambiar(sesion, codigo, activa=True)


@enrutador.post(
    "/{codigo}/desactivar", response_model=ReglaSalida, responses=NO_EXISTE, summary="Desactivar una regla",
)
def desactivar(codigo: str, sesion: SesionBD):
    """La regla deja de aplicarse. Para ver el efecto en un lote ya validado hay que validarlo de nuevo."""
    return _cambiar(sesion, codigo, activa=False)
