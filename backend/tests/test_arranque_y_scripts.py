"""Arranque del servidor y scripts de consola (Fase 8)."""
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.configuracion import CARPETA_DATOS
from app.esquemas import FacturaEntrada
from app.modelos import Eps, Factura, Lote, Regla
from app.servicios.lotes import deducir_periodo
from scripts import carga_inicial as script_carga
from scripts import generar_lote as script_generador


# --- Arranque ---------------------------------------------------------------------------
def test_al_arrancar_se_crean_las_tablas_y_las_reglas(sesion):
    """Con la base vacía, encender el servidor deja las 8 reglas creadas y activas."""
    from app.principal import app

    assert sesion.scalar(select(func.count()).select_from(Regla)) == 0
    with TestClient(app) as cliente:       # el bloque `with` ejecuta el arranque (lifespan)
        reglas = cliente.get("/api/reglas").json()
        assert len(reglas) == 8 and all(regla["activa"] for regla in reglas)
        # Sin datos todavía: las páginas y los indicadores responden igual, en ceros.
        indicadores = cliente.get("/api/indicadores").json()
        assert indicadores["total_lotes"] == 0 and indicadores["resumen"]["total_facturas"] == 0
        assert cliente.get("/api/indicadores/glosas").json()["por_periodo"] == []
        assert cliente.get("/").status_code == 200


def test_el_periodo_sin_fechas_es_el_mes_actual():
    factura = FacturaEntrada(numFactura="F-1", eps="EPS-ALFA", valorTotal=0, items=[], rips={})
    assert deducir_periodo([factura]) == date.today().strftime("%Y-%m")


# --- Script de carga inicial ------------------------------------------------------------
def test_script_de_carga_inicial(sesion, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["carga_inicial"])
    script_carga.main()
    salida = capsys.readouterr().out
    assert "EPS con contrato:        3" in salida and "12 facturas nuevas" in salida
    assert sesion.scalar(select(func.count()).select_from(Factura)) == 12

    # Ejecutarlo otra vez no duplica nada.
    script_carga.main()
    assert "ya existía" in capsys.readouterr().out
    assert sesion.scalar(select(func.count()).select_from(Factura)) == 12


def test_script_de_carga_inicial_con_reiniciar_borra_lo_anterior(sesion_con_datos, monkeypatch, capsys):
    sesion_con_datos.add(Eps(codigo="EPS-TEMPORAL", nombre="EPS que debe desaparecer"))
    sesion_con_datos.commit()

    monkeypatch.setattr("sys.argv", ["carga_inicial", "--reiniciar"])
    script_carga.main()

    assert "Tablas borradas." in capsys.readouterr().out
    sesion_con_datos.expire_all()
    assert sesion_con_datos.scalar(select(func.count()).select_from(Eps)) == 3
    assert sesion_con_datos.scalar(select(func.count()).select_from(Lote)) == 1


# --- Script generador de lotes ----------------------------------------------------------
def test_script_generador_sin_opciones_crea_los_lotes_de_demostracion(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(script_generador, "CARPETA_DATOS", tmp_path)
    monkeypatch.setattr("sys.argv", ["generar_lote"])
    script_generador.main()

    salida = capsys.readouterr().out
    assert "80 con errores sembrados (40.0 %)" in salida and "30 con errores sembrados (15.0 %)" in salida
    nombres = sorted(archivo.name for archivo in tmp_path.iterdir())
    assert nombres == [
        "lote_linea_base_200.json", "lote_linea_base_200_esperado.json",
        "lote_piloto_200.json", "lote_piloto_200_esperado.json",
    ]
    # Lo generado es idéntico a lo que está guardado en data/ (misma semilla, mismo resultado).
    for nombre in nombres:
        assert (tmp_path / nombre).read_text(encoding="utf-8") == (CARPETA_DATOS / nombre).read_text(encoding="utf-8")


def test_script_generador_a_la_medida(tmp_path, monkeypatch, capsys):
    salida = tmp_path / "carpeta_nueva" / "lote_prueba.json"
    monkeypatch.setattr("sys.argv", [
        "generar_lote", "--facturas", "25", "--porcentaje-error", "20", "--semilla", "9",
        "--periodo", "2026-10", "--prefijo", "OCT", "--tipo", "piloto", "--salida", str(salida),
    ])
    script_generador.main()

    lote = json.loads(salida.read_text(encoding="utf-8"))
    esperado = json.loads((salida.parent / "lote_prueba_esperado.json").read_text(encoding="utf-8"))
    assert (lote["tipo"], lote["periodo"], len(lote["facturas"])) == ("piloto", "2026-10", 25)
    assert lote["nombre"] == "Lote sintético OCT (25 facturas)"
    assert lote["facturas"][0]["numFactura"] == "OCT-0001"
    assert (esperado["con_inconsistencias"], esperado["semilla"]) == (5, 9)
    assert "5 con errores sembrados (20.0 %)" in capsys.readouterr().out


def test_script_generador_rechaza_opciones_invalidas(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["generar_lote", "--facturas", "10", "--tipo", "otro"])
    with pytest.raises(SystemExit):
        script_generador.main()
    assert "invalid choice" in capsys.readouterr().err
