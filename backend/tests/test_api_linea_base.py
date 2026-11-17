"""API del indicador de glosas y de la prueba z entre línea base y piloto (HU-07)."""
import pytest

from app.servicios.estadistica import prueba_z_dos_proporciones

# Facturas del lote demo que quedan aptas y una que queda con inconsistencias (TA-01).
APTAS = ["FV-1001", "FV-1002", "FV-1004", "FV-1008", "FV-1010"]
CON_ERROR = "FV-1005"


@pytest.fixture()
def validado(cliente):
    """Cliente con el lote demo (lote 1, tipo general, junio de 2026) ya validado."""
    cliente.post("/api/lotes/1/validar")
    return cliente


def cargar_y_validar(cliente, facturas, nombre, tipo, periodo=None):
    cuerpo = {"nombre": nombre, "tipo": tipo, "facturas": facturas}
    if periodo:
        cuerpo["periodo"] = periodo
    lote = cliente.post("/api/lotes", json=cuerpo)
    assert lote.status_code == 201, lote.text
    assert cliente.post(f"/api/lotes/{lote.json()['id']}/validar").status_code == 200
    return lote.json()["id"]


@pytest.fixture()
def con_base_y_piloto(validado, lote_demo_json):
    """Además del lote general: línea base con 7 glosadas de 12 y piloto con 1 glosada de 6."""
    cargar_y_validar(validado, lote_demo_json, "Línea base de prueba", "linea_base", "2026-05")
    piloto = [factura for factura in lote_demo_json if factura["numFactura"] in APTAS + [CON_ERROR]]
    cargar_y_validar(validado, piloto, "Piloto de prueba", "piloto", "2026-07")
    return validado


# --- Indicador: porcentaje de facturas glosadas --------------------------------------
def test_indicador_de_glosas_del_lote_demo(validado):
    datos = validado.get("/api/indicadores/glosas").json()

    assert datos["total"] == {
        "validadas": 12, "glosadas": 7, "porcentaje_glosadas": 58.3,
        "valor_facturado": 664800, "valor_en_riesgo": 260000,
    }
    assert datos["por_periodo"] == [{
        "periodo": "2026-06", "validadas": 12, "glosadas": 7, "porcentaje_glosadas": 58.3,
        "valor_facturado": 664800, "valor_en_riesgo": 260000,
    }]


def test_glosas_por_causal_se_miden_sobre_las_facturas_validadas(validado):
    causales = {fila["grupo"]: fila for fila in validado.get("/api/indicadores/glosas").json()["por_causal"]}

    assert list(causales) == ["FA", "TA", "SO", "AU"]
    # 4 de las 12 facturas incumplen alguna regla de facturación: 33,3 %.
    assert (causales["FA"]["facturas_afectadas"], causales["FA"]["porcentaje_facturas"]) == (4, 33.3)
    assert (causales["TA"]["facturas_afectadas"], causales["TA"]["porcentaje_facturas"]) == (2, 16.7)
    assert (causales["SO"]["facturas_afectadas"], causales["SO"]["porcentaje_facturas"]) == (1, 8.3)
    assert (causales["AU"]["facturas_afectadas"], causales["AU"]["porcentaje_facturas"]) == (1, 8.3)

    reglas = {regla["codigo"]: regla for regla in causales["FA"]["reglas"]}
    assert list(reglas) == ["FA-01", "FA-02", "FA-03", "FA-04"]
    # FA-03 tiene 2 hallazgos pero en una sola factura: cuenta 1 factura.
    assert (reglas["FA-03"]["facturas_afectadas"], reglas["FA-03"]["porcentaje_facturas"]) == (1, 8.3)


def test_indicador_sin_validar_no_divide_por_cero(cliente):
    datos = cliente.get("/api/indicadores/glosas").json()
    assert datos["total"]["validadas"] == 0 and datos["total"]["porcentaje_glosadas"] == 0
    assert datos["por_periodo"][0]["validadas"] == 0
    assert all(fila["porcentaje_facturas"] == 0 for fila in datos["por_causal"])


