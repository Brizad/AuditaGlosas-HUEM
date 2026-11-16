"""Configuración del sistema: carpetas del proyecto y conexión a la base de datos.

Todo lo que cambia entre un computador y otro (dónde está la base de datos) se
lee de variables de entorno, para no tener que tocar el código.
"""
import os
from pathlib import Path

# Carpetas del proyecto, calculadas a partir de la ubicación de este archivo.
RAIZ_BACKEND = Path(__file__).resolve().parent.parent
RAIZ_PROYECTO = RAIZ_BACKEND.parent
CARPETA_DATOS = RAIZ_PROYECTO / "data"
CARPETA_FRONTEND = RAIZ_PROYECTO / "frontend"

# Archivos de datos sintéticos que usa la carga inicial.
ARCHIVO_CONTRATOS = CARPETA_DATOS / "contratos_tarifas.json"
ARCHIVO_CATALOGO = CARPETA_DATOS / "catalogo_servicios.json"
ARCHIVO_LOTE_DEMO = CARPETA_DATOS / "lote_demo.json"


def normalizar_url_base_datos(url: str | None) -> str:
    """Devuelve la dirección de la base de datos que debe usar SQLAlchemy.

    - Sin valor: se usa un archivo SQLite dentro de `backend/` (desarrollo).
    - `postgres://...` o `postgresql://...`: se ajusta para usar el
      controlador `psycopg`, que es el que se instala con el proyecto.
    """
    url = (url or "").strip()
    if not url:
        return f"sqlite:///{(RAIZ_BACKEND / 'auditaglosas.db').as_posix()}"
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo):]
    return url


# Ejemplo para PostgreSQL:
#   DATABASE_URL=postgresql://usuario:clave@localhost:5432/auditaglosas
URL_BASE_DATOS = normalizar_url_base_datos(os.getenv("DATABASE_URL"))
