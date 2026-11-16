"""Endpoints de reportes por causal, por EPS y exportación a CSV (HU-05)."""
from fastapi import APIRouter, Response

from app.respuestas import FilaEpsSalida, ReportePorCausalSalida, ReportePorEpsSalida
from app.rutas.comunes import FiltroReporte, SesionBD, causal_a_salida, resumen_a_salida
from app.servicios.reportes import exportar_csv, reporte_por_causal, reporte_por_eps

enrutador = APIRouter(prefix="/api/reportes", tags=["Reportes"])


@enrutador.get("/por-causal", response_model=ReportePorCausalSalida, summary="Hallazgos por grupo de causal")
def por_causal(sesion: SesionBD, filtro: FiltroReporte):
    """Hallazgos, facturas afectadas y valor por cada grupo de causal (FA, TA, SO, AU) y por regla."""
    reporte = reporte_por_causal(sesion, filtro)
    return ReportePorCausalSalida(
        total_hallazgos=reporte.total_hallazgos,
        valor_hallazgos=reporte.valor_hallazgos,
        grupos=[causal_a_salida(fila) for fila in reporte.grupos],
    )


@enrutador.get("/por-eps", response_model=ReportePorEpsSalida, summary="Facturas e inconsistencias por EPS")
def por_eps(sesion: SesionBD, filtro: FiltroReporte):
    """Cuántas facturas de cada EPS están aptas o con inconsistencias y cuánto valor está en riesgo."""
    return ReportePorEpsSalida(filas=[
        FilaEpsSalida(
            eps_codigo=fila.eps_codigo, eps_nombre=fila.eps_nombre,
            **resumen_a_salida(fila.resumen).model_dump(),
        )
        for fila in reporte_por_eps(sesion, filtro)
    ])


@enrutador.get(
    "/exportar.csv",
    summary="Descargar el reporte de hallazgos en CSV",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "Archivo CSV separado por punto y coma."}},
)
def exportar(sesion: SesionBD, filtro: FiltroReporte):
    """Una fila por hallazgo (las facturas aptas salen con una fila sin hallazgo). Se abre directo en Excel."""
    nombre = f"reporte_validacion_lote_{filtro.lote_id}.csv" if filtro.lote_id else "reporte_validacion.csv"
    # El BOM (﻿) hace que Excel reconozca las tildes.
    return Response(
        content="﻿" + exportar_csv(sesion, filtro),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
