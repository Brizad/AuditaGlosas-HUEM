"""Motor de reglas: aplica las reglas activas a una factura."""
from collections.abc import Collection
from dataclasses import dataclass

from app.reglas.base import ContextoFactura, HallazgoDetectado
from app.reglas.registro import reglas_registradas


@dataclass(frozen=True)
class ResultadoFactura:
    """Resultado de validar una factura."""

    hallazgos: list[HallazgoDetectado]
    valor_en_riesgo: float

    @property
    def apta(self) -> bool:
        """Una factura es apta para radicar si no tiene hallazgos."""
        return not self.hallazgos


def validar_factura(contexto: ContextoFactura, codigos_activos: Collection[str] | None = None) -> ResultadoFactura:
    """Aplica a la factura cada regla registrada que esté activa.

    `codigos_activos` trae los códigos de las reglas encendidas. Si es None se
    aplican todas (útil en pruebas).

    El valor en riesgo de la factura es la suma de sus hallazgos, sin pasar del
    valor total: no se puede glosar más de lo que se facturó.
    """
    hallazgos: list[HallazgoDetectado] = []
    for regla in reglas_registradas():
        if codigos_activos is not None and regla.codigo not in codigos_activos:
            continue
        hallazgos.extend(regla.evaluar(contexto))

    suma = sum(hallazgo.valor_en_riesgo for hallazgo in hallazgos)
    valor_en_riesgo = max(0.0, min(contexto.valor_total, suma))
    return ResultadoFactura(hallazgos=hallazgos, valor_en_riesgo=valor_en_riesgo)
