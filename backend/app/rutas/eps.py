"""Endpoints de contratos: EPS, tarifas pactadas, autorizaciones y catálogo de servicios (HU-02, HU-04)."""
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modelos import AutorizacionRequerida, Eps, Factura, ServicioCatalogo, SoporteRequerido, Tarifa
from app.respuestas import (
    AutorizacionEntrada,
    AutorizacionSalida,
    CatalogoSalida,
    EpsDetalleSalida,
    EpsEdicion,
    EpsEntrada,
    EpsSalida,
    Mensaje,
    ServicioCatalogoEntrada,
    ServicioCatalogoSalida,
    TarifaEdicion,
    TarifaEntrada,
    TarifaSalida,
)
from app.rutas.comunes import SesionBD

enrutador = APIRouter(prefix="/api/eps", tags=["Contratos y tarifas"])
enrutador_catalogo = APIRouter(prefix="/api/catalogo", tags=["Catálogo de servicios"])

NO_EXISTE = {404: {"model": Mensaje, "description": "No existe."}}
YA_EXISTE = {409: {"model": Mensaje, "description": "Ya existe o está en uso."}}


# ---------------------------------------------------------------------------
# Ayudas
# ---------------------------------------------------------------------------
def buscar_eps(sesion: Session, codigo: str) -> Eps:
    """Devuelve la EPS con sus tarifas y autorizaciones, o responde 404."""
    eps = sesion.scalar(
        select(Eps)
        .where(Eps.codigo == codigo)
        .options(selectinload(Eps.tarifas), selectinload(Eps.autorizaciones))
    )
    if eps is None:
        raise HTTPException(status_code=404, detail=f"No existe la EPS «{codigo}».")
    return eps


def buscar_tarifa(eps: Eps, codigo_servicio: str) -> Tarifa:
    for tarifa in eps.tarifas:
        if tarifa.codigo_servicio == codigo_servicio:
            return tarifa
    raise HTTPException(status_code=404, detail=f"{eps.nombre} no tiene tarifa para «{codigo_servicio}».")


def descripciones_del_catalogo(sesion: Session) -> dict[str, str]:
    return {servicio.codigo: servicio.descripcion for servicio in sesion.scalars(select(ServicioCatalogo))}


def facturas_por_eps(sesion: Session) -> dict[int, int]:
    """id de la EPS -> cuántas facturas tiene cargadas."""
    return dict(sesion.execute(select(Factura.eps_id, func.count(Factura.id)).group_by(Factura.eps_id)).all())


def eps_a_salida(eps: Eps, total_facturas: int) -> EpsSalida:
    return EpsSalida(
        codigo=eps.codigo, nombre=eps.nombre, total_tarifas=len(eps.tarifas),
        total_autorizaciones=len(eps.autorizaciones), total_facturas=total_facturas,
    )


def tarifa_a_salida(tarifa: Tarifa, eps: Eps, descripciones: dict[str, str]) -> TarifaSalida:
    exigidos = {autorizacion.codigo_servicio for autorizacion in eps.autorizaciones}
    return TarifaSalida(
        codigo_servicio=tarifa.codigo_servicio, descripcion=descripciones.get(tarifa.codigo_servicio),
        valor=tarifa.valor, requiere_autorizacion=tarifa.codigo_servicio in exigidos,
    )


def autorizaciones_a_salida(eps: Eps, descripciones: dict[str, str]) -> list[AutorizacionSalida]:
    """Servicios que la EPS exige autorizar, cada uno con su descripción del catálogo."""
    return [
        AutorizacionSalida(codigo_servicio=a.codigo_servicio, descripcion=descripciones.get(a.codigo_servicio))
        for a in eps.autorizaciones
    ]


# ---------------------------------------------------------------------------
# EPS
# ---------------------------------------------------------------------------
@enrutador.get("", response_model=list[EpsSalida], summary="Listar las EPS")
def listar_eps(sesion: SesionBD):
    conteo = facturas_por_eps(sesion)
    consulta = select(Eps).options(selectinload(Eps.tarifas), selectinload(Eps.autorizaciones)).order_by(Eps.nombre)
    return [eps_a_salida(eps, conteo.get(eps.id, 0)) for eps in sesion.scalars(consulta)]


@enrutador.post("", status_code=201, response_model=EpsSalida, responses=YA_EXISTE, summary="Crear una EPS")
def crear_eps(entrada: EpsEntrada, sesion: SesionBD):
    codigo = entrada.codigo.upper()
    if sesion.scalar(select(Eps).where(Eps.codigo == codigo)) is not None:
        raise HTTPException(status_code=409, detail=f"Ya existe una EPS con el código «{codigo}».")
    eps = Eps(codigo=codigo, nombre=entrada.nombre)
    sesion.add(eps)
    sesion.commit()
    return eps_a_salida(eps, 0)


