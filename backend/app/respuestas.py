"""Forma de los datos que DEVUELVE la API (esquemas Pydantic de salida).

FastAPI usa estas clases para dos cosas: garantizar que la respuesta siempre
tenga los mismos campos y mostrarlos en la documentación de `/docs`.
"""
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

# --- Tipos para los datos que el usuario digita en «Contratos y tarifas» -----
CodigoEps = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_-]{2,30}$")]
CodigoServicio = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9._-]{1,20}$")]
Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
ValorTarifa = Annotated[float, Field(ge=0, le=999_999_999_999, allow_inf_nan=False)]


# --- Sistema ------------------------------------------------------------------
class Mensaje(BaseModel):
    detail: str


# --- Reglas -------------------------------------------------------------------
class ReglaSalida(BaseModel):
    codigo: str
    nombre: str
    grupo: str
    nombre_grupo: str
    descripcion: str
    activa: bool


# --- Lotes y facturas ---------------------------------------------------------
class ResumenSalida(BaseModel):
    total_facturas: int
    aptas: int
    con_inconsistencias: int
    sin_validar: int
    valor_facturado: float
    valor_en_riesgo: float
    porcentaje_aptas: float
    porcentaje_con_inconsistencias: float


class LoteSalida(BaseModel):
    id: int
    nombre: str
    tipo: str
    periodo: str
    estado: str
    fecha_carga: datetime
    fecha_validacion: datetime | None
    resumen: ResumenSalida


class FacturaResumenSalida(BaseModel):
    id: int
    num_factura: str
    eps_codigo: str
    eps_nombre: str
    fecha_expedicion: date | None
    valor_total: float
    estado: str
    valor_en_riesgo: float
    total_hallazgos: int
    reglas: list[str] = Field(description="Códigos de las reglas que generaron hallazgos.")


class ResultadosLoteSalida(BaseModel):
    lote: LoteSalida
    facturas: list[FacturaResumenSalida]


class HallazgoSalida(BaseModel):
    regla: str
    grupo: str
    nombre_grupo: str
    titulo: str
    detalle: str
    valor_en_riesgo: float


class ItemSalida(BaseModel):
    codigo: str
    descripcion: str | None
    cantidad: float
    valor_unitario: float
    valor: float


class ServicioSalida(BaseModel):
    clase: str
    codigo: str
    descripcion: str | None
    cantidad: float
    valor_unitario: float
    valor_servicio: float
    num_autorizacion: str | None
    indice_usuario: int


class FacturaDetalleSalida(BaseModel):
    id: int
    lote_id: int
    lote_nombre: str
    num_factura: str
    eps_codigo: str
    eps_nombre: str
    fecha_expedicion: date | None
    valor_total: float
    rips_num_factura: str | None
    estado: str
    valor_en_riesgo: float
    items: list[ItemSalida]
    servicios: list[ServicioSalida]
    soportes: list[str]
    hallazgos: list[HallazgoSalida]


# --- Reportes -----------------------------------------------------------------
class FilaReglaSalida(BaseModel):
    codigo: str
    nombre: str
    hallazgos: int
    facturas_afectadas: int
    valor_hallazgos: float


class FilaCausalSalida(BaseModel):
    grupo: str
    nombre_grupo: str
    hallazgos: int
    facturas_afectadas: int
    valor_hallazgos: float
    reglas: list[FilaReglaSalida]


class ReportePorCausalSalida(BaseModel):
    total_hallazgos: int
    valor_hallazgos: float = Field(
        description="Suma del valor de cada hallazgo. Puede ser mayor al valor en riesgo de las facturas, "
        "porque un mismo servicio puede tener varios hallazgos.",
    )
    grupos: list[FilaCausalSalida]


class FilaEpsSalida(ResumenSalida):
    eps_codigo: str
    eps_nombre: str


class ReportePorEpsSalida(BaseModel):
    filas: list[FilaEpsSalida]


# --- EPS, tarifas y catálogo ----------------------------------------------------
class EpsEntrada(BaseModel):
    codigo: CodigoEps = Field(description="Código corto sin espacios, por ejemplo «EPS-ALFA».")
    nombre: Nombre


class EpsEdicion(BaseModel):
    nombre: Nombre


class EpsSalida(BaseModel):
    codigo: str
    nombre: str
    total_tarifas: int
    total_autorizaciones: int
    total_facturas: int


class TarifaEntrada(BaseModel):
    codigo_servicio: CodigoServicio
    valor: ValorTarifa


class TarifaEdicion(BaseModel):
    valor: ValorTarifa


