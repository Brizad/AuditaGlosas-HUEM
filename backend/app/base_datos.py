"""Conexión a la base de datos con SQLAlchemy.

Aquí se crean tres cosas que usa el resto del sistema:
- `motor_bd`: la conexión a la base de datos (SQLite o PostgreSQL).
- `SesionLocal`: fábrica de sesiones; una sesión es una "conversación" con la base.
- `Base`: clase de la que heredan todas las tablas de `modelos.py`.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.configuracion import URL_BASE_DATOS

ES_SQLITE = URL_BASE_DATOS.startswith("sqlite")
SQLITE_EN_MEMORIA = URL_BASE_DATOS in ("sqlite://", "sqlite:///:memory:")


def crear_motor(url: str) -> Engine:
    """Crea la conexión según el tipo de base de datos."""
    if not ES_SQLITE:
        # PostgreSQL: `pool_pre_ping` revisa que la conexión siga viva antes de usarla.
        return create_engine(url, pool_pre_ping=True)

    opciones: dict = {"connect_args": {"check_same_thread": False}}
    if SQLITE_EN_MEMORIA:
        # Base en memoria (pruebas): una sola conexión compartida para no perder los datos.
        opciones["poolclass"] = StaticPool
    return create_engine(url, **opciones)


motor_bd = crear_motor(URL_BASE_DATOS)


@event.listens_for(motor_bd, "connect")
def activar_llaves_foraneas(conexion, _registro) -> None:
    """SQLite trae las llaves foráneas apagadas; se encienden en cada conexión."""
    if ES_SQLITE:
        cursor = conexion.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SesionLocal = sessionmaker(bind=motor_bd, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Clase base de todas las tablas."""


def crear_tablas() -> None:
    """Crea las tablas que todavía no existan."""
    from app import modelos  # noqa: F401  (se importa para que las tablas queden registradas)

    Base.metadata.create_all(motor_bd)


def obtener_sesion() -> Iterator[Session]:
    """Entrega una sesión a cada petición de la API y la cierra al terminar."""
    sesion = SesionLocal()
    try:
        yield sesion
    finally:
        sesion.close()
