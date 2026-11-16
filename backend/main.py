"""Punto de entrada del backend de AuditaGlosas HUEM.

Se ejecuta desde la carpeta `backend/` con:

    uvicorn main:app --reload

La aplicación completa se arma en `app/principal.py`.
"""
from app.principal import app

__all__ = ["app"]
