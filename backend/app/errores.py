"""Mensajes de error claros y en español para quien carga un lote.

Cuando el JSON no tiene la estructura esperada, Pydantic genera errores
técnicos en inglés. Aquí se traducen y se indica en qué factura y en qué campo
está el problema, por ejemplo:

    Factura n.º 4 (FV-1004) → rips → usuarios[1] → servicios → consultas[1] → vrServicio: debe ser un número.

Los mensajes nunca repiten el valor recibido, para no devolver por error datos
de un paciente.
"""
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

MAXIMO_ERRORES = 50

# tipo de error de Pydantic -> mensaje en español ({} se llena con el contexto del error)
MENSAJES = {
    "missing": "falta este campo obligatorio",
    "string_type": "debe ser texto",
    "float_type": "debe ser un número",
    "float_parsing": "debe ser un número",
    "int_type": "debe ser un número entero",
    "int_parsing": "debe ser un número entero",
    "finite_number": "debe ser un número válido",
    "bool_type": "debe ser verdadero o falso",
    "list_type": "debe ser una lista [ ]",
    "dict_type": "debe ser un objeto { }",
    "model_attributes_type": "debe ser un objeto { }",
    "date_type": "debe ser una fecha con formato AAAA-MM-DD",
    "date_parsing": "debe ser una fecha con formato AAAA-MM-DD",
    "date_from_datetime_parsing": "debe ser una fecha con formato AAAA-MM-DD",
    "date_from_datetime_inexact": "debe ser una fecha con formato AAAA-MM-DD",
    "greater_than": "debe ser mayor que {gt}",
    "greater_than_equal": "debe ser mayor o igual a {ge}",
    "less_than": "debe ser menor que {lt}",
    "less_than_equal": "debe ser menor o igual a {le}",
    "string_too_short": "no puede estar vacío",
    "string_too_long": "es demasiado largo (máximo {max_length} caracteres)",
    "string_pattern_mismatch": "no tiene el formato esperado",
    "too_short": "debe tener al menos {min_length} elemento(s)",
    "too_long": "tiene demasiados elementos (máximo {max_length})",
    "literal_error": "valor no permitido; las opciones son {expected}",
    "json_invalid": "el contenido no es un JSON válido",
}


def _numero_de_factura(cuerpo, posicion: int) -> str | None:
    """Busca el `numFactura` de la factura que está en esa posición del lote."""
    try:
        numero = cuerpo["facturas"][posicion].get("numFactura")
    except (TypeError, KeyError, IndexError, AttributeError):
        return None
    return str(numero)[:40] if isinstance(numero, (str, int)) and not isinstance(numero, bool) else None


def ubicacion_legible(ubicacion: tuple, cuerpo=None) -> str:
    """Convierte ('body','facturas',3,'rips','numFactura') en «Factura n.º 4 (FV-1004) → rips → numFactura»."""
    partes: list[str] = []
    elementos = [parte for parte in ubicacion if parte not in ("body", "query", "path")]
    indice = 0
    while indice < len(elementos):
        parte = elementos[indice]
        siguiente = elementos[indice + 1] if indice + 1 < len(elementos) else None
        if parte == "facturas" and isinstance(siguiente, int) and not partes:
            numero = _numero_de_factura(cuerpo, siguiente)
            partes.append(f"Factura n.º {siguiente + 1}" + (f" ({numero})" if numero else ""))
            indice += 2
        elif isinstance(siguiente, int):
            partes.append(f"{parte}[{siguiente + 1}]")
            indice += 2
        else:
            partes.append(str(parte))
            indice += 1
    return " → ".join(partes) or "Archivo"


def mensaje_legible(error: dict) -> str:
    """Traduce un error de Pydantic. Si no se conoce el tipo, deja el mensaje original."""
    plantilla = MENSAJES.get(error.get("type", ""))
    if plantilla is None:
        return error.get("msg", "valor no válido")
    # Los límites llegan como 0.0; se muestran como 0 para que el mensaje se lea natural.
    contexto = {
        clave: int(valor) if isinstance(valor, float) and valor.is_integer() else valor
        for clave, valor in (error.get("ctx") or {}).items()
    }
    try:
        return plantilla.format(**contexto)
    except (KeyError, IndexError):
        return plantilla


def traducir_errores(errores: list[dict], cuerpo=None) -> list[str]:
    """Lista de mensajes listos para mostrar, con un tope para no abrumar."""
    mensajes = [f"{ubicacion_legible(e.get('loc', ()), cuerpo)}: {mensaje_legible(e)}." for e in errores]
    if len(mensajes) > MAXIMO_ERRORES:
        restantes = len(mensajes) - MAXIMO_ERRORES
        mensajes = mensajes[:MAXIMO_ERRORES] + [f"… y {restantes} errores más."]
    return mensajes


async def manejar_error_de_estructura(_peticion: Request, error: RequestValidationError) -> JSONResponse:
    """Respuesta 422 cuando lo enviado no tiene la estructura esperada."""
    errores = traducir_errores(list(error.errors()), error.body)
    return JSONResponse(
        status_code=422,
        content={"detail": "Los datos enviados no tienen la estructura esperada.", "errores": errores},
    )
