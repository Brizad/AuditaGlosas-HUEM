"""Reglas del grupo AU · Autorizaciones (Res. 2284 de 2023)."""
from app.reglas.base import ContextoFactura, HallazgoDetectado, ReglaBase
from app.reglas.registro import registrar


@registrar
class ReglaAutorizacionRequerida(ReglaBase):
    """AU-01: si la EPS exige autorizar un servicio, el RIPS debe traer el número.

    Qué servicios exige autorizar cada EPS está en la tabla
    `autorizaciones_requeridas`.
    """

    codigo = "AU-01"
    nombre = "Falta número de autorización"
    grupo = "AU"
    descripcion = "Los servicios que la EPS exige autorizar tienen número de autorización."

    def evaluar(self, contexto: ContextoFactura) -> list[HallazgoDetectado]:
        hallazgos = []
        for servicio in contexto.servicios:
            exige_autorizacion = servicio.codigo in contexto.codigos_con_autorizacion
            trae_numero = bool((servicio.num_autorizacion or "").strip())
            if exige_autorizacion and not trae_numero:
                hallazgos.append(self.hallazgo(
                    detalle=f"{contexto.nombre_eps} exige autorización para {contexto.describir(servicio.codigo)}.",
                    valor_en_riesgo=servicio.valor,
                ))
        return hallazgos
