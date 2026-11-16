"""Carga los datos sintéticos de `data/` en la base de datos.

Uso (desde la carpeta `backend/`):

    python -m scripts.carga_inicial              Crea las tablas y carga lo que falte
    python -m scripts.carga_inicial --reiniciar  Borra TODO y vuelve a cargar desde cero
"""
import argparse

from app.base_datos import Base, SesionLocal, crear_tablas, motor_bd
from app.servicios.carga_inicial import ejecutar_carga_inicial


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga inicial de AuditaGlosas HUEM (datos sintéticos).")
    parser.add_argument("--reiniciar", action="store_true", help="Borra todas las tablas antes de cargar.")
    opciones = parser.parse_args()

    if opciones.reiniciar:
        from app import modelos  # noqa: F401  (registra las tablas antes de borrarlas)

        Base.metadata.drop_all(motor_bd)
        print("Tablas borradas.")

    crear_tablas()
    with SesionLocal() as sesion:
        resumen = ejecutar_carga_inicial(sesion)

    print("Carga inicial terminada:")
    print(f"  EPS con contrato:        {resumen['eps']}")
    print(f"  Servicios en catálogo:   {resumen['servicios_catalogo']}")
    print(f"  Lote de demostración:    {resumen['lote_demo']} ({resumen['facturas_lote_demo']} facturas nuevas)")


if __name__ == "__main__":
    main()
