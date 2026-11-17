"""Puente entre la base de datos y el motor de reglas.

El motor no conoce la base de datos: aquí se leen las tablas, se arma el
`ContextoFactura` que las reglas entienden y se guarda el resultado.
"""
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.constantes import ESTADO_APTA, ESTADO_CON_INCONSISTENCIAS, ESTADO_LOTE_VALIDADO, VALOR_MAXIMO
from app.modelos import Eps, Factura, Hallazgo, Lote, ServicioCatalogo, SoporteRequerido
from app.reglas import ContextoFactura, ItemFacturado, ServicioPrestado, validar_factura
from app.servicios.catalogo_reglas import codigos_activos, sincronizar_reglas


@dataclass
class Contrato:
    """Lo pactado con una EPS: tarifas y servicios que exige autorizar."""

    nombre_eps: str
    tarifas: dict[str, float] = field(default_factory=dict)
    codigos_con_autorizacion: set[str] = field(default_factory=set)


@dataclass
class DatosReferencia:
    """Contratos y catálogos. Se leen una sola vez por lote, no por factura."""

    contratos: dict[int, Contrato] = field(default_factory=dict)           # id de la EPS -> contrato
    descripciones: dict[str, str] = field(default_factory=dict)            # código -> descripción
    tipos_servicio: dict[str, str] = field(default_factory=dict)           # código -> tipo
    soportes_requeridos: dict[str, list[str]] = field(default_factory=dict)  # tipo -> soportes


def cargar_datos_referencia(sesion: Session) -> DatosReferencia:
    """Lee de la base de datos los contratos de todas las EPS y los catálogos."""
    referencia = DatosReferencia()

    consulta_eps = select(Eps).options(selectinload(Eps.tarifas), selectinload(Eps.autorizaciones))
    for eps in sesion.scalars(consulta_eps):
        referencia.contratos[eps.id] = Contrato(
            nombre_eps=eps.nombre,
            tarifas={tarifa.codigo_servicio: tarifa.valor for tarifa in eps.tarifas},
            codigos_con_autorizacion={autorizacion.codigo_servicio for autorizacion in eps.autorizaciones},
        )

    for servicio in sesion.scalars(select(ServicioCatalogo)):
        referencia.descripciones[servicio.codigo] = servicio.descripcion
        referencia.tipos_servicio[servicio.codigo] = servicio.tipo

    for soporte in sesion.scalars(select(SoporteRequerido).order_by(SoporteRequerido.id)):
        referencia.soportes_requeridos.setdefault(soporte.tipo_servicio, []).append(soporte.nombre_soporte)

    return referencia


def construir_contexto(factura: Factura, referencia: DatosReferencia) -> ContextoFactura:
    """Convierte una factura guardada en el contexto que reciben las reglas."""
    contrato = referencia.contratos.get(factura.eps_id) or Contrato(nombre_eps=factura.eps.nombre)
    return ContextoFactura(
        num_factura=factura.num_factura,
        valor_total=factura.valor_total,
        rips_num_factura=factura.rips_num_factura,
        items=[
            ItemFacturado(codigo=item.codigo, cantidad=item.cantidad, valor_unitario=item.valor_unitario)
            for item in factura.items
        ],
        servicios=[
            ServicioPrestado(
                clase=servicio.clase,
                codigo=servicio.codigo,
                valor=servicio.valor_servicio,
                cantidad=servicio.cantidad,
                valor_unitario=servicio.valor_unitario,
                num_autorizacion=servicio.num_autorizacion,
            )
            for servicio in factura.servicios
        ],
        soportes=[soporte.nombre for soporte in factura.soportes],
        nombre_eps=contrato.nombre_eps,
        tarifas=contrato.tarifas,
        codigos_con_autorizacion=contrato.codigos_con_autorizacion,
        descripciones=referencia.descripciones,
        tipos_servicio=referencia.tipos_servicio,
        soportes_requeridos=referencia.soportes_requeridos,
    )


def validar_lote(sesion: Session, lote: Lote) -> Lote:
    """Aplica las reglas activas a todas las facturas del lote y guarda el resultado.

    Cada validación borra los hallazgos anteriores y los calcula de nuevo. Por
    eso, si se activa o desactiva una regla, basta con validar otra vez.
    """
    sincronizar_reglas(sesion)          # asegura que todas las reglas del código estén en la tabla
    activos = codigos_activos(sesion)
    referencia = cargar_datos_referencia(sesion)

    # Se traen las facturas con todo lo que necesitan las reglas, en pocas consultas.
    consulta = (
        select(Factura)
        .where(Factura.lote_id == lote.id)
        .options(
            selectinload(Factura.eps),
            selectinload(Factura.items),
            selectinload(Factura.servicios),
            selectinload(Factura.soportes),
            selectinload(Factura.hallazgos),
        )
    )
    for factura in sesion.scalars(consulta):
        resultado = validar_factura(construir_contexto(factura, referencia), activos)
        # Al reemplazar la lista, SQLAlchemy borra los hallazgos viejos (delete-orphan).
        factura.hallazgos = [
            Hallazgo(
                regla_codigo=hallazgo.regla,
                grupo=hallazgo.grupo,
                titulo=hallazgo.titulo,
                detalle=hallazgo.detalle,
                # Tope de seguridad: una cantidad absurda en el lote no debe desbordar la columna.
                valor_en_riesgo=min(hallazgo.valor_en_riesgo, VALOR_MAXIMO),
            )
            for hallazgo in resultado.hallazgos
        ]
        factura.estado = ESTADO_APTA if resultado.apta else ESTADO_CON_INCONSISTENCIAS
        factura.valor_en_riesgo = resultado.valor_en_riesgo

    lote.estado = ESTADO_LOTE_VALIDADO
    lote.fecha_validacion = datetime.now()
    sesion.commit()
    return lote
