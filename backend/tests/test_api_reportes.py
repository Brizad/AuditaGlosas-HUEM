"""API de reportes por causal, por EPS, exportación CSV e indicadores (HU-05)."""
import copy
import csv
import io

import pytest

from app.servicios.reportes import celda_segura


@pytest.fixture()
def validado(cliente):
    """Cliente con el lote demo (lote 1) ya validado."""
    cliente.post("/api/lotes/1/validar")
    return cliente


def leer_csv(respuesta) -> list[list[str]]:
    texto = respuesta.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(texto), delimiter=";"))


# --- Reporte por causal -----------------------------------------------------------
def test_reporte_por_causal_del_lote_demo(validado):
    reporte = validado.get("/api/reportes/por-causal", params={"lote_id": 1}).json()
    grupos = {fila["grupo"]: fila for fila in reporte["grupos"]}

    assert list(grupos) == ["FA", "TA", "SO", "AU"]
    assert (grupos["FA"]["hallazgos"], grupos["FA"]["facturas_afectadas"], grupos["FA"]["valor_hallazgos"]) == (
        5, 4, 117000,
    )
    assert (grupos["TA"]["hallazgos"], grupos["TA"]["facturas_afectadas"], grupos["TA"]["valor_hallazgos"]) == (
        2, 2, 37000,
    )
    assert (grupos["SO"]["hallazgos"], grupos["SO"]["valor_hallazgos"]) == (1, 65000)
    assert (grupos["AU"]["hallazgos"], grupos["AU"]["valor_hallazgos"]) == (1, 65000)
    assert reporte["total_hallazgos"] == 9
    # La suma de hallazgos (284.000) supera el valor en riesgo (260.000) por el tope de la factura FV-1003.
    assert reporte["valor_hallazgos"] == 284000


def test_reporte_por_causal_detalla_cada_regla(validado):
    reporte = validado.get("/api/reportes/por-causal").json()
    reglas = {regla["codigo"]: regla for grupo in reporte["grupos"] for regla in grupo["reglas"]}
    assert len(reglas) == 8
    assert (reglas["FA-03"]["hallazgos"], reglas["FA-03"]["facturas_afectadas"]) == (2, 1)
    assert reglas["FA-03"]["valor_hallazgos"] == 36000
    assert reglas["TA-01"]["valor_hallazgos"] == 5000 and reglas["TA-02"]["valor_hallazgos"] == 32000


def test_reporte_por_causal_sin_validar_sale_en_ceros(cliente):
    reporte = cliente.get("/api/reportes/por-causal").json()
    assert reporte["total_hallazgos"] == 0 and len(reporte["grupos"]) == 4


# --- Reporte por EPS ----------------------------------------------------------------
def test_reporte_por_eps_del_lote_demo(validado):
    filas = {fila["eps_codigo"]: fila for fila in validado.get("/api/reportes/por-eps").json()["filas"]}

    def cifras(codigo):
        fila = filas[codigo]
        return fila["total_facturas"], fila["aptas"], fila["con_inconsistencias"], fila["valor_en_riesgo"]

    assert cifras("EPS-ALFA") == (5, 2, 3, 76000)
    assert cifras("EPS-BETA") == (4, 2, 2, 147000)
    assert cifras("EPS-GAMMA") == (3, 1, 2, 37000)
    assert filas["EPS-ALFA"]["eps_nombre"] == "EPS Alfa"
    assert filas["EPS-ALFA"]["porcentaje_con_inconsistencias"] == 60.0
    assert sum(fila["valor_en_riesgo"] for fila in filas.values()) == 260000


def test_filtros_de_los_reportes(validado):
    otro_periodo = validado.get("/api/reportes/por-eps", params={"periodo": "2025-01"}).json()["filas"]
    assert len(otro_periodo) == 3 and all(fila["total_facturas"] == 0 for fila in otro_periodo)

    mismo_periodo = validado.get("/api/reportes/por-causal", params={"periodo": "2026-06"}).json()
    assert mismo_periodo["total_hallazgos"] == 9
    assert validado.get("/api/reportes/por-causal", params={"tipo": "piloto"}).json()["total_hallazgos"] == 0
    assert validado.get("/api/reportes/por-causal", params={"periodo": "junio"}).status_code == 422
    assert validado.get("/api/reportes/por-causal", params={"lote_id": 0}).status_code == 422


