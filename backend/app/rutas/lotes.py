"""Endpoints de lotes: cargar, listar, validar, ver resultados y eliminar (HU-01, HU-05)."""
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.esquemas import LoteEntrada
from app.modelos import Factura, Lote
from app.respuestas import FacturaResumenSalida, LoteSalida, Mensaje, ResultadosLoteSalida
from app.rutas.comunes import PATRON_PERIODO, IdRegistro, SesionBD, buscar_lote, lote_a_salida
from app.servicios.lotes import ErrorDeCarga, eliminar_lote, guardar_lote, resumir_lote, resumir_lotes
from app.servicios.validacion import validar_lote

enrutador = APIRouter(prefix="/api/lotes", tags=["Lotes"])

NO_EXISTE = {404: {"model": Mensaje, "description": "El lote no existe."}}


@enrutador.post(
    "",
    status_code=201,
    response_model=LoteSalida,
    summary="Cargar un lote de facturas con su RIPS",
    responses={422: {"description": "El JSON no tiene la estructura esperada o el lote no se puede guardar."}},
)
def cargar_lote(entrada: LoteEntrada, sesion: SesionBD):
    """Recibe el lote en JSON, revisa su estructura y lo guarda **sin validar**.

    Se rechaza (422) si falta un campo obligatorio, si un dato tiene el tipo
    equivocado, si hay facturas repetidas o si la EPS no está registrada. La
    respuesta trae la lista `errores` con cada problema en español.

    El documento del paciente que venga en el RIPS se descarta: no se guarda.
    """
    try:
        lote = guardar_lote(sesion, entrada)
    except ErrorDeCarga as error:
        return JSONResponse(
            status_code=422,
            content={"detail": "El lote no se pudo cargar. Corrija el archivo y vuelva a intentarlo.",
                     "errores": error.errores},
        )
    return lote_a_salida(lote, resumir_lote(sesion, lote.id))


@enrutador.get("", response_model=list[LoteSalida], summary="Listar los lotes cargados")
def listar_lotes(
    sesion: SesionBD,
    tipo: Annotated[Literal["general", "linea_base", "piloto"] | None, Query()] = None,
    periodo: Annotated[str | None, Query(pattern=PATRON_PERIODO)] = None,
):
    """Lotes del más reciente al más antiguo, cada uno con su resumen."""
    consulta = select(Lote).order_by(Lote.id.desc())
    if tipo:
        consulta = consulta.where(Lote.tipo == tipo)
    if periodo:
        consulta = consulta.where(Lote.periodo == periodo)
    lotes = list(sesion.scalars(consulta))
    resumenes = resumir_lotes(sesion, [lote.id for lote in lotes])
    return [lote_a_salida(lote, resumenes[lote.id]) for lote in lotes]


@enrutador.get("/{lote_id}", response_model=LoteSalida, responses=NO_EXISTE, summary="Consultar un lote")
def ver_lote(lote_id: IdRegistro, sesion: SesionBD):
    lote = buscar_lote(sesion, lote_id)
    return lote_a_salida(lote, resumir_lote(sesion, lote.id))


@enrutador.delete("/{lote_id}", status_code=204, responses=NO_EXISTE, summary="Eliminar un lote")
def borrar_lote(lote_id: IdRegistro, sesion: SesionBD):
    """Elimina el lote con sus facturas y hallazgos. No se puede deshacer."""
    eliminar_lote(sesion, buscar_lote(sesion, lote_id))
    return Response(status_code=204)


@enrutador.post(
    "/{lote_id}/validar", response_model=LoteSalida, responses=NO_EXISTE,
    summary="Validar el lote antes de radicar",
)
def validar(lote_id: IdRegistro, sesion: SesionBD):
    """Aplica las reglas **activas** a cada factura y guarda los hallazgos.

    Se puede ejecutar varias veces: cada vez se recalcula todo con las reglas
    que estén activas en ese momento.
    """
    lote = validar_lote(sesion, buscar_lote(sesion, lote_id))
    return lote_a_salida(lote, resumir_lote(sesion, lote.id))


@enrutador.get(
    "/{lote_id}/resultados", response_model=ResultadosLoteSalida, responses=NO_EXISTE,
    summary="Resultados del lote factura por factura",
)
def resultados(
    lote_id: IdRegistro,
    sesion: SesionBD,
    estado: Annotated[Literal["apta", "con_inconsistencias", "sin_validar"] | None, Query()] = None,
):
    """Resumen del lote y estado de cada factura, con las reglas que incumple."""
    lote = buscar_lote(sesion, lote_id)
    consulta = (
        select(Factura)
        .where(Factura.lote_id == lote.id)
        .options(joinedload(Factura.eps), selectinload(Factura.hallazgos))
        .order_by(Factura.id)
    )
    if estado:
        consulta = consulta.where(Factura.estado == estado)
    facturas = [
        FacturaResumenSalida(
            id=factura.id, num_factura=factura.num_factura,
            eps_codigo=factura.eps.codigo, eps_nombre=factura.eps.nombre,
            fecha_expedicion=factura.fecha_expedicion, valor_total=factura.valor_total,
            estado=factura.estado, valor_en_riesgo=factura.valor_en_riesgo,
            total_hallazgos=len(factura.hallazgos),
            reglas=sorted({hallazgo.regla_codigo for hallazgo in factura.hallazgos}),
        )
        for factura in sesion.scalars(consulta)
    ]
    return ResultadosLoteSalida(lote=lote_a_salida(lote, resumir_lote(sesion, lote.id)), facturas=facturas)
