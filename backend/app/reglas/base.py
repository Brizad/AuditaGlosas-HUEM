"""Piezas comunes del motor de reglas.

- `ContextoFactura`: todo lo que una regla necesita saber de una factura.
- `HallazgoDetectado`: una inconsistencia encontrada por una regla.
- `ReglaBase`: clase de la que heredan todas las reglas.

Nada de este archivo consulta la base de datos: las reglas trabajan con datos
ya preparados. Por eso se pueden probar armando un contexto a mano.
"""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# Grupos de causales del Manual Único de Devoluciones, Glosas y Respuestas (Res. 2284 de 2023).
GRUPOS = {
    "FA": "Facturación y codificación",
    "TA": "Tarifas",
    "SO": "Soportes",
    "AU": "Autorizaciones",
}

# Diferencia máxima en pesos que se acepta al comparar valores (redondeos).
TOLERANCIA = 0.5

# Un código de consulta o procedimiento válido tiene 6 caracteres: dígitos o mayúsculas.
_PATRON_CODIGO = re.compile(r"[0-9A-Z]{6}")


def codigo_valido(codigo: str) -> bool:
    """Indica si el código tiene el formato de 6 caracteres válidos."""
    return _PATRON_CODIGO.fullmatch(codigo or "") is not None


def pesos(valor: float) -> str:
    """Escribe un valor como dinero colombiano: 38000 -> «$38.000»."""
    return "$" + f"{round(valor):,}".replace(",", ".")


def texto_comparable(texto: str) -> str:
    """Quita espacios sobrantes y mayúsculas para comparar nombres de soportes."""
    return " ".join((texto or "").split()).casefold()


@dataclass(frozen=True)
class ItemFacturado:
    """Renglón cobrado en la factura."""

    codigo: str
    cantidad: float
    valor_unitario: float

    @property
    def valor(self) -> float:
        return self.cantidad * self.valor_unitario


@dataclass(frozen=True)
class ServicioPrestado:
    """Servicio reportado en el RIPS (consulta, procedimiento o medicamento)."""

    clase: str
    codigo: str
    valor: float                      # valor total del servicio (vrServicio)
    cantidad: float = 1
    valor_unitario: float | None = None
    num_autorizacion: str | None = None

    def __post_init__(self):
        # Si no se indica el valor unitario, es el valor del servicio (consultas y procedimientos).
        if self.valor_unitario is None:
            object.__setattr__(self, "valor_unitario", self.valor)


@dataclass
class ContextoFactura:
    """Factura + contrato de su EPS + catálogo: lo que reciben las reglas."""

    # Datos de la factura
    num_factura: str
    valor_total: float
    rips_num_factura: str | None = None
    items: list[ItemFacturado] = field(default_factory=list)
    servicios: list[ServicioPrestado] = field(default_factory=list)
    soportes: list[str] = field(default_factory=list)
    # Contrato con la EPS
    nombre_eps: str = ""
    tarifas: dict[str, float] = field(default_factory=dict)             # código -> valor pactado
    codigos_con_autorizacion: set[str] = field(default_factory=set)     # códigos que la EPS exige autorizar
    # Catálogo de servicios
    descripciones: dict[str, str] = field(default_factory=dict)         # código -> descripción
    tipos_servicio: dict[str, str] = field(default_factory=dict)        # código -> tipo (laboratorio, imagen...)
    soportes_requeridos: dict[str, list[str]] = field(default_factory=dict)  # tipo -> soportes obligatorios

    def describir(self, codigo: str) -> str:
        """Devuelve «código (descripción)» o solo el código si no está en el catálogo."""
        descripcion = self.descripciones.get(codigo)
        return f"{codigo} ({descripcion})" if descripcion else codigo


@dataclass(frozen=True)
class HallazgoDetectado:
    """Inconsistencia encontrada por una regla en una factura."""

    regla: str            # código de la regla, por ejemplo «SO-01»
    grupo: str            # FA, TA, SO o AU
    titulo: str
    detalle: str
    valor_en_riesgo: float


class ReglaBase(ABC):
    """Clase base de todas las reglas.

    Para crear una regla nueva: heredar de esta clase, llenar los cuatro datos,
    escribir `evaluar` y ponerle el decorador `@registrar` (ver `registro.py`).
    """

    codigo: str = ""          # identificador interno, por ejemplo «TA-01»
    nombre: str = ""          # título corto que se muestra en el hallazgo
    grupo: str = ""           # grupo de causal de la Res. 2284: FA, TA, SO o AU
    descripcion: str = ""     # qué verifica la regla, en una frase

    @abstractmethod
    def evaluar(self, contexto: ContextoFactura) -> list[HallazgoDetectado]:
        """Revisa la factura y devuelve los hallazgos (lista vacía si cumple)."""

    def hallazgo(self, detalle: str, valor_en_riesgo: float, titulo: str | None = None) -> HallazgoDetectado:
        """Atajo para crear un hallazgo de esta regla sin repetir código y grupo."""
        return HallazgoDetectado(
            regla=self.codigo,
            grupo=self.grupo,
            titulo=titulo or self.nombre,
            detalle=detalle,
            valor_en_riesgo=max(0.0, float(valor_en_riesgo)),
        )
