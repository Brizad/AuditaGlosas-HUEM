"""Crea la aplicación FastAPI y conecta sus piezas."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.base_datos import crear_tablas

DESCRIPCION = (
    "Sistema de auditoría y control de glosas del Hospital Universitario Erasmo Meoz. "
    "Valida cada factura contra su RIPS, sus soportes y las tarifas pactadas antes de radicarla "
    "(Res. 2275 y 2284 de 2023). Solo usa datos sintéticos."
)


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    """Lo que se hace una sola vez al arrancar el servidor."""
    crear_tablas()
    yield


app = FastAPI(title="AuditaGlosas HUEM", version="1.0.0", description=DESCRIPCION, lifespan=ciclo_de_vida)


@app.get("/api/salud", tags=["Sistema"])
def salud():
    """Confirma que el servidor está vivo."""
    return {"estado": "ok", "sistema": "AuditaGlosas HUEM"}