def test_glosas_por_periodo_y_por_tipo(con_base_y_piloto):
    datos = con_base_y_piloto.get("/api/indicadores/glosas").json()

    periodos = [(fila["periodo"], fila["validadas"], fila["glosadas"], fila["porcentaje_glosadas"])
                for fila in datos["por_periodo"]]
    assert periodos == [("2026-05", 12, 7, 58.3), ("2026-06", 12, 7, 58.3), ("2026-07", 6, 1, 16.7)]
    assert (datos["total"]["validadas"], datos["total"]["glosadas"]) == (30, 15)
    assert datos["total"]["porcentaje_glosadas"] == 50.0

    tipos = {fila["tipo"]: fila for fila in datos["por_tipo"]}
    assert list(tipos) == ["general", "linea_base", "piloto"]
    assert (tipos["linea_base"]["lotes"], tipos["linea_base"]["validadas"], tipos["linea_base"]["glosadas"]) == (1, 12, 7)
    assert (tipos["piloto"]["lotes"], tipos["piloto"]["validadas"], tipos["piloto"]["glosadas"]) == (1, 6, 1)
    assert tipos["piloto"]["porcentaje_glosadas"] == 16.7


def test_el_filtro_aplica_al_indicador_pero_no_a_las_cifras_por_tipo(con_base_y_piloto):
    datos = con_base_y_piloto.get("/api/indicadores/glosas", params={"tipo": "piloto"}).json()

    assert (datos["total"]["validadas"], datos["total"]["glosadas"]) == (6, 1)
    assert [fila["periodo"] for fila in datos["por_periodo"]] == ["2026-07"]
    causales = {fila["grupo"]: fila["facturas_afectadas"] for fila in datos["por_causal"]}
    assert causales == {"FA": 0, "TA": 1, "SO": 0, "AU": 0}
    # Las cifras por tipo siguen completas: la pantalla las necesita para la prueba z.
    assert {fila["tipo"]: fila["validadas"] for fila in datos["por_tipo"]} == {
        "general": 12, "linea_base": 12, "piloto": 6,
    }

    por_periodo = con_base_y_piloto.get("/api/indicadores/glosas", params={"periodo": "2026-05"}).json()
    assert por_periodo["total"]["validadas"] == 12
    assert con_base_y_piloto.get("/api/indicadores/glosas", params={"tipo": "otro"}).status_code == 422


# --- Prueba z -------------------------------------------------------------------------
def test_prueba_z_con_cifras_digitadas(cliente):
    respuesta = cliente.post("/api/indicadores/prueba-z", json={
        "linea_base": {"total_facturas": 100, "facturas_glosadas": 45},
        "piloto": {"total_facturas": 100, "facturas_glosadas": 30},
    })
    assert respuesta.status_code == 200
    r = respuesta.json()

    assert (r["origen_linea_base"], r["origen_piloto"]) == ("manual", "manual")
    assert (r["alfa"], r["hipotesis"]) == (0.05, "reduce")      # valores por defecto del proyecto
    assert r["z"] == pytest.approx(2.1909, abs=1e-4)
    assert r["valor_p"] == pytest.approx(0.0142, abs=1e-4)
    assert r["se_rechaza_h0"] is True
    assert r["interpretacion"].startswith("Con un nivel de significancia de 0,05 se rechaza la hipótesis nula")
    assert r["advertencias"] == []


def test_prueba_z_con_los_lotes_de_linea_base_y_piloto(con_base_y_piloto):
    r = con_base_y_piloto.post("/api/indicadores/prueba-z", json={}).json()

    assert (r["origen_linea_base"], r["origen_piloto"]) == ("lotes", "lotes")
    assert (r["glosadas_linea_base"], r["total_linea_base"]) == (7, 12)
    assert (r["glosadas_piloto"], r["total_piloto"]) == (1, 6)
    esperado = prueba_z_dos_proporciones(7, 12, 1, 6)
    assert r["z"] == pytest.approx(esperado.z)
    assert r["valor_p"] == pytest.approx(esperado.valor_p)
    # Muestras tan pequeñas no cumplen el supuesto de la aproximación normal: se avisa.
    assert r["supuestos_cumplidos"] is False and len(r["advertencias"]) == 1