@enrutador.get(
    "/{codigo}", response_model=EpsDetalleSalida, responses=NO_EXISTE,
    summary="Consultar una EPS con su contrato",
)
def ver_eps(codigo: str, sesion: SesionBD):
    """La EPS con sus tarifas pactadas y los servicios para los que exige autorización."""
    eps = buscar_eps(sesion, codigo)
    descripciones = descripciones_del_catalogo(sesion)
    base = eps_a_salida(eps, facturas_por_eps(sesion).get(eps.id, 0))
    return EpsDetalleSalida(
        **base.model_dump(),
        tarifas=[tarifa_a_salida(tarifa, eps, descripciones) for tarifa in eps.tarifas],
        autorizaciones=autorizaciones_a_salida(eps, descripciones),
    )


@enrutador.put("/{codigo}", response_model=EpsSalida, responses=NO_EXISTE, summary="Cambiar el nombre de una EPS")
def editar_eps(codigo: str, entrada: EpsEdicion, sesion: SesionBD):
    eps = buscar_eps(sesion, codigo)
    eps.nombre = entrada.nombre
    sesion.commit()
    return eps_a_salida(eps, facturas_por_eps(sesion).get(eps.id, 0))


@enrutador.delete(
    "/{codigo}", status_code=204, responses={**NO_EXISTE, **YA_EXISTE}, summary="Eliminar una EPS",
)
def eliminar_eps(codigo: str, sesion: SesionBD):
    """Elimina la EPS con su contrato. No se permite si tiene facturas cargadas."""
    eps = buscar_eps(sesion, codigo)
    total = facturas_por_eps(sesion).get(eps.id, 0)
    if total:
        raise HTTPException(
            status_code=409,
            detail=f"No se puede eliminar {eps.nombre}: tiene {total} factura(s) cargada(s). "
                   "Elimine primero los lotes que las contienen.",
        )
    sesion.delete(eps)
    sesion.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Tarifas pactadas
# ---------------------------------------------------------------------------
@enrutador.get(
    "/{codigo}/tarifas", response_model=list[TarifaSalida], responses=NO_EXISTE,
    summary="Listar las tarifas pactadas",
)
def listar_tarifas(codigo: str, sesion: SesionBD):
    eps = buscar_eps(sesion, codigo)
    descripciones = descripciones_del_catalogo(sesion)
    return [tarifa_a_salida(tarifa, eps, descripciones) for tarifa in eps.tarifas]


@enrutador.post(
    "/{codigo}/tarifas", status_code=201, response_model=TarifaSalida,
    responses={**NO_EXISTE, **YA_EXISTE}, summary="Agregar una tarifa pactada",
)
def crear_tarifa(codigo: str, entrada: TarifaEntrada, sesion: SesionBD):
    eps = buscar_eps(sesion, codigo)
    if any(tarifa.codigo_servicio == entrada.codigo_servicio for tarifa in eps.tarifas):
        raise HTTPException(
            status_code=409,
            detail=f"{eps.nombre} ya tiene tarifa para «{entrada.codigo_servicio}». Edítela en lugar de crearla.",
        )
    tarifa = Tarifa(codigo_servicio=entrada.codigo_servicio, valor=entrada.valor)
    eps.tarifas.append(tarifa)
    sesion.commit()
    return tarifa_a_salida(tarifa, eps, descripciones_del_catalogo(sesion))


@enrutador.put(
    "/{codigo}/tarifas/{codigo_servicio}", response_model=TarifaSalida, responses=NO_EXISTE,
    summary="Cambiar el valor de una tarifa",
)
def editar_tarifa(codigo: str, codigo_servicio: str, entrada: TarifaEdicion, sesion: SesionBD):
    eps = buscar_eps(sesion, codigo)
    tarifa = buscar_tarifa(eps, codigo_servicio)
    tarifa.valor = entrada.valor
    sesion.commit()
    return tarifa_a_salida(tarifa, eps, descripciones_del_catalogo(sesion))


@enrutador.delete(
    "/{codigo}/tarifas/{codigo_servicio}", status_code=204, responses=NO_EXISTE, summary="Eliminar una tarifa",
)
def eliminar_tarifa(codigo: str, codigo_servicio: str, sesion: SesionBD):
    eps = buscar_eps(sesion, codigo)
    eps.tarifas.remove(buscar_tarifa(eps, codigo_servicio))
    sesion.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Servicios que exigen autorización
