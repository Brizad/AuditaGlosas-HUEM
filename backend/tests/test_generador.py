"""Generador de lotes sintéticos (Fase 7): el motor debe detectar exactamente los errores sembrados."""
import json

import pytest
from sqlalchemy import select

from app.base_datos import Base
from app.configuracion import CARPETA_DATOS
from app.esquemas import LoteEntrada
from app.servicios.catalogo_reglas import sincronizar_reglas
from app.servicios.lotes import guardar_lote, resumir_lote
from app.servicios.validacion import validar_lote
from scripts.generar_lote import LOTES_DE_DEMOSTRACION, PESOS_DE_ERROR, generar_lote, ruta_del_esperado


def parametros(definicion: dict) -> dict:
    return {clave: valor for clave, valor in definicion.items() if clave != "archivo"}


def generar(cantidad=120, porcentaje_error=50, semilla=1, tipo="general"):
    return generar_lote(
        cantidad=cantidad, porcentaje_error=porcentaje_error, semilla=semilla,
        periodo="2026-09", prefijo="PR", nombre=f"Prueba {semilla}", tipo=tipo,
    )


def reglas_detectadas(sesion, lote_json: dict) -> dict[str, list[str]]:
    """Carga y valida el lote; devuelve factura -> reglas incumplidas (solo las que tienen hallazgos)."""
    sincronizar_reglas(sesion)
    lote = guardar_lote(sesion, LoteEntrada(**lote_json))
    validar_lote(sesion, lote)
    return {
        factura.num_factura: sorted({hallazgo.regla_codigo for hallazgo in factura.hallazgos})
        for factura in lote.facturas if factura.hallazgos
    }


# --- El generador ---------------------------------------------------------------------
def test_la_misma_semilla_produce_el_mismo_lote():
    assert generar(semilla=7) == generar(semilla=7)
    assert generar(semilla=7)[0]["facturas"] != generar(semilla=8)[0]["facturas"]


def test_el_lote_trae_la_cantidad_y_el_porcentaje_pedidos():
    lote, esperado = generar(cantidad=200, porcentaje_error=40, tipo="linea_base")

    assert (lote["tipo"], lote["periodo"]) == ("linea_base", "2026-09")
    assert len(lote["facturas"]) == 200
    assert len({factura["numFactura"] for factura in lote["facturas"]}) == 200       # sin números repetidos
    assert {factura["eps"] for factura in lote["facturas"]} == {"EPS-ALFA", "EPS-BETA", "EPS-GAMMA"}
    assert all(factura["fechaExpedicion"].startswith("2026-09-") for factura in lote["facturas"])
    assert (esperado["con_inconsistencias"], esperado["aptas"]) == (80, 120)
    assert esperado["porcentaje_con_inconsistencias"] == 40.0
    assert len(esperado["reglas_por_factura"]) == 80
    assert set(esperado["facturas_por_regla"]) == set(PESOS_DE_ERROR)


def test_el_lote_tiene_la_estructura_que_acepta_la_carga():
    lote, _ = generar()
    entrada = LoteEntrada(**lote)        # si la estructura fuera inválida, aquí fallaría
    assert len(entrada.facturas) == 120


def test_los_documentos_son_inventados_y_se_reconocen_como_sinteticos():
    lote, _ = generar()
    for factura in lote["facturas"]:
        for usuario in factura["rips"]["usuarios"]:
            assert usuario["numDocumentoIdentificacion"].startswith("SINT")


@pytest.mark.parametrize("porcentaje, con_error", [(0, 0), (100, 60)])
def test_porcentajes_extremos(sesion_con_datos, porcentaje, con_error):
    lote, esperado = generar(cantidad=60, porcentaje_error=porcentaje)
    assert esperado["con_inconsistencias"] == con_error
    assert len(reglas_detectadas(sesion_con_datos, lote)) == con_error


@pytest.mark.parametrize("argumentos", [{"cantidad": 0}, {"cantidad": 5001}, {"porcentaje_error": -1}, {"porcentaje_error": 101}])
def test_parametros_fuera_de_rango_se_rechazan(argumentos):
    with pytest.raises(ValueError):
        generar(**argumentos)


