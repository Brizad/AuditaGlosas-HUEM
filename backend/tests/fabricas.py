"""Ayudas para armar datos de prueba a mano (sin base de datos).

Todos los datos son sintéticos. El contrato por defecto es el de «EPS Beta» de
`data/contratos_tarifas.json`, que exige autorización para 871121 y 902210.
"""
from app.reglas import ContextoFactura, ItemFacturado, ServicioPrestado

TARIFAS_BETA = {
    "871121": 65000, "890201": 41000, "890301": 34000,
    "902210": 19500, "903841": 10200, "MED-0001": 480,
}
AUTORIZACIONES_BETA = {"871121", "902210"}
DESCRIPCIONES = {
    "890201": "Consulta de primera vez por medicina general",
    "890301": "Consulta de control por medicina general",
    "903841": "Glucosa en suero",
    "902210": "Hemograma",
    "871121": "Radiografía de tórax",
    "MED-0001": "Acetaminofén 500 mg tableta",
    "MED-0002": "Amoxicilina 500 mg cápsula",
}
TIPOS = {
    "890201": "consulta", "890301": "consulta", "903841": "laboratorio", "902210": "laboratorio",
    "871121": "imagen", "MED-0001": "medicamento", "MED-0002": "medicamento",
}
SOPORTES_REQUERIDOS = {
    "laboratorio": ["Resultado de laboratorio"],
    "imagen": ["Lectura o informe del examen"],
    "medicamento": ["Fórmula médica"],
}


def consulta(codigo: str, valor: float, autorizacion: str | None = None) -> ServicioPrestado:
    return ServicioPrestado(clase="consulta", codigo=codigo, valor=valor, num_autorizacion=autorizacion)


def procedimiento(codigo: str, valor: float, autorizacion: str | None = None) -> ServicioPrestado:
    return ServicioPrestado(clase="procedimiento", codigo=codigo, valor=valor, num_autorizacion=autorizacion)


def medicamento(codigo: str, cantidad: float, valor_unitario: float) -> ServicioPrestado:
    return ServicioPrestado(
        clase="medicamento", codigo=codigo, valor=cantidad * valor_unitario,
        cantidad=cantidad, valor_unitario=valor_unitario,
    )


def contexto(servicios: list[ServicioPrestado], soportes: list[str] | None = None, **cambios) -> ContextoFactura:
    """Arma una factura coherente a partir de sus servicios.

    Por defecto los ítems y el total de la factura coinciden con el RIPS; con
    `cambios` se puede dañar cualquier dato para provocar un hallazgo.
    """
    datos = dict(
        num_factura="FV-9001",
        rips_num_factura="FV-9001",
        valor_total=sum(servicio.valor for servicio in servicios),
        items=[ItemFacturado(s.codigo, s.cantidad, s.valor_unitario) for s in servicios],
        servicios=servicios,
        soportes=soportes or [],
        nombre_eps="EPS Beta",
        tarifas=dict(TARIFAS_BETA),
        codigos_con_autorizacion=set(AUTORIZACIONES_BETA),
        descripciones=dict(DESCRIPCIONES),
        tipos_servicio=dict(TIPOS),
        soportes_requeridos={tipo: list(nombres) for tipo, nombres in SOPORTES_REQUERIDOS.items()},
    )
    datos.update(cambios)
    return ContextoFactura(**datos)