class TarifaSalida(BaseModel):
    codigo_servicio: str
    descripcion: str | None
    valor: float
    requiere_autorizacion: bool


class AutorizacionEntrada(BaseModel):
    codigo_servicio: CodigoServicio


class AutorizacionSalida(BaseModel):
    codigo_servicio: str
    descripcion: str | None


class EpsDetalleSalida(EpsSalida):
    tarifas: list[TarifaSalida]
    autorizaciones: list[AutorizacionSalida]


class ServicioCatalogoEntrada(BaseModel):
    descripcion: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
    # Se acepta con mayúsculas («Imagen») y se guarda en minúsculas («imagen»).
    tipo: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[A-Za-zñÑ_]{3,30}$")]


class ServicioCatalogoSalida(BaseModel):
    codigo: str
    descripcion: str
    tipo: str


class CatalogoSalida(BaseModel):
    servicios: list[ServicioCatalogoSalida]
    soportes_requeridos: dict[str, list[str]] = Field(description="Tipo de servicio -> soportes obligatorios.")


# --- Indicadores ---------------------------------------------------------------
class IndicadoresSalida(BaseModel):
    total_lotes: int
    eps_registradas: int
    reglas_activas: int
    total_reglas: int
    resumen: ResumenSalida
    hallazgos_por_grupo: list[FilaCausalSalida]
    ultimos_lotes: list[LoteSalida]


# --- Línea base y piloto (HU-07) -------------------------------------------------
class CifrasGlosaSalida(BaseModel):
    validadas: int = Field(description="Facturas ya validadas (aptas + con inconsistencias).")
    glosadas: int = Field(description="Facturas con al menos una inconsistencia.")
    porcentaje_glosadas: float
    valor_facturado: float
    valor_en_riesgo: float


class GlosasPorPeriodoSalida(CifrasGlosaSalida):
    periodo: str = Field(description="Mes en formato AAAA-MM.")


class GlosasPorTipoSalida(CifrasGlosaSalida):
    tipo: str = Field(description="general, linea_base o piloto.")
    lotes: int


class GlosasPorReglaSalida(BaseModel):
    codigo: str
    nombre: str
    facturas_afectadas: int
    porcentaje_facturas: float


class GlosasPorCausalSalida(BaseModel):
    grupo: str
    nombre_grupo: str
    facturas_afectadas: int
    porcentaje_facturas: float = Field(description="Sobre las facturas validadas. No suman 100 entre causales.")
    reglas: list[GlosasPorReglaSalida]


class IndicadorGlosasSalida(BaseModel):
    total: CifrasGlosaSalida
    por_periodo: list[GlosasPorPeriodoSalida]
    por_causal: list[GlosasPorCausalSalida]
    por_tipo: list[GlosasPorTipoSalida] = Field(description="Siempre de todos los lotes (no aplica el filtro).")


class GrupoPruebaZ(BaseModel):
    """Cifras agregadas de un grupo (nunca datos de pacientes)."""

    total_facturas: Annotated[int, Field(gt=0, le=10_000_000)]
    facturas_glosadas: Annotated[int, Field(ge=0, le=10_000_000)]


class PruebaZEntrada(BaseModel):
    linea_base: GrupoPruebaZ | None = Field(
        default=None, description="Si no se envía, se toman los lotes de tipo «linea_base» ya validados.")
    piloto: GrupoPruebaZ | None = Field(
        default=None, description="Si no se envía, se toman los lotes de tipo «piloto» ya validados.")
    alfa: Annotated[float, Field(gt=0, lt=1, allow_inf_nan=False)] = 0.05
    hipotesis: Literal["reduce", "diferente"] = Field(
        default="reduce", description="reduce: el piloto baja la proporción (una cola). diferente: dos colas.")


class PruebaZSalida(BaseModel):
    total_linea_base: int
    glosadas_linea_base: int
    proporcion_linea_base: float
    origen_linea_base: str = Field(description="«lotes» si salió de los lotes cargados, «manual» si se digitó.")
    total_piloto: int
    glosadas_piloto: int
    proporcion_piloto: float
    origen_piloto: str
    diferencia: float = Field(description="Proporción de la línea base menos la del piloto.")
    proporcion_combinada: float
    error_estandar: float
    z: float
    valor_p: float
    alfa: float
    hipotesis: str
    valor_critico: float
    se_rechaza_h0: bool
    intervalo_inferior: float
    intervalo_superior: float
    nivel_confianza: float
    supuestos_cumplidos: bool
    interpretacion: str
    advertencias: list[str]
