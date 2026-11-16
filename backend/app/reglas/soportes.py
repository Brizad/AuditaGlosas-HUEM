"""Reglas del grupo SO · Soportes (Res. 2284 de 2023)."""
from app.reglas.base import ContextoFactura, HallazgoDetectado, ReglaBase, texto_comparable
from app.reglas.registro import registrar


@registrar
class ReglaSoporteObligatorio(ReglaBase):
    """SO-01: cada servicio debe venir con los soportes que exige su tipo.

    Ejemplo: un laboratorio exige «Resultado de laboratorio»; una imagen exige
    «Lectura o informe del examen». Qué soporte exige cada tipo está en la
    tabla `soportes_requeridos`.
    """

    codigo = "SO-01"
    nombre = "Soporte obligatorio faltante"
    grupo = "SO"
    descripcion = "La factura incluye los soportes obligatorios según el tipo de servicio."

    def evaluar(self, contexto: ContextoFactura) -> list[HallazgoDetectado]:
        adjuntos = {texto_comparable(soporte) for soporte in contexto.soportes}
        hallazgos = []
        for servicio in contexto.servicios:
            tipo = contexto.tipos_servicio.get(servicio.codigo)
            for soporte in contexto.soportes_requeridos.get(tipo, []):
                if texto_comparable(soporte) not in adjuntos:
                    hallazgos.append(self.hallazgo(
                        detalle=f"{contexto.describir(servicio.codigo)} requiere «{soporte}».",
                        valor_en_riesgo=servicio.valor,
                    ))
        return hallazgos