def test_prueba_z_mezcla_cifras_digitadas_y_lotes(con_base_y_piloto):
    r = con_base_y_piloto.post("/api/indicadores/prueba-z", json={
        "linea_base": {"total_facturas": 200, "facturas_glosadas": 80},
        "hipotesis": "diferente", "alfa": 0.01,
    }).json()
    assert (r["origen_linea_base"], r["origen_piloto"]) == ("manual", "lotes")
    assert (r["total_linea_base"], r["total_piloto"]) == (200, 6)
    assert (r["hipotesis"], r["alfa"]) == ("diferente", 0.01)


def test_prueba_z_sin_lotes_etiquetados_explica_que_falta(validado):
    respuesta = validado.post("/api/indicadores/prueba-z", json={})
    assert respuesta.status_code == 409
    assert "línea base" in respuesta.json()["detail"] and "digite las cifras" in respuesta.json()["detail"]

    # Con la línea base digitada, lo que falta es el piloto.
    respuesta = validado.post("/api/indicadores/prueba-z", json={
        "linea_base": {"total_facturas": 100, "facturas_glosadas": 40},
    })
    assert respuesta.status_code == 409 and "piloto" in respuesta.json()["detail"]


def test_un_lote_sin_validar_no_sirve_para_la_prueba_z(cliente, lote_demo_json):
    cliente.post("/api/lotes", json={"nombre": "Base sin validar", "tipo": "linea_base", "facturas": lote_demo_json})
    respuesta = cliente.post("/api/indicadores/prueba-z", json={
        "piloto": {"total_facturas": 100, "facturas_glosadas": 10},
    })
    assert respuesta.status_code == 409 and "línea base" in respuesta.json()["detail"]


@pytest.mark.parametrize(
    "cuerpo, texto",
    [
        ({"linea_base": {"total_facturas": 10, "facturas_glosadas": 11},
          "piloto": {"total_facturas": 10, "facturas_glosadas": 1}}, "no pueden ser más que el total"),
        ({"linea_base": {"total_facturas": 0, "facturas_glosadas": 0},
          "piloto": {"total_facturas": 10, "facturas_glosadas": 1}}, "debe ser mayor que 0"),
        ({"linea_base": {"total_facturas": 10, "facturas_glosadas": -1},
          "piloto": {"total_facturas": 10, "facturas_glosadas": 1}}, "debe ser mayor o igual a 0"),
        ({"linea_base": {"total_facturas": 10.5, "facturas_glosadas": 1},
          "piloto": {"total_facturas": 10, "facturas_glosadas": 1}}, "número entero"),
        ({"linea_base": {"total_facturas": 10, "facturas_glosadas": 1},
          "piloto": {"total_facturas": 10, "facturas_glosadas": 1}, "alfa": 1.5}, "debe ser menor que 1"),
        ({"linea_base": {"total_facturas": 10, "facturas_glosadas": 1},
          "piloto": {"total_facturas": 10, "facturas_glosadas": 1}, "hipotesis": "aumenta"}, "valor no permitido"),
    ],
)
def test_prueba_z_rechaza_cifras_imposibles_con_mensaje_claro(cliente, cuerpo, texto):
    respuesta = cliente.post("/api/indicadores/prueba-z", json=cuerpo)
    assert respuesta.status_code == 422
    datos = respuesta.json()
    assert texto in (datos["detail"] + " " + " ".join(datos.get("errores", [])))


def test_los_endpoints_de_linea_base_estan_documentados(cliente):
    rutas = cliente.get("/openapi.json").json()["paths"]
    assert "/api/indicadores/glosas" in rutas and "/api/indicadores/prueba-z" in rutas
