"""Backend base de AuditaGlosas HUEM (FastAPI).

Por ahora solo: un endpoint de prueba y la carga del lote demo.
Los datos son sintéticos: nunca se guardan datos reales de pacientes.
"""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException

# Ruta al lote demo: carpeta raíz del proyecto / data / lote_demo.json
RUTA_LOTE = Path(__file__).resolve().parent.parent / "data" / "lote_demo.json"

app = FastAPI(title="AuditaGlosas HUEM", version="0.1.0")


def cargar_lote() -> list[dict]:
    """Lee el archivo JSON y devuelve la lista de facturas."""
    if not RUTA_LOTE.exists():
        raise HTTPException(status_code=404, detail=f"No existe {RUTA_LOTE.name}")
    with open(RUTA_LOTE, encoding="utf-8") as archivo:
        return json.load(archivo)


@app.get("/salud")
def salud():
    """Endpoint de prueba: confirma que el servidor está vivo."""
    return {"estado": "ok", "sistema": "AuditaGlosas HUEM"}


@app.get("/lote")
def ver_lote():
    """Resumen del lote: cantidad de facturas y sus números."""
    facturas = cargar_lote()
    return {
        "total_facturas": len(facturas),
        "facturas": [f["numFactura"] for f in facturas],
    }


@app.get("/lote/{num_factura}")
def ver_factura(num_factura: str):
    """Devuelve una factura completa (con su RIPS) por su número."""
    for factura in cargar_lote():
        if factura["numFactura"] == num_factura:
            return factura
    raise HTTPException(status_code=404, detail="Factura no encontrada")
