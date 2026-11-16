"""Forma de los datos que entran por la API (esquemas Pydantic).

Estos esquemas revisan la ESTRUCTURA del lote: que estén los campos
obligatorios y que cada uno tenga el tipo correcto. Si algo falla, el lote se
rechaza con un mensaje claro.

No revisan el CONTENIDO (por ejemplo, que el código tenga 6 caracteres o que
el valor coincida con la tarifa): eso es trabajo de las reglas.

Los nombres de los campos van como en el RIPS (Res. 2275 de 2023), por eso
están en camelCase: `numFactura`, `codConsulta`, `vrServicio`, etc.
"""
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints


def _numero_a_texto(valor):
    """Si un código llega como número (890201) lo convierte a texto ("890201")."""
    if isinstance(valor, int) and not isinstance(valor, bool):
        return str(valor)
    return valor


# Tipos reutilizables -------------------------------------------------------
Codigo = Annotated[
    str,
    BeforeValidator(_numero_a_texto),
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20),
]
NumeroFactura = Annotated[
    str,
    BeforeValidator(_numero_a_texto),
    StringConstraints(strip_whitespace=True, min_length=1, max_length=40),
]
Valor = Annotated[float, Field(ge=0, le=999_999_999_999, allow_inf_nan=False)]
Cantidad = Annotated[float, Field(gt=0, le=1_000_000, allow_inf_nan=False)]
TextoCorto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class EsquemaEntrada(BaseModel):
    """Base de los esquemas de entrada.

    `extra="ignore"` descarta los campos que el sistema no usa. Gracias a esto
    el documento del paciente (`numDocumentoIdentificacion`) nunca pasa de aquí
    y por lo tanto nunca llega a la base de datos (Ley 1581 de 2012).
    """

    model_config = ConfigDict(extra="ignore")


# RIPS ----------------------------------------------------------------------
class ConsultaRips(EsquemaEntrada):
    codConsulta: Codigo
    vrServicio: Valor
    numAutorizacion: Annotated[str | None, BeforeValidator(_numero_a_texto)] = None


class ProcedimientoRips(EsquemaEntrada):
    codProcedimiento: Codigo
    vrServicio: Valor
    numAutorizacion: Annotated[str | None, BeforeValidator(_numero_a_texto)] = None


class MedicamentoRips(EsquemaEntrada):
    codTecnologiaSalud: Codigo
    nomTecnologiaSalud: str | None = None
    cantidadMedicamento: Cantidad
    vrUnitMedicamento: Valor
    vrServicio: Valor
    numAutorizacion: Annotated[str | None, BeforeValidator(_numero_a_texto)] = None


class ServiciosUsuario(EsquemaEntrada):
    consultas: list[ConsultaRips] = Field(default_factory=list)
    procedimientos: list[ProcedimientoRips] = Field(default_factory=list)
    medicamentos: list[MedicamentoRips] = Field(default_factory=list)


class UsuarioRips(EsquemaEntrada):
    """Usuario del RIPS: solo se leen sus servicios, no su identificación."""

    servicios: ServiciosUsuario = Field(default_factory=ServiciosUsuario)


class Rips(EsquemaEntrada):
    # Puede venir vacío o distinto al de la factura: lo reporta la regla FA-01.
    numFactura: Annotated[str | None, BeforeValidator(_numero_a_texto)] = None
    usuarios: list[UsuarioRips] = Field(default_factory=list)


# Factura y lote -------------------------------------------------------------
class ItemFacturaEntrada(EsquemaEntrada):
    codigo: Codigo
    cantidad: Cantidad
    valorUnitario: Valor


class FacturaEntrada(EsquemaEntrada):
    numFactura: NumeroFactura
    eps: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
    fechaExpedicion: date | None = None
    valorTotal: Valor
    items: list[ItemFacturaEntrada]
    soportes: list[TextoCorto] = Field(default_factory=list)
    rips: Rips


class LoteEntrada(EsquemaEntrada):
    """Lo que se envía para cargar un lote."""

    nombre: TextoCorto = Field(description="Nombre para reconocer el lote, por ejemplo «Radicación junio EPS Alfa».")
    tipo: Literal["general", "linea_base", "piloto"] = Field(
        default="general",
        description="«linea_base» y «piloto» se usan para comparar el antes y el después (HU-07).",
    )
    periodo: Annotated[str | None, StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = Field(
        default=None,
        description="Periodo en formato AAAA-MM. Si no se envía, se toma de las fechas de las facturas.",
    )
    facturas: list[FacturaEntrada] = Field(min_length=1, max_length=5000)
