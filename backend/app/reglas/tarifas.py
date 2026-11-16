"""Reglas del grupo TA · Tarifas (Res. 2284 de 2023).

Comparan lo cobrado con las tarifas pactadas en el contrato de la EPS
(tabla `tarifas`).
"""
from app.constantes import CLASE_MEDICAMENTO
from app.reglas.base import TOLERANCIA, ContextoFactura, HallazgoDetectado, ReglaBase, codigo_valido, pesos
from app.reglas.registro import registrar


@registrar
class ReglaTarifaPactada(ReglaBase):
    """TA-01: el valor unitario cobrado debe ser igual a la tarifa pactada.

    El valor en riesgo es la diferencia por la cantidad: si se cobraron 20
    tabletas a $500 y lo pactado es $480, están en riesgo 20 × $20 = $400.
    """

    codigo = "TA-01"
    nombre = "Tarifa distinta a la pactada"
    grupo = "TA"
    descripcion = "El valor unitario coincide con la tarifa pactada en el contrato de la EPS."

    def evaluar(self, contexto: ContextoFactura) -> list[HallazgoDetectado]:
        hallazgos = []
        for servicio in contexto.servicios:
            tarifa = contexto.tarifas.get(servicio.codigo)
            if tarifa is None:
                continue  # sin tarifa pactada: lo reporta TA-02
            diferencia = abs(servicio.valor_unitario - tarifa)
            if diferencia > TOLERANCIA:
                hallazgos.append(self.hallazgo(
                    detalle=(
                        f"{contexto.describir(servicio.codigo)}: facturado {pesos(servicio.valor_unitario)}, "
                        f"pactado con {contexto.nombre_eps} {pesos(tarifa)}."
                    ),
                    valor_en_riesgo=diferencia * servicio.cantidad,
                ))
        return hallazgos


@registrar
class ReglaServicioConTarifa(ReglaBase):
    """TA-02: todo servicio cobrado debe tener tarifa pactada con la EPS.

    Si el código de una consulta o procedimiento está mal escrito no se reporta
    aquí, porque ese error ya lo reporta FA-04 y sería contarlo dos veces.
    """

    codigo = "TA-02"
    nombre = "Servicio sin tarifa pactada"
    grupo = "TA"
    descripcion = "El servicio tiene tarifa pactada en el contrato de la EPS."

    def evaluar(self, contexto: ContextoFactura) -> list[HallazgoDetectado]:
        hallazgos = []
        for servicio in contexto.servicios:
            if servicio.codigo in contexto.tarifas:
                continue
            if servicio.clase == CLASE_MEDICAMENTO or codigo_valido(servicio.codigo):
                hallazgos.append(self.hallazgo(
                    detalle=(
                        f"{contexto.describir(servicio.codigo)} no tiene tarifa "
                        f"en el contrato con {contexto.nombre_eps}."
                    ),
                    valor_en_riesgo=servicio.valor,
                ))
        return hallazgos
