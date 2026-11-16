"""Crea la aplicación FastAPI y conecta sus piezas."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

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


@app.middleware("http")
async def limitar_tamano(peticion: Request, siguiente):
    """Rechaza peticiones demasiado grandes antes de leerlas."""
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
