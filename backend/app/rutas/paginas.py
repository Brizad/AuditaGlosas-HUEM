"""Páginas web del frontend, servidas por FastAPI.

Cada página es un archivo HTML de la carpeta `frontend/`. El HTML no trae
datos: los pide a la API con JavaScript (`fetch`).
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.configuracion import CARPETA_FRONTEND

enrutador = APIRouter(include_in_schema=False)  # no aparecen en /docs: no son parte de la API

# dirección en el navegador -> archivo HTML
PAGINAS = {
    "/": "index.html",
    "/carga": "carga.html",
    "/resultados": "resultados.html",
    "/factura": "factura.html",
    "/reportes": "reportes.html",
    "/reglas": "reglas.html",
    "/contratos": "contratos.html",
    "/linea-base": "linea-base.html",
}


def _crear_ruta(direccion: str, archivo: str) -> None:
    """Registra una dirección que devuelve su archivo HTML."""

    @enrutador.get(direccion, response_class=FileResponse)
    def pagina():
        return FileResponse(CARPETA_FRONTEND / archivo, media_type="text/html; charset=utf-8")


for _direccion, _archivo in PAGINAS.items():
    _crear_ruta(_direccion, _archivo)
