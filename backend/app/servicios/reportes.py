"""Reportes de inconsistencias por causal y por EPS, y exportación a CSV (HU-05)."""
import csv
import io
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.constantes import ESTADO_APTA, ESTADO_CON_INCONSISTENCIAS
from app.modelos import Eps, Factura, Hallazgo, Lote
from app.reglas import GRUPOS, reglas_registradas
from app.servicios.lotes import ResumenFacturas, columnas_de_resumen, fila_a_resumen


@dataclass(frozen=True)
class Filtro:
    """Qué lotes entran en un reporte. Sin filtros entran todos."""

    lote_id: int | None = None
    periodo: str | None = None
    tipo: str | None = None

    def lotes(self):
        """Subconsulta con los id de los lotes que cumplen el filtro."""
        consulta = select(Lote.id)
        if self.lote_id is not None:
            consulta = consulta.where(Lote.id == self.lote_id)
        if self.periodo:
            consulta = consulta.where(Lote.periodo == self.periodo)
        if self.tipo:
            consulta = consulta.where(Lote.tipo == self.tipo)
        return consulta


# ---------------------------------------------------------------------------
# Reporte por causal
# ---------------------------------------------------------------------------
@dataclass
class FilaRegla:
    codigo: str
    nombre: str
    hallazgos: int = 0
    facturas_afectadas: int = 0
    valor_hallazgos: float = 0.0


@dataclass
class FilaCausal:
    grupo: str
    nombre_grupo: str
    hallazgos: int = 0
    facturas_afectadas: int = 0
    valor_hallazgos: float = 0.0
    reglas: list[FilaRegla] = field(default_factory=list)


@dataclass
class ReportePorCausal:
    total_hallazgos: int
    valor_hallazgos: float
    grupos: list[FilaCausal]


def reporte_por_causal(sesion: Session, filtro: Filtro = Filtro()) -> ReportePorCausal:
    """Cuenta hallazgos, facturas afectadas y valor por grupo de causal y por regla.

    Siempre devuelve los cuatro grupos y todas las reglas, aunque estén en cero,
    para que las tablas y gráficas tengan siempre la misma forma.
    """
    grupos = {codigo: FilaCausal(grupo=codigo, nombre_grupo=nombre) for codigo, nombre in GRUPOS.items()}
    reglas = {regla.codigo: FilaRegla(codigo=regla.codigo, nombre=regla.nombre) for regla in reglas_registradas()}
    for regla in reglas_registradas():
        grupos[regla.grupo].reglas.append(reglas[regla.codigo])

    facturas_del_filtro = select(Factura.id).where(Factura.lote_id.in_(filtro.lotes()))
    columnas = [
        func.count(Hallazgo.id),
        func.count(func.distinct(Hallazgo.factura_id)),
        func.coalesce(func.sum(Hallazgo.valor_en_riesgo), 0),
    ]

    # Totales por regla.
    por_regla = (
        select(Hallazgo.regla_codigo, *columnas)
        .where(Hallazgo.factura_id.in_(facturas_del_filtro))
        .group_by(Hallazgo.regla_codigo)
    )
    for codigo, cantidad, facturas, valor in sesion.execute(por_regla):
        if codigo in reglas:
            fila = reglas[codigo]
            fila.hallazgos, fila.facturas_afectadas, fila.valor_hallazgos = int(cantidad), int(facturas), float(valor)

    # Totales por grupo (aparte, porque una factura puede tener dos reglas del mismo grupo).
    por_grupo = (
        select(Hallazgo.grupo, *columnas)
        .where(Hallazgo.factura_id.in_(facturas_del_filtro))
        .group_by(Hallazgo.grupo)
    )
    for codigo, cantidad, facturas, valor in sesion.execute(por_grupo):
        if codigo in grupos:
            fila = grupos[codigo]
            fila.hallazgos, fila.facturas_afectadas, fila.valor_hallazgos = int(cantidad), int(facturas), float(valor)

    return ReportePorCausal(
        total_hallazgos=sum(fila.hallazgos for fila in grupos.values()),
        valor_hallazgos=sum(fila.valor_hallazgos for fila in grupos.values()),
        grupos=list(grupos.values()),
    )


