"""Motor de reglas de AuditaGlosas.

Al importar este paquete se cargan los archivos de reglas, y cada regla queda
anotada en el registro gracias al decorador `@registrar`.

Para agregar un archivo de reglas nuevo basta con importarlo aquí.
"""
from app.reglas import autorizaciones, facturacion, soportes  # noqa: F401
from app.reglas.base import GRUPOS, ContextoFactura, HallazgoDetectado, ItemFacturado, ReglaBase, ServicioPrestado
from app.reglas.motor import ResultadoFactura, validar_factura
from app.reglas.registro import obtener_regla, registrar, reglas_registradas

__all__ = [
    "GRUPOS",
    "ContextoFactura",
    "HallazgoDetectado",
    "ItemFacturado",
    "ReglaBase",
    "ResultadoFactura",
    "ServicioPrestado",
    "obtener_regla",
    "registrar",
    "reglas_registradas",
    "validar_factura",
]
