"""Tablas de la base de datos (una clase por tabla).

Se organizan en tres grupos:
1. Contratos y catálogos: EPS, tarifas, autorizaciones, catálogo de servicios, soportes por tipo.
2. Reglas: el catálogo de reglas y si cada una está activa.
3. Lotes: lote, facturas, ítems facturados, servicios del RIPS, soportes y hallazgos.

Importante (Ley 1581 de 2012): no existe tabla de pacientes y no se guarda
ningún dato que los identifique.
"""
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.base_datos import Base

# Tipo de columna para dinero y cantidades: 14 dígitos, 2 decimales.
# `asdecimal=False` hace que Python reciba números normales (float).
DINERO = Numeric(14, 2, asdecimal=False)

# Valores permitidos (se usan también en los esquemas y en las reglas).
TIPOS_LOTE = ("general", "linea_base", "piloto")
ESTADO_LOTE_CARGADO = "cargado"
ESTADO_LOTE_VALIDADO = "validado"
ESTADO_SIN_VALIDAR = "sin_validar"
ESTADO_APTA = "apta"
ESTADO_CON_INCONSISTENCIAS = "con_inconsistencias"
CLASE_CONSULTA = "consulta"
CLASE_PROCEDIMIENTO = "procedimiento"
CLASE_MEDICAMENTO = "medicamento"


# ---------------------------------------------------------------------------
# 1. Contratos y catálogos
# ---------------------------------------------------------------------------
class Eps(Base):
    """Entidad a la que el hospital le factura (EPS u otro pagador)."""

    __tablename__ = "eps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))

    tarifas: Mapped[list["Tarifa"]] = relationship(
        back_populates="eps", cascade="all, delete-orphan", order_by="Tarifa.codigo_servicio"
    )
    autorizaciones: Mapped[list["AutorizacionRequerida"]] = relationship(
        back_populates="eps", cascade="all, delete-orphan", order_by="AutorizacionRequerida.codigo_servicio"
    )
    facturas: Mapped[list["Factura"]] = relationship(back_populates="eps")