# ---------------------------------------------------------------------------
@enrutador.get(
    "/{codigo}/autorizaciones", response_model=list[AutorizacionSalida], responses=NO_EXISTE,
    summary="Listar los servicios que exigen autorización",
)
def listar_autorizaciones(codigo: str, sesion: SesionBD):
    return autorizaciones_a_salida(buscar_eps(sesion, codigo), descripciones_del_catalogo(sesion))


@enrutador.post(
    "/{codigo}/autorizaciones", status_code=201, response_model=AutorizacionSalida,
    responses={**NO_EXISTE, **YA_EXISTE}, summary="Exigir autorización para un servicio",
)
def crear_autorizacion(codigo: str, entrada: AutorizacionEntrada, sesion: SesionBD):
    eps = buscar_eps(sesion, codigo)
    if any(a.codigo_servicio == entrada.codigo_servicio for a in eps.autorizaciones):
        raise HTTPException(
            status_code=409, detail=f"{eps.nombre} ya exige autorización para «{entrada.codigo_servicio}».",
        )
    eps.autorizaciones.append(AutorizacionRequerida(codigo_servicio=entrada.codigo_servicio))
    sesion.commit()
    return AutorizacionSalida(
        codigo_servicio=entrada.codigo_servicio,
        descripcion=descripciones_del_catalogo(sesion).get(entrada.codigo_servicio),
    )


@enrutador.delete(
    "/{codigo}/autorizaciones/{codigo_servicio}", status_code=204, responses=NO_EXISTE,
    summary="Dejar de exigir autorización para un servicio",
)
def eliminar_autorizacion(codigo: str, codigo_servicio: str, sesion: SesionBD):
    eps = buscar_eps(sesion, codigo)
    for autorizacion in eps.autorizaciones:
        if autorizacion.codigo_servicio == codigo_servicio:
            eps.autorizaciones.remove(autorizacion)
            sesion.commit()
            return Response(status_code=204)
    raise HTTPException(status_code=404, detail=f"{eps.nombre} no exige autorización para «{codigo_servicio}».")


# ---------------------------------------------------------------------------
# Catálogo de servicios (descripción y tipo de cada código)
# ---------------------------------------------------------------------------
@enrutador_catalogo.get("", response_model=CatalogoSalida, summary="Catálogo de servicios y soportes por tipo")
def ver_catalogo(sesion: SesionBD):
    """Descripción y tipo de cada servicio, y qué soportes exige cada tipo (los usa la regla SO-01)."""
    soportes: dict[str, list[str]] = {}
    for soporte in sesion.scalars(select(SoporteRequerido).order_by(SoporteRequerido.id)):
        soportes.setdefault(soporte.tipo_servicio, []).append(soporte.nombre_soporte)
    servicios = sesion.scalars(select(ServicioCatalogo).order_by(ServicioCatalogo.codigo))
    return CatalogoSalida(
        servicios=[ServicioCatalogoSalida(codigo=s.codigo, descripcion=s.descripcion, tipo=s.tipo) for s in servicios],
        soportes_requeridos=soportes,
    )


@enrutador_catalogo.put(
    "/servicios/{codigo_servicio}", response_model=ServicioCatalogoSalida,
    summary="Crear o actualizar un servicio del catálogo",
)
def guardar_servicio(
    codigo_servicio: Annotated[str, Path(pattern=r"^[A-Za-z0-9._-]{1,20}$")],
    entrada: ServicioCatalogoEntrada,
    sesion: SesionBD,
):
    """El tipo (consulta, laboratorio, imagen, medicamento…) define qué soportes exige la regla SO-01."""
    servicio = sesion.get(ServicioCatalogo, codigo_servicio)
    if servicio is None:
        servicio = ServicioCatalogo(codigo=codigo_servicio, descripcion=entrada.descripcion, tipo=entrada.tipo)
        sesion.add(servicio)
    else:
        servicio.descripcion, servicio.tipo = entrada.descripcion, entrada.tipo
    sesion.commit()
    return ServicioCatalogoSalida(codigo=servicio.codigo, descripcion=servicio.descripcion, tipo=servicio.tipo)


@enrutador_catalogo.delete(
    "/servicios/{codigo_servicio}", status_code=204, responses=NO_EXISTE,
    summary="Quitar un servicio del catálogo",
)
def eliminar_servicio(codigo_servicio: str, sesion: SesionBD):
    servicio = sesion.get(ServicioCatalogo, codigo_servicio)
    if servicio is None:
        raise HTTPException(status_code=404, detail=f"«{codigo_servicio}» no está en el catálogo.")
    sesion.delete(servicio)
    sesion.commit()
    return Response(status_code=204)
