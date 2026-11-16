"""Indicador de la línea base y el piloto: porcentaje de facturas glosadas (HU-07).

¿Qué es aquí una «factura glosada»? El sistema trabaja ANTES de radicar, así
que todavía no existe la respuesta de la EPS. Por eso se mide como la factura
en la que el motor encontró al menos una inconsistencia: es la que la EPS
glosaría si se radicara tal como está.

    % glosadas = facturas con inconsistencias / facturas validadas × 100

Las facturas sin validar no entran en la cuenta.
"""
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constantes import TIPOS_LOTE
from app.modelos import Factura, Lote
from app.servicios.lotes import ResumenFacturas, columnas_de_resumen, fila_a_resumen
from app.servicios.reportes import Filtro, reporte_por_causal, resumen_general


def porcentaje(parte: int, total: int) -> float:
    """Porcentaje con un decimal; 0 si no hay total (evita dividir por cero)."""
    return round(100 * parte / total, 1) if total else 0.0


@dataclass(frozen=True)
class CifrasDeGlosa:
    """Facturas validadas y cuántas de ellas quedaron glosadas."""

    validadas: int = 0
    glosadas: int = 0
    valor_facturado: float = 0.0
    valor_en_riesgo: float = 0.0

    @property
    def porcentaje_glosadas(self) -> float:
        return porcentaje(self.glosadas, self.validadas)


def cifras_de(resumen: ResumenFacturas) -> CifrasDeGlosa:
    """Pasa del resumen general de facturas a las cifras del indicador."""
    return CifrasDeGlosa(
        validadas=resumen.aptas + resumen.con_inconsistencias,
        glosadas=resumen.con_inconsistencias,
        valor_facturado=resumen.valor_facturado,
        valor_en_riesgo=resumen.valor_en_riesgo,
    )


@dataclass(frozen=True)
class GlosasPorPeriodo:
    periodo: str            # AAAA-MM
    cifras: CifrasDeGlosa


@dataclass(frozen=True)
class GlosasPorTipo:
    tipo: str               # general, linea_base o piloto
    lotes: int              # cuántos lotes de ese tipo hay
    cifras: CifrasDeGlosa


@dataclass
class GlosasPorRegla:
    codigo: str
    nombre: str
    facturas_afectadas: int
    porcentaje_facturas: float


@dataclass
class GlosasPorCausal:
    grupo: str
    nombre_grupo: str
    facturas_afectadas: int
    porcentaje_facturas: float      # sobre las facturas validadas
    reglas: list[GlosasPorRegla] = field(default_factory=list)


def glosas_por_periodo(sesion: Session, filtro: Filtro = Filtro()) -> list[GlosasPorPeriodo]:
    """Porcentaje de facturas glosadas de cada periodo (mes), del más antiguo al más reciente."""
    consulta = (
        select(Lote.periodo, *columnas_de_resumen())
        .join(Lote, Factura.lote_id == Lote.id)
        .where(Factura.lote_id.in_(filtro.lotes()))
        .group_by(Lote.periodo)
        .order_by(Lote.periodo)
    )
    return [
        GlosasPorPeriodo(periodo=fila[0], cifras=cifras_de(fila_a_resumen(fila[1:])))
        for fila in sesion.execute(consulta)
    ]


def glosas_por_tipo(sesion: Session) -> list[GlosasPorTipo]:
    """Cifras de cada tipo de lote. Las de `linea_base` y `piloto` alimentan la prueba z."""
    lotes_por_tipo: dict[str, int] = {tipo: 0 for tipo in TIPOS_LOTE}
    for tipo in sesion.scalars(select(Lote.tipo)):
        lotes_por_tipo[tipo] = lotes_por_tipo.get(tipo, 0) + 1
    return [
        GlosasPorTipo(tipo=tipo, lotes=cantidad, cifras=cifras_de(resumen_general(sesion, Filtro(tipo=tipo))))
        for tipo, cantidad in lotes_por_tipo.items()
    ]


def glosas_por_causal(sesion: Session, filtro: Filtro = Filtro()) -> list[GlosasPorCausal]:
    """Qué porcentaje de las facturas validadas incumple cada grupo de causal y cada regla.

    Los porcentajes NO suman 100: una misma factura puede incumplir varias reglas.
    """
    validadas = cifras_de(resumen_general(sesion, filtro)).validadas
    return [
        GlosasPorCausal(
            grupo=grupo.grupo, nombre_grupo=grupo.nombre_grupo,
            facturas_afectadas=grupo.facturas_afectadas,
            porcentaje_facturas=porcentaje(grupo.facturas_afectadas, validadas),
            reglas=[
                GlosasPorRegla(
                    codigo=regla.codigo, nombre=regla.nombre, facturas_afectadas=regla.facturas_afectadas,
                    porcentaje_facturas=porcentaje(regla.facturas_afectadas, validadas),
                )
                for regla in grupo.reglas
            ],
        )
        for grupo in reporte_por_causal(sesion, filtro).grupos
    ]
