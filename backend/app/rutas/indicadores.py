"""Endpoints de indicadores (HU-05 y HU-07)."""
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constantes import TIPO_LINEA_BASE, TIPO_PILOTO
from app.modelos import Eps, Lote
from app.respuestas import (
    CifrasGlosaSalida,
    GlosasPorCausalSalida,
    GlosasPorPeriodoSalida,
    GlosasPorReglaSalida,
    GlosasPorTipoSalida,
    GrupoPruebaZ,
    IndicadorGlosasSalida,
    IndicadoresSalida,
    Mensaje,
    PruebaZEntrada,
    PruebaZSalida,
)
from app.rutas.comunes import FiltroReporte, SesionBD, causal_a_salida, lote_a_salida, resumen_a_salida
from app.servicios.catalogo_reglas import listar_reglas
from app.servicios.estadistica import prueba_z_dos_proporciones
from app.servicios.indicadores import (
    CifrasDeGlosa,
    cifras_de,
    glosas_por_causal,
    glosas_por_periodo,
    glosas_por_tipo,
)
from app.servicios.lotes import resumir_lotes
from app.servicios.reportes import Filtro, reporte_por_causal, resumen_general

enrutador = APIRouter(prefix="/api/indicadores", tags=["Indicadores"])

LOTES_RECIENTES = 5


@enrutador.get("", response_model=IndicadoresSalida, summary="Indicadores generales")
def indicadores_generales(sesion: SesionBD):
    """Cifras de la página de inicio: totales de todos los lotes, hallazgos por causal y últimos lotes."""
    reglas = listar_reglas(sesion)
    ultimos = list(sesion.scalars(select(Lote).order_by(Lote.id.desc()).limit(LOTES_RECIENTES)))
    resumenes = resumir_lotes(sesion, [lote.id for lote in ultimos])
    return IndicadoresSalida(
        total_lotes=sesion.scalar(select(func.count()).select_from(Lote)),
        eps_registradas=sesion.scalar(select(func.count()).select_from(Eps)),
        reglas_activas=sum(1 for regla in reglas if regla.activa),
        total_reglas=len(reglas),
        resumen=resumen_a_salida(resumen_general(sesion)),
        hallazgos_por_grupo=[causal_a_salida(fila) for fila in reporte_por_causal(sesion).grupos],
        ultimos_lotes=[lote_a_salida(lote, resumenes[lote.id]) for lote in ultimos],
    )


# ---------------------------------------------------------------------------
# Línea base y piloto (HU-07)
# ---------------------------------------------------------------------------
NOMBRES_DE_GRUPO = {TIPO_LINEA_BASE: "línea base", TIPO_PILOTO: "piloto"}


def _cifras_a_salida(cifras: CifrasDeGlosa) -> dict:
    """Campos comunes de las respuestas del indicador."""
    return CifrasGlosaSalida(
        validadas=cifras.validadas, glosadas=cifras.glosadas, porcentaje_glosadas=cifras.porcentaje_glosadas,
        valor_facturado=cifras.valor_facturado, valor_en_riesgo=cifras.valor_en_riesgo,
    ).model_dump()


@enrutador.get("/glosas", response_model=IndicadorGlosasSalida, summary="Porcentaje de facturas glosadas")
def indicador_de_glosas(sesion: SesionBD, filtro: FiltroReporte):
    """Porcentaje de facturas glosadas (con inconsistencias) en total, por periodo y por causal.

    `por_tipo` trae las cifras de los lotes marcados como línea base y piloto: son las que
    usa la prueba z cuando no se digitan cifras a mano.
    """
    return IndicadorGlosasSalida(
        total=_cifras_a_salida(cifras_de(resumen_general(sesion, filtro))),
        por_periodo=[
            GlosasPorPeriodoSalida(periodo=fila.periodo, **_cifras_a_salida(fila.cifras))
            for fila in glosas_por_periodo(sesion, filtro)
        ],
        por_causal=[
            GlosasPorCausalSalida(
                grupo=fila.grupo, nombre_grupo=fila.nombre_grupo, facturas_afectadas=fila.facturas_afectadas,
                porcentaje_facturas=fila.porcentaje_facturas,
                reglas=[GlosasPorReglaSalida(**asdict(regla)) for regla in fila.reglas],
            )
            for fila in glosas_por_causal(sesion, filtro)
        ],
        por_tipo=[
            GlosasPorTipoSalida(tipo=fila.tipo, lotes=fila.lotes, **_cifras_a_salida(fila.cifras))
            for fila in glosas_por_tipo(sesion)
        ],
    )


def _cifras_del_grupo(sesion: Session, digitadas: GrupoPruebaZ | None, tipo: str) -> tuple[int, int, str]:
    """Devuelve (glosadas, total, origen) de un grupo: lo digitado o, si no, lo que haya en los lotes de ese tipo."""
    nombre = NOMBRES_DE_GRUPO[tipo]
    if digitadas is not None:
        if digitadas.facturas_glosadas > digitadas.total_facturas:
            raise HTTPException(
                status_code=422,
                detail=f"En {nombre}, las facturas glosadas no pueden ser más que el total de facturas.",
            )
        return digitadas.facturas_glosadas, digitadas.total_facturas, "manual"

    cifras = cifras_de(resumen_general(sesion, Filtro(tipo=tipo)))
    if cifras.validadas == 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No hay facturas validadas en lotes de tipo «{nombre}». "
                "Cargue y valide un lote de ese tipo o digite las cifras."
            ),
        )
    return cifras.glosadas, cifras.validadas, "lotes"


@enrutador.post(
    "/prueba-z",
    response_model=PruebaZSalida,
    summary="Prueba z: línea base contra piloto",
    responses={409: {"model": Mensaje, "description": "Faltan lotes validados de línea base o de piloto."}},
)
def prueba_z(sesion: SesionBD, entrada: PruebaZEntrada):
    """Compara la proporción de facturas glosadas de la línea base contra la del piloto.

    Cada grupo puede digitarse (cifras agregadas) u omitirse para tomarlo de los lotes
    cargados con ese tipo. Devuelve z, valor p, la decisión y la interpretación en español.
    """
    glosadas_base, total_base, origen_base = _cifras_del_grupo(sesion, entrada.linea_base, TIPO_LINEA_BASE)
    glosadas_piloto, total_piloto, origen_piloto = _cifras_del_grupo(sesion, entrada.piloto, TIPO_PILOTO)
    resultado = prueba_z_dos_proporciones(
        glosadas_base, total_base, glosadas_piloto, total_piloto, alfa=entrada.alfa, hipotesis=entrada.hipotesis,
    )
    return PruebaZSalida(**asdict(resultado), origen_linea_base=origen_base, origen_piloto=origen_piloto)
