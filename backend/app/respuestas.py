"""Forma de los datos que DEVUELVE la API (esquemas Pydantic de salida).

FastAPI usa estas clases para dos cosas: garantizar que la respuesta siempre
tenga los mismos campos y mostrarlos en la documentación de `/docs`.
"""
from datetime import date, datetime
from typing import Annotated

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