class Tarifa(Base):
    """Valor pactado con una EPS para un servicio (código CUPS o de medicamento)."""

    __tablename__ = "tarifas"
    __table_args__ = (UniqueConstraint("eps_id", "codigo_servicio", name="uq_tarifa_eps_servicio"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    eps_id: Mapped[int] = mapped_column(ForeignKey("eps.id", ondelete="CASCADE"), index=True)
    codigo_servicio: Mapped[str] = mapped_column(String(20))
    valor: Mapped[float] = mapped_column(DINERO)

    eps: Mapped[Eps] = relationship(back_populates="tarifas")


class AutorizacionRequerida(Base):
    """Servicio para el que una EPS exige número de autorización."""

    __tablename__ = "autorizaciones_requeridas"
    __table_args__ = (UniqueConstraint("eps_id", "codigo_servicio", name="uq_autorizacion_eps_servicio"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    eps_id: Mapped[int] = mapped_column(ForeignKey("eps.id", ondelete="CASCADE"), index=True)
    codigo_servicio: Mapped[str] = mapped_column(String(20))

    eps: Mapped[Eps] = relationship(back_populates="autorizaciones")


class ServicioCatalogo(Base):
    """Descripción y tipo de cada servicio (consulta, laboratorio, imagen, medicamento)."""

    __tablename__ = "servicios_catalogo"

    codigo: Mapped[str] = mapped_column(String(20), primary_key=True)
    descripcion: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(30))


class SoporteRequerido(Base):
    """Soporte que debe acompañar la factura según el tipo de servicio."""

    __tablename__ = "soportes_requeridos"
    __table_args__ = (UniqueConstraint("tipo_servicio", "nombre_soporte", name="uq_soporte_tipo_nombre"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo_servicio: Mapped[str] = mapped_column(String(30), index=True)
    nombre_soporte: Mapped[str] = mapped_column(String(120))


# ---------------------------------------------------------------------------
# 2. Catálogo de reglas
# ---------------------------------------------------------------------------
class Regla(Base):
    """Una regla de validación y su interruptor (activa o no).

    El código Python de la regla vive en `app/reglas/`; esta tabla solo guarda
    sus datos descriptivos y si el usuario la tiene encendida.
    """

    __tablename__ = "reglas"

    codigo: Mapped[str] = mapped_column(String(10), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    grupo: Mapped[str] = mapped_column(String(2))
    descripcion: Mapped[str] = mapped_column(Text)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------------------
# 3. Lotes, facturas y hallazgos
# ---------------------------------------------------------------------------
class Lote(Base):
    """Grupo de facturas que se cargan y validan juntas."""

    __tablename__ = "lotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(20), default="general")  # general, linea_base o piloto
    periodo: Mapped[str] = mapped_column(String(7), index=True)  # AAAA-MM
    estado: Mapped[str] = mapped_column(String(20), default=ESTADO_LOTE_CARGADO)
    fecha_carga: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    fecha_validacion: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    facturas: Mapped[list["Factura"]] = relationship(
        back_populates="lote", cascade="all, delete-orphan", order_by="Factura.id"
    )


class Factura(Base):
    """Factura de venta con el resultado de su última validación."""

    __tablename__ = "facturas"
    __table_args__ = (UniqueConstraint("lote_id", "num_factura", name="uq_factura_lote_numero"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lotes.id", ondelete="CASCADE"), index=True)
    eps_id: Mapped[int] = mapped_column(ForeignKey("eps.id"), index=True)
    num_factura: Mapped[str] = mapped_column(String(40))
    fecha_expedicion: Mapped[date | None] = mapped_column(Date, nullable=True)
    valor_total: Mapped[float] = mapped_column(DINERO)
    # Número de factura que viene escrito dentro del RIPS (la regla FA-01 lo compara).
    rips_num_factura: Mapped[str | None] = mapped_column(String(40), nullable=True)
    estado: Mapped[str] = mapped_column(String(20), default=ESTADO_SIN_VALIDAR)
    valor_en_riesgo: Mapped[float] = mapped_column(DINERO, default=0)

    lote: Mapped[Lote] = relationship(back_populates="facturas")
    eps: Mapped[Eps] = relationship(back_populates="facturas")
    items: Mapped[list["ItemFactura"]] = relationship(
        back_populates="factura", cascade="all, delete-orphan", order_by="ItemFactura.id"
    )
    servicios: Mapped[list["ServicioRips"]] = relationship(
        back_populates="factura", cascade="all, delete-orphan", order_by="ServicioRips.id"
    )
    soportes: Mapped[list["SoporteFactura"]] = relationship(
        back_populates="factura", cascade="all, delete-orphan", order_by="SoporteFactura.id"
    )
    hallazgos: Mapped[list["Hallazgo"]] = relationship(
        back_populates="factura", cascade="all, delete-orphan", order_by="Hallazgo.id"
    )


class ItemFactura(Base):
    """Renglón cobrado en la factura."""

    __tablename__ = "items_factura"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    factura_id: Mapped[int] = mapped_column(ForeignKey("facturas.id", ondelete="CASCADE"), index=True)
    codigo: Mapped[str] = mapped_column(String(20))
    cantidad: Mapped[float] = mapped_column(DINERO)
    valor_unitario: Mapped[float] = mapped_column(DINERO)

    factura: Mapped[Factura] = relationship(back_populates="items")


class ServicioRips(Base):
    """Servicio reportado en el RIPS: consulta, procedimiento o medicamento.

    Los tres comparten columnas; `clase` indica cuál es. No se guarda el
    documento del paciente, solo su posición dentro del RIPS (`indice_usuario`).
    """

    __tablename__ = "servicios_rips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    factura_id: Mapped[int] = mapped_column(ForeignKey("facturas.id", ondelete="CASCADE"), index=True)
    clase: Mapped[str] = mapped_column(String(20))
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cantidad: Mapped[float] = mapped_column(DINERO, default=1)
    valor_unitario: Mapped[float] = mapped_column(DINERO)
    valor_servicio: Mapped[float] = mapped_column(DINERO)
    num_autorizacion: Mapped[str | None] = mapped_column(String(40), nullable=True)
    indice_usuario: Mapped[int] = mapped_column(Integer, default=1)

    factura: Mapped[Factura] = relationship(back_populates="servicios")


class SoporteFactura(Base):
    """Soporte que el facturador declara adjunto a la factura."""

    __tablename__ = "soportes_factura"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    factura_id: Mapped[int] = mapped_column(ForeignKey("facturas.id", ondelete="CASCADE"), index=True)
    nombre: Mapped[str] = mapped_column(String(120))

    factura: Mapped[Factura] = relationship(back_populates="soportes")


class Hallazgo(Base):
    """Inconsistencia que una regla encontró en una factura."""

    __tablename__ = "hallazgos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    factura_id: Mapped[int] = mapped_column(ForeignKey("facturas.id", ondelete="CASCADE"), index=True)
    regla_codigo: Mapped[str] = mapped_column(ForeignKey("reglas.codigo"), index=True)
    grupo: Mapped[str] = mapped_column(String(2), index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    detalle: Mapped[str] = mapped_column(Text)
    valor_en_riesgo: Mapped[float] = mapped_column(DINERO, default=0)

    factura: Mapped[Factura] = relationship(back_populates="hallazgos")
