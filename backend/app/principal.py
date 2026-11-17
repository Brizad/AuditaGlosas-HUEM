"""Crea la aplicación FastAPI y conecta sus piezas."""
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as ErrorHttp

from app.base_datos import SesionLocal, crear_tablas
from app.configuracion import CARPETA_FRONTEND
from app.errores import manejar_error_de_estructura
from app.rutas import eps, facturas, indicadores, lotes, paginas, reglas, reportes
from app.servicios.catalogo_reglas import sincronizar_reglas

DESCRIPCION = (
    "Sistema de auditoría y control de glosas del Hospital Universitario Erasmo Meoz. "
    "Valida cada factura contra su RIPS, sus soportes y las tarifas pactadas antes de radicarla "
    "(Res. 2275 y 2284 de 2023). Solo usa datos sintéticos."
)

# Tamaño máximo de lo que se puede enviar en una petición (un lote grande pesa pocos MB).
MAXIMO_BYTES = 20 * 1024 * 1024

# Política de seguridad de contenido: el navegador solo carga scripts y estilos de este mismo
# servidor. Si un dato malicioso lograra colarse en una página, no podría ejecutar código.
POLITICA_DE_CONTENIDO = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
# La documentación automática carga sus archivos desde internet, por eso no lleva la política.
RUTAS_DE_DOCUMENTACION = ("/docs", "/redoc", "/openapi.json")

METODOS_QUE_CAMBIAN_DATOS = {"POST", "PUT", "PATCH", "DELETE"}
# Valores de la cabecera `Sec-Fetch-Site` que indican que la petición sale de este mismo sistema.
SITIOS_PROPIOS = {"same-origin", "none"}

# Textos que el servidor trae en inglés para direcciones que no existen.
MENSAJES_HTTP = {
    "Not Found": "No existe esa dirección.",
    "Method Not Allowed": "Esa operación no está permitida en esta dirección.",
}
MENSAJE_ERROR_BASE_DE_DATOS = (
    "No se pudo completar la operación en la base de datos. Intente de nuevo; "
    "si el problema sigue, avise al área de sistemas."
)

registro = logging.getLogger("auditaglosas")


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    """Lo que se hace una sola vez al arrancar el servidor."""
    crear_tablas()
    # Las reglas nuevas que haya en el código quedan creadas (y activas) en la tabla.
    with SesionLocal() as sesion:
        sincronizar_reglas(sesion)
    yield


app = FastAPI(title="AuditaGlosas HUEM", version="1.0.0", description=DESCRIPCION, lifespan=ciclo_de_vida)

# Errores de estructura en español en lugar del mensaje técnico por defecto.
app.add_exception_handler(RequestValidationError, manejar_error_de_estructura)


@app.exception_handler(ErrorHttp)
async def manejar_error_http(_peticion: Request, error: ErrorHttp):
    """Errores como «no existe»: mismo formato de siempre, con los textos por defecto traducidos."""
    detalle = MENSAJES_HTTP.get(error.detail, error.detail) if isinstance(error.detail, str) else error.detail
    return JSONResponse(status_code=error.status_code, content={"detail": detalle}, headers=error.headers)


@app.exception_handler(SQLAlchemyError)
async def manejar_error_de_base_de_datos(_peticion: Request, error: SQLAlchemyError):
    """Si la base de datos falla, se responde en español y el detalle técnico queda solo en el registro."""
    registro.error("Error de base de datos: %s", type(error).__name__, exc_info=error)
    return JSONResponse(status_code=500, content={"detail": MENSAJE_ERROR_BASE_DE_DATOS})


def viene_de_otro_sitio(peticion: Request) -> bool:
    """Indica si la petición la disparó una página que no es de este sistema.

    El navegador avisa desde qué sitio sale cada petición y una página no puede falsificar ese aviso:
    - `Sec-Fetch-Site` (navegadores actuales): «same-origin» si sale de este mismo sistema.
    - `Origin` (navegadores antiguos): la dirección del sitio que la envía; se compara con la nuestra.
    Los programas que no son navegadores (curl, scripts, pruebas) no envían esas cabeceras y pasan.
    """
    sitio = peticion.headers.get("sec-fetch-site", "").lower()
    if sitio:
        # «none» es cuando la persona escribe la dirección ella misma; lo demás viene de otra página.
        return sitio not in SITIOS_PROPIOS
    origen = peticion.headers.get("origin")
    if origen is None:
        return False
    return urlsplit(origen).netloc.lower() != peticion.headers.get("host", "").lower()


@app.middleware("http")
async def proteger_cambios(peticion: Request, siguiente):
    """Revisa las peticiones que modifican datos antes de atenderlas.

    1. Solo se aceptan si salen de las páginas del propio sistema. Como no hay inicio de sesión,
       sin esto cualquier página abierta en el mismo navegador podría, por ejemplo, apagar reglas.
    2. Deben declarar su tamaño y no pasar del máximo, para no recibir archivos enormes.
    """
    if peticion.method in METODOS_QUE_CAMBIAN_DATOS and viene_de_otro_sitio(peticion):
        return JSONResponse(
            status_code=403, content={"detail": "Solo se aceptan cambios hechos desde las páginas del sistema."},
        )
    if "chunked" in peticion.headers.get("transfer-encoding", "").lower():
        # Un envío «por trozos» no dice cuánto pesa: no se podría aplicar el límite.
        return JSONResponse(status_code=411, content={"detail": "La petición debe indicar su tamaño (Content-Length)."})
    tamano = peticion.headers.get("content-length", "")
    if tamano.isdigit() and int(tamano) > MAXIMO_BYTES:
        return JSONResponse(status_code=413, content={"detail": "El archivo es demasiado grande (máximo 20 MB)."})
    return await siguiente(peticion)


@app.middleware("http")
async def agregar_cabeceras_de_seguridad(peticion: Request, siguiente):
    """Agrega a cada respuesta las cabeceras que protegen al navegador."""
    respuesta = await siguiente(peticion)
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "no-referrer"
    if not peticion.url.path.startswith(RUTAS_DE_DOCUMENTACION):
        respuesta.headers["Content-Security-Policy"] = POLITICA_DE_CONTENIDO
        # El navegador siempre pregunta si hay una versión más nueva (los datos cambian a menudo).
        respuesta.headers.setdefault("Cache-Control", "no-cache")
    return respuesta


@app.get("/api/salud", tags=["Sistema"], summary="Estado del servidor")
def salud():
    """Confirma que el servidor está vivo."""
    return {"estado": "ok", "sistema": "AuditaGlosas HUEM"}


# Cada archivo de `rutas/` aporta un grupo de endpoints.
app.include_router(lotes.enrutador)
app.include_router(facturas.enrutador)
app.include_router(reportes.enrutador)
app.include_router(reglas.enrutador)
app.include_router(eps.enrutador)
app.include_router(eps.enrutador_catalogo)
app.include_router(indicadores.enrutador)

# Frontend: las páginas HTML y sus archivos de estilos y JavaScript.
app.include_router(paginas.enrutador)
app.mount("/static", StaticFiles(directory=CARPETA_FRONTEND), name="static")
