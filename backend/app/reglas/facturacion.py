"""Reglas del grupo FA · Facturación y codificación (Res. 2284 de 2023).

Comparan la factura con su RIPS: que sean del mismo número, que los valores
cuadren, que los códigos coincidan y que estén bien escritos.
"""
from app.constantes import CLASE_CONSULTA, CLASE_PROCEDIMIENTO
from app.reglas.base import TOLERANCIA, ContextoFactura, HallazgoDetectado, ReglaBase, codigo_valido, pesos
from app.reglas.registro import registrar


@registrar
class ReglaRipsCorrespondeAFactura(ReglaBase):
    """FA-01: el RIPS debe traer el mismo número de la factura.

    Si no coincide, la EPS devuelve la cuenta completa: por eso el valor en
    riesgo es el total de la factura.
    """

    codigo = "FA-01"
    nombre = "El RIPS no corresponde a la factura"
    grupo = "FA"
    descripcion = "El RIPS corresponde a la factura (mismo número de factura)."

    def evaluar(self, contexto: ContextoFactura) -> list[HallazgoDetectado]:
        if contexto.rips_num_factura == contexto.num_factura:
            return []
        numero_rips = contexto.rips_num_factura or "(vacío)"
        return [self.hallazgo(
            detalle=(
                f"La factura es {contexto.num_factura} y el RIPS reporta {numero_rips}. "
                "Causaría la devolución de la cuenta."
            ),
            valor_en_riesgo=contexto.valor_total,
        )]


@registrar
class ReglaTotalIgualASumaRips(ReglaBase):
    """FA-02: el total de la factura debe ser igual a la suma de servicios del RIPS."""

    codigo = "FA-02"
    nombre = "Valor total distinto a la suma del RIPS"
    grupo = "FA"
    descripcion = "El valor total de la factura coincide con la suma de los servicios del RIPS."

    def evaluar(self, contexto: ContextoFactura) -> list[HallazgoDetectado]:
        suma_rips = sum(servicio.valor for servicio in contexto.servicios)
        diferencia = contexto.valor_total - suma_rips
        if abs(diferencia) <= TOLERANCIA:
            return []
        return [self.hallazgo(
            detalle=(
                f"Factura: {pesos(contexto.valor_total)} · RIPS: {pesos(suma_rips)} · "
                f"diferencia {pesos(abs(diferencia))}."
            ),
            valor_en_riesgo=abs(diferencia),
        )]


@registrar
class ReglaCodigosFacturaYRips(ReglaBase):
    """FA-03: todo código cobrado debe estar en el RIPS y todo código del RIPS debe estar cobrado."""

    codigo = "FA-03"
    nombre = "Códigos distintos entre factura y RIPS"
    grupo = "FA"
    descripcion = "Cada código facturado tiene su registro en el RIPS y viceversa."

    def evaluar(self, contexto: ContextoFactura) -> list[HallazgoDetectado]:
        codigos_factura = {item.codigo for item in contexto.items}
        codigos_rips = {servicio.codigo for servicio in contexto.servicios}
        hallazgos = []

        for item in contexto.items:
            if item.codigo not in codigos_rips:
                hallazgos.append(self.hallazgo(
                    titulo="Código facturado sin registro en el RIPS",
                    detalle=f"El código {item.codigo} aparece en la factura pero no en el RIPS.",
                    valor_en_riesgo=item.valor,
                ))
        for servicio in contexto.servicios:
            if servicio.codigo not in codigos_factura:
                hallazgos.append(self.hallazgo(
                    titulo="Servicio del RIPS no facturado",
                    detalle=f"El código {servicio.codigo} está en el RIPS pero no en la factura.",
                    valor_en_riesgo=servicio.valor,
                ))
        return hallazgos


@registrar
class ReglaFormatoDeCodigo(ReglaBase):
    """FA-04: los códigos de consultas y procedimientos deben tener 6 caracteres válidos.

    Los medicamentos no se revisan aquí porque usan otra codificación.
    """

    codigo = "FA-04"
    nombre = "Código con formato inválido"
    grupo = "FA"
    descripcion = "Los códigos de procedimientos y consultas tienen formato válido (6 caracteres)."

    def evaluar(self, contexto: ContextoFactura) -> list[HallazgoDetectado]:
        hallazgos = []
        for servicio in contexto.servicios:
            es_consulta_o_procedimiento = servicio.clase in (CLASE_CONSULTA, CLASE_PROCEDIMIENTO)
            if es_consulta_o_procedimiento and not codigo_valido(servicio.codigo):
                hallazgos.append(self.hallazgo(
                    detalle=f"«{servicio.codigo}» no tiene 6 caracteres válidos (dígitos o letras mayúsculas).",
                    valor_en_riesgo=servicio.valor,
                ))
        return hallazgos
