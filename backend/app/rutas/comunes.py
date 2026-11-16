"""Piezas que comparten varios archivos de rutas."""
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.base_datos import obtener_sesion
from app.modelos import Lote, Regla
from app.reglas import GRUPOS
from app.respuestas import FilaCausalSalida, FilaReglaSalida, LoteSalida, ReglaSalida, ResumenSalida
from app.servicios.lotes import ResumenFacturas
from app.servicios.reportes import FilaCausal, Filtro

# Con esto cada endpoint recibe su sesión de base de datos escribiendo `sesion: SesionBD`.
SesionBD = Annotated[Session, Depends(obtener_sesion)]

PATRON_PERIODO = r"^\d{4}-(0[1-9]|1[0-2])$"


def filtro_de_reporte(
    lote_id: Annotated[int | None, Query(ge=1, description="Solo este lote.")] = None,
    periodo: Annotated[str | None, Query(pattern=PATRON_PERIODO, description="Solo este periodo (AAAA-MM).")] = None,
    tipo: Annotated[
        Literal["general", "linea_base", "piloto"] | None, Query(description="Solo lotes de este tipo.")
    ] = None,
) -> Filtro:
    """Filtros opcionales que aceptan los reportes."""
    return Filtro(lote_id=lote_id, periodo=periodo, tipo=tipo)


FiltroReporte = Annotated[Filtro, Depends(filtro_de_reporte)]


def buscar_lote(sesion: Session, lote_id: int) -> Lote:
    """Devuelve el lote o responde 404 si no existe."""
    lote = sesion.get(Lote, lote_id)
    if lote is None:
        raise HTTPException(status_code=404, detail=f"No existe el lote {lote_id}.")
    return lote


# --- Conversión de datos internos a respuestas de la API ---------------------
def resumen_a_salida(resumen: ResumenFacturas) -> ResumenSalida:
    return ResumenSalida(
        total_facturas=resumen.total_facturas,
        aptas=resumen.aptas,
        con_inconsistencias=resumen.con_inconsistencias,
        sin_validar=resumen.sin_validar,
        valor_facturado=resumen.valor_facturado,
        valor_en_riesgo=resumen.valor_en_riesgo,
        porcentaje_aptas=resumen.porcentaje_aptas,
        porcentaje_con_inconsistencias=resumen.porcentaje_con_inconsistencias,
    )


def lote_a_salida(lote: Lote, resumen: ResumenFacturas) -> LoteSalida:
    return LoteSalida(
        id=lote.id, nombre=lote.nombre, tipo=lote.tipo, periodo=lote.periodo, estado=lote.estado,
        fecha_carga=lote.fecha_carga, fecha_validacion=lote.fecha_validacion,
        resumen=resumen_a_salida(resumen),
    )


def regla_a_salida(regla: Regla) -> ReglaSalida:
    return ReglaSalida(
        codigo=regla.codigo, nombre=regla.nombre, grupo=regla.grupo,
        nombre_grupo=GRUPOS.get(regla.grupo, regla.grupo),
        descripcion=regla.descripcion, activa=regla.activa,
    )


def causal_a_salida(fila: FilaCausal) -> FilaCausalSalida:
    return FilaCausalSalida(
        grupo=fila.grupo, nombre_grupo=fila.nombre_grupo, hallazgos=fila.hallazgos,
        facturas_afectadas=fila.facturas_afectadas, valor_hallazgos=fila.valor_hallazgos,
        reglas=[
            FilaReglaSalida(
                codigo=regla.codigo, nombre=regla.nombre, hallazgos=regla.hallazgos,
                facturas_afectadas=regla.facturas_afectadas, valor_hallazgos=regla.valor_hallazgos,
            )
            for regla in fila.reglas
        ],
    )