# --- El motor contra los errores sembrados --------------------------------------------
@pytest.mark.parametrize("semilla", [1, 2, 3, 4, 5])
def test_el_motor_detecta_exactamente_los_errores_sembrados(sesion_con_datos, semilla):
    """Ni un error de menos (falso negativo) ni uno de más (falso positivo), factura por factura."""
    lote, esperado = generar(cantidad=300, porcentaje_error=50, semilla=semilla)
    assert reglas_detectadas(sesion_con_datos, lote) == esperado["reglas_por_factura"]


def test_cada_regla_aparece_en_los_lotes_de_prueba():
    """Con 300 facturas y 50 % de error, las 8 reglas quedan cubiertas."""
    _, esperado = generar(cantidad=300, porcentaje_error=50)
    assert all(cantidad > 0 for cantidad in esperado["facturas_por_regla"].values())


def test_el_documento_sintetico_tampoco_se_guarda(sesion_con_datos):
    """Aunque sea inventado, el documento del usuario no llega a la base de datos (Ley 1581 de 2012)."""
    lote, _ = generar(cantidad=20)
    reglas_detectadas(sesion_con_datos, lote)

    # Se recorre TODA la base de datos buscando la marca de los documentos generados.
    for tabla in Base.metadata.sorted_tables:
        for fila in sesion_con_datos.execute(select(tabla)):
            assert not any(isinstance(valor, str) and "SINT0" in valor for valor in fila), tabla.name


# --- Los lotes de demostración guardados en data/ ---------------------------------------
@pytest.mark.parametrize("definicion", LOTES_DE_DEMOSTRACION, ids=lambda definicion: definicion["archivo"])
def test_los_archivos_de_data_estan_al_dia_con_el_generador(definicion):
    """Si alguien cambia el generador, debe volver a ejecutar `python -m scripts.generar_lote`."""
    ruta = CARPETA_DATOS / definicion["archivo"]
    lote, esperado = generar_lote(**parametros(definicion))
    assert json.loads(ruta.read_text(encoding="utf-8")) == lote
    assert json.loads(ruta_del_esperado(ruta).read_text(encoding="utf-8")) == esperado


@pytest.mark.parametrize(
    "archivo, con_inconsistencias, aptas",
    [("lote_linea_base_200.json", 80, 120), ("lote_piloto_200.json", 30, 170)],
)
def test_los_lotes_de_demostracion_dan_el_resultado_esperado(sesion_con_datos, archivo, con_inconsistencias, aptas):
    ruta = CARPETA_DATOS / archivo
    lote_json = json.loads(ruta.read_text(encoding="utf-8"))
    esperado = json.loads(ruta_del_esperado(ruta).read_text(encoding="utf-8"))

    detectadas = reglas_detectadas(sesion_con_datos, lote_json)
    assert detectadas == esperado["reglas_por_factura"]
    assert len(detectadas) == con_inconsistencias

    resumen = resumir_lote(sesion_con_datos, 2)      # el lote 1 es el demo de la carga inicial
    assert (resumen.total_facturas, resumen.aptas, resumen.con_inconsistencias) == (200, aptas, con_inconsistencias)
    assert resumen.valor_en_riesgo > 0


def test_prueba_z_con_los_lotes_de_demostracion_por_la_api(cliente):
    """Flujo completo de HU-07: cargar línea base y piloto, validarlos y comparar (40 % contra 15 %)."""
    for definicion in LOTES_DE_DEMOSTRACION:
        lote_json = json.loads((CARPETA_DATOS / definicion["archivo"]).read_text(encoding="utf-8"))
        lote = cliente.post("/api/lotes", json=lote_json)
        assert lote.status_code == 201
        assert lote.json()["tipo"] == definicion["tipo"] and lote.json()["periodo"] == definicion["periodo"]
        cliente.post(f"/api/lotes/{lote.json()['id']}/validar")

    r = cliente.post("/api/indicadores/prueba-z", json={}).json()
    assert (r["glosadas_linea_base"], r["total_linea_base"]) == (80, 200)
    assert (r["glosadas_piloto"], r["total_piloto"]) == (30, 200)
    assert r["z"] == pytest.approx(5.599, abs=1e-3)
    assert r["valor_p"] < 0.001 and r["se_rechaza_h0"] is True
    assert r["supuestos_cumplidos"] is True and r["advertencias"] == []

    glosas = cliente.get("/api/indicadores/glosas", params={"tipo": "piloto"}).json()
    assert glosas["total"]["porcentaje_glosadas"] == 15.0
