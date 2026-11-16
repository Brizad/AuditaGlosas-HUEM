"""Guardar, resumir y eliminar lotes de facturas (HU-01)."""
from collections import Counter
from dataclasses import dataclass
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.constantes import (
    CLASE_CONSULTA,
    CLASE_MEDICAMENTO,
    CLASE_PROCEDIMIENTO,
    ESTADO_APTA,
    ESTADO_CON_INCONSISTENCIAS,
    ESTADO_SIN_VALIDAR,
)
from app.esquemas import FacturaEntrada, LoteEntrada
from app.modelos import (
    Eps,
    Factura,
    ItemFactura,
    Lote,
    ServicioRips,
    SoporteFactura,
)


class ErrorDeCarga(Exception):
    """El lote tiene buena estructura pero no se puede guardar.

    Lleva la lista de problemas para mostrársela completa al facturador.
    """

    def __init__(self, errores: list[str]):
        super().__init__("; ".join(errores))
        self.errores = errores


def deducir_periodo(facturas: list[FacturaEntrada]) -> str:
    """Devuelve el mes (AAAA-MM) que más se repite en las fechas de expedición.

    Si ninguna factura trae fecha, se usa el mes actual.
    """
    meses = Counter(f.fechaExpedicion.strftime("%Y-%m") for f in facturas if f.fechaExpedicion)
    if not meses:
        return date.today().strftime("%Y-%m")
    return meses.most_common(1)[0][0]


def _revisar_lote(entrada: LoteEntrada, codigos_eps: set[str]) -> list[str]:
    """Busca facturas repetidas y EPS que no estén registradas."""
    errores: list[str] = []
    vistas: set[str] = set()
    for posicion, factura in enumerate(entrada.facturas, start=1):
        if factura.numFactura in vistas:
            errores.append(f"Factura n.º {posicion} ({factura.numFactura}): está repetida dentro del lote.")
        vistas.add(factura.numFactura)
        if factura.eps not in codigos_eps:
            errores.append(
                f"Factura n.º {posicion} ({factura.numFactura}): la EPS «{factura.eps}» no está registrada. "
                "Créela primero en «Contratos y tarifas»."
            )
    return errores


def _servicios_del_rips(entrada: FacturaEntrada) -> list[ServicioRips]:
    """Convierte consultas, procedimientos y medicamentos del RIPS en filas de una sola tabla."""
    servicios: list[ServicioRips] = []
    for indice, usuario in enumerate(entrada.rips.usuarios, start=1):
        for consulta in usuario.servicios.consultas:
            servicios.append(ServicioRips(
                clase=CLASE_CONSULTA, codigo=consulta.codConsulta, cantidad=1,
                valor_unitario=consulta.vrServicio, valor_servicio=consulta.vrServicio,
                num_autorizacion=consulta.numAutorizacion, indice_usuario=indice,
            ))
        for procedimiento in usuario.servicios.procedimientos:
            servicios.append(ServicioRips(
                clase=CLASE_PROCEDIMIENTO, codigo=procedimiento.codProcedimiento, cantidad=1,
                valor_unitario=procedimiento.vrServicio, valor_servicio=procedimiento.vrServicio,
                num_autorizacion=procedimiento.numAutorizacion, indice_usuario=indice,
            ))
        for medicamento in usuario.servicios.medicamentos:
            servicios.append(ServicioRips(
                clase=CLASE_MEDICAMENTO, codigo=medicamento.codTecnologiaSalud,
                nombre=(medicamento.nomTecnologiaSalud or None),
                cantidad=medicamento.cantidadMedicamento,
                valor_unitario=medicamento.vrUnitMedicamento, valor_servicio=medicamento.vrServicio,
                num_autorizacion=medicamento.numAutorizacion, indice_usuario=indice,
            ))
    return servicios


def guardar_lote(sesion: Session, entrada: LoteEntrada) -> Lote:
    """Guarda el lote con todas sus facturas. Si algo no cuadra, no guarda nada.

    Lanza `ErrorDeCarga` si hay facturas repetidas o EPS sin registrar.
    """
    eps_por_codigo = {eps.codigo: eps for eps in sesion.scalars(select(Eps))}
    errores = _revisar_lote(entrada, set(eps_por_codigo))
    if errores:
        raise ErrorDeCarga(errores)

    lote = Lote(
        nombre=entrada.nombre,
        tipo=entrada.tipo,
        periodo=entrada.periodo or deducir_periodo(entrada.facturas),
    )
    for factura in entrada.facturas:
        lote.facturas.append(Factura(
            num_factura=factura.numFactura,
            eps=eps_por_codigo[factura.eps],
            fecha_expedicion=factura.fechaExpedicion,
            valor_total=factura.valorTotal,
            rips_num_factura=factura.rips.numFactura,
            items=[
                ItemFactura(codigo=item.codigo, cantidad=item.cantidad, valor_unitario=item.valorUnitario)
                for item in factura.items
            ],
            servicios=_servicios_del_rips(factura),
            soportes=[SoporteFactura(nombre=nombre) for nombre in factura.soportes],
        ))

    sesion.add(lote)
    sesion.commit()
    return lote


def eliminar_lote(sesion: Session, lote: Lote) -> None:
    """Borra el lote con sus facturas, servicios, soportes y hallazgos."""
    sesion.delete(lote)
    sesion.commit()


@dataclass(frozen=True)
class ResumenLote:
    """Las cifras que se muestran en las tarjetas de resultados."""

    total_facturas: int
    aptas: int
    con_inconsistencias: int
    sin_validar: int
    valor_facturado: float
    valor_en_riesgo: float

    @property
    def porcentaje_aptas(self) -> float:
        """Porcentaje de facturas aptas sobre las ya validadas."""
        validadas = self.aptas + self.con_inconsistencias
        return round(100 * self.aptas / validadas, 1) if validadas else 0.0


def resumir_lote(sesion: Session, lote_id: int) -> ResumenLote:
    """Cuenta las facturas del lote por estado y suma sus valores (una sola consulta)."""

    def contar_estado(estado: str):
        return func.coalesce(func.sum(case((Factura.estado == estado, 1), else_=0)), 0)

    fila = sesion.execute(
        select(
            func.count(Factura.id),
            contar_estado(ESTADO_APTA),
            contar_estado(ESTADO_CON_INCONSISTENCIAS),
            contar_estado(ESTADO_SIN_VALIDAR),
            func.coalesce(func.sum(Factura.valor_total), 0),
            func.coalesce(func.sum(Factura.valor_en_riesgo), 0),
        ).where(Factura.lote_id == lote_id)
    ).one()
    return ResumenLote(
        total_facturas=fila[0], aptas=int(fila[1]), con_inconsistencias=int(fila[2]), sin_validar=int(fila[3]),
        valor_facturado=float(fila[4]), valor_en_riesgo=float(fila[5]),
    )