# --- Exportación a CSV ----------------------------------------------------------------
def test_exportar_csv(validado):
    respuesta = validado.get("/api/reportes/exportar.csv", params={"lote_id": 1})
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/csv")
    assert 'filename="reporte_validacion_lote_1.csv"' in respuesta.headers["content-disposition"]
    assert respuesta.content.startswith(b"\xef\xbb\xbf")          # BOM para que Excel lea las tildes

    filas = leer_csv(respuesta)
    assert filas[0] == [
        "lote", "periodo", "factura", "eps", "valor_factura", "estado",
        "regla", "grupo", "hallazgo", "detalle", "valor_en_riesgo",
    ]
    datos = filas[1:]
    assert len(datos) == 14                                        # 9 hallazgos + 5 facturas aptas
    assert sum(1 for fila in datos if fila[5] == "Apta") == 5
    assert sum(int(fila[10]) for fila in datos) == 284000

    fila_tarifa = next(fila for fila in datos if fila[2] == "FV-1005")
    assert fila_tarifa[3:9] == ["EPS-GAMMA", "41000", "Corregir", "TA-01", "Tarifas", "Tarifa distinta a la pactada"]
    assert fila_tarifa[10] == "5000"


def test_exportar_csv_sin_validar_marca_las_facturas(cliente):
    datos = leer_csv(cliente.get("/api/reportes/exportar.csv"))[1:]
    assert len(datos) == 12 and all(fila[5] == "Sin validar" for fila in datos)


def test_el_csv_no_deja_pasar_formulas_de_excel(cliente, lote_demo_json):
    factura = copy.deepcopy(lote_demo_json[0])
    factura["numFactura"] = factura["rips"]["numFactura"] = "=HYPERLINK(\"http://x\")"
    lote = cliente.post("/api/lotes", json={"nombre": "+Lote raro", "facturas": [factura]}).json()
    datos = leer_csv(cliente.get("/api/reportes/exportar.csv", params={"lote_id": lote["id"]}))[1:]
    assert datos[0][0] == "'+Lote raro"
    assert datos[0][2].startswith("'=HYPERLINK")


@pytest.mark.parametrize("valor, esperado", [
    ("=1+1", "'=1+1"), ("+57", "'+57"), ("-5", "'-5"), ("@cmd", "'@cmd"),
    ("FV-1001", "FV-1001"), ("", ""), (None, ""), (38000, "38000"),
])
def test_celda_segura(valor, esperado):
    assert celda_segura(valor) == esperado


# --- Indicadores generales ----------------------------------------------------------------
def test_indicadores_generales(validado):
    indicadores = validado.get("/api/indicadores").json()
    assert indicadores["total_lotes"] == 1
    assert indicadores["eps_registradas"] == 3
    assert (indicadores["reglas_activas"], indicadores["total_reglas"]) == (8, 8)
    resumen = indicadores["resumen"]
    assert (resumen["total_facturas"], resumen["aptas"], resumen["con_inconsistencias"]) == (12, 5, 7)
    assert resumen["valor_en_riesgo"] == 260000 and resumen["valor_facturado"] == 664800
    assert [fila["grupo"] for fila in indicadores["hallazgos_por_grupo"]] == ["FA", "TA", "SO", "AU"]
    assert indicadores["ultimos_lotes"][0]["nombre"] == "Lote de demostración (Sprint 0)"


def test_indicadores_cuentan_las_reglas_inactivas(validado):
    validado.post("/api/reglas/FA-04/desactivar")
    indicadores = validado.get("/api/indicadores").json()
    assert (indicadores["reglas_activas"], indicadores["total_reglas"]) == (7, 8)
