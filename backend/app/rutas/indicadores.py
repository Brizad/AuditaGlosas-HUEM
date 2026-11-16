"""Endpoints de indicadores (HU-05 y HU-07)."""
from fastapi import APIRouter
from sqlalchemy import func, select

from app.modelos import Eps, Lote
from app.respuestas import IndicadoresSalida
from app.rutas.comunes import SesionBD, causal_a_salida, lote_a_salida, resumen_a_salida
from app.servicios.catalogo_reglas import listar_reglas
from app.servicios.lotes import resumir_lotes
from app.servicios.reportes import reporte_por_causal, resumen_general

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
