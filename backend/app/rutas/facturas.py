"""Endpoint del detalle de una factura con sus hallazgos (HU-05)."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.modelos import Factura, ServicioCatalogo
from app.reglas import GRUPOS
from app.respuestas import FacturaDetalleSalida, HallazgoSalida, ItemSalida, Mensaje, ServicioSalida
from app.rutas.comunes import SesionBD

enrutador = APIRouter(prefix="/api/facturas", tags=["Facturas"])


@enrutador.get(
    "/{factura_id}",
    response_model=FacturaDetalleSalida,
    responses={404: {"model": Mensaje, "description": "La factura no existe."}},
    summary="Detalle de una factura",
)
def ver_factura(factura_id: int, sesion: SesionBD):
    """Lo facturado, lo reportado en el RIPS, los soportes y cada hallazgo con su valor en riesgo."""
    factura = sesion.scalar(
        select(Factura)
        .where(Factura.id == factura_id)
        .options(
            joinedload(Factura.lote), joinedload(Factura.eps),
            selectinload(Factura.items), selectinload(Factura.servicios),
            selectinload(Factura.soportes), selectinload(Factura.hallazgos),
        )
    )
    if factura is None:
        raise HTTPException(status_code=404, detail=f"No existe la factura {factura_id}.")

    # Descripciones del catálogo para los códigos que aparecen en esta factura.
    codigos = {item.codigo for item in factura.items} | {servicio.codigo for servicio in factura.servicios}
    descripciones = {
        servicio.codigo: servicio.descripcion
        for servicio in sesion.scalars(select(ServicioCatalogo).where(ServicioCatalogo.codigo.in_(codigos)))
    }

    return FacturaDetalleSalida(
        id=factura.id, lote_id=factura.lote_id, lote_nombre=factura.lote.nombre,
        num_factura=factura.num_factura, eps_codigo=factura.eps.codigo, eps_nombre=factura.eps.nombre,
        fecha_expedicion=factura.fecha_expedicion, valor_total=factura.valor_total,
        rips_num_factura=factura.rips_num_factura, estado=factura.estado, valor_en_riesgo=factura.valor_en_riesgo,
        items=[
            ItemSalida(
                codigo=item.codigo, descripcion=descripciones.get(item.codigo), cantidad=item.cantidad,
                valor_unitario=item.valor_unitario, valor=item.cantidad * item.valor_unitario,
            )
            for item in factura.items
        ],
        servicios=[
            ServicioSalida(
                clase=servicio.clase, codigo=servicio.codigo,
                descripcion=descripciones.get(servicio.codigo) or servicio.nombre,
                cantidad=servicio.cantidad, valor_unitario=servicio.valor_unitario,
                valor_servicio=servicio.valor_servicio, num_autorizacion=servicio.num_autorizacion,
                indice_usuario=servicio.indice_usuario,
            )
            for servicio in factura.servicios
        ],
        soportes=[soporte.nombre for soporte in factura.soportes],
        hallazgos=[
            HallazgoSalida(
                regla=hallazgo.regla_codigo, grupo=hallazgo.grupo,
                nombre_grupo=GRUPOS.get(hallazgo.grupo, hallazgo.grupo),
                titulo=hallazgo.titulo, detalle=hallazgo.detalle, valor_en_riesgo=hallazgo.valor_en_riesgo,
            )
            for hallazgo in factura.hallazgos
        ],
    )