# ---------------------------------------------------------------------------
# Reporte por EPS
# ---------------------------------------------------------------------------
@dataclass
class FilaEps:
    eps_codigo: str
    eps_nombre: str
    resumen: ResumenFacturas


def reporte_por_eps(sesion: Session, filtro: Filtro = Filtro()) -> list[FilaEps]:
    """Facturas, estados y valores de cada EPS. Incluye las EPS sin facturas (en cero)."""
    consulta = (
        select(Factura.eps_id, *columnas_de_resumen())
        .where(Factura.lote_id.in_(filtro.lotes()))
        .group_by(Factura.eps_id)
    )
    resumen_por_eps = {fila[0]: fila_a_resumen(fila[1:]) for fila in sesion.execute(consulta)}
    return [
        FilaEps(eps_codigo=eps.codigo, eps_nombre=eps.nombre, resumen=resumen_por_eps.get(eps.id, ResumenFacturas()))
        for eps in sesion.scalars(select(Eps).order_by(Eps.nombre))
    ]


def resumen_general(sesion: Session, filtro: Filtro = Filtro()) -> ResumenFacturas:
    """Totales de todas las facturas que cumplen el filtro."""
    consulta = select(*columnas_de_resumen()).where(Factura.lote_id.in_(filtro.lotes()))
    return fila_a_resumen(sesion.execute(consulta).one())


# ---------------------------------------------------------------------------
# Exportación a CSV
# ---------------------------------------------------------------------------
ENCABEZADOS_CSV = [
    "lote", "periodo", "factura", "eps", "valor_factura", "estado",
    "regla", "grupo", "hallazgo", "detalle", "valor_en_riesgo",
]
ESTADOS_LEGIBLES = {ESTADO_APTA: "Apta", ESTADO_CON_INCONSISTENCIAS: "Corregir"}


def celda_segura(valor) -> str:
    """Evita que Excel interprete un texto como fórmula.

    Si un dato del lote empieza por =, +, - o @, Excel lo ejecutaría como
    fórmula al abrir el CSV. Anteponer un apóstrofo lo deja como texto.
    """
    texto = "" if valor is None else str(valor)
    if texto and texto[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + texto
    return texto


def exportar_csv(sesion: Session, filtro: Filtro = Filtro()) -> str:
    """Arma el reporte de hallazgos en CSV: una fila por hallazgo.

    Las facturas aptas salen con una sola fila sin hallazgo. Se separa con
    punto y coma porque así lo abre Excel en español sin pasos adicionales.
    """
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    escritor.writerow(ENCABEZADOS_CSV)

    consulta = (
        select(Factura)
        .where(Factura.lote_id.in_(filtro.lotes()))
        .options(joinedload(Factura.lote), joinedload(Factura.eps), selectinload(Factura.hallazgos))
        .order_by(Factura.lote_id, Factura.id)
    )
    for factura in sesion.scalars(consulta):
        inicio = [
            celda_segura(factura.lote.nombre), factura.lote.periodo, celda_segura(factura.num_factura),
            celda_segura(factura.eps.codigo), round(factura.valor_total),
            ESTADOS_LEGIBLES.get(factura.estado, "Sin validar"),
        ]
        if not factura.hallazgos:
            escritor.writerow([*inicio, "", "", "", "", 0])
        for hallazgo in factura.hallazgos:
            escritor.writerow([
                *inicio, hallazgo.regla_codigo, GRUPOS.get(hallazgo.grupo, hallazgo.grupo),
                celda_segura(hallazgo.titulo), celda_segura(hallazgo.detalle), round(hallazgo.valor_en_riesgo),
            ])
    return salida.getvalue()
