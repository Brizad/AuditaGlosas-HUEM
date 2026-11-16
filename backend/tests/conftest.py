"""Preparación común de las pruebas.

Las pruebas usan una base de datos SQLite EN MEMORIA: se crea vacía para cada
prueba y desaparece al terminar, así nunca tocan la base de datos real.
"""
import os

# Debe ir antes de importar `app`, porque la conexión se crea al importar.
os.environ["DATABASE_URL"] = "sqlite://"

import pytest  # noqa: E402

from app import modelos  # noqa: E402,F401  (registra las tablas)
from app.base_datos import Base, SesionLocal, motor_bd  # noqa: E402
from app.servicios.carga_inicial import ejecutar_carga_inicial  # noqa: E402


@pytest.fixture()
def sesion():
    """Sesión sobre una base de datos recién creada y vacía."""
    Base.metadata.drop_all(motor_bd)
    Base.metadata.create_all(motor_bd)
    with SesionLocal() as sesion_bd:
        yield sesion_bd


@pytest.fixture()
def sesion_con_datos(sesion):
    """Sesión con la carga inicial hecha: 3 EPS, catálogo y lote demo de 12 facturas."""
    ejecutar_carga_inicial(sesion)
    return sesion
