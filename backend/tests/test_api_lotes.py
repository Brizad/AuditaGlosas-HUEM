"""API de lotes y facturas: cargar, validar, consultar y eliminar (HU-01, HU-05)."""
import copy

DOCUMENTOS = [f"90000001{n:02d}" for n in range(1, 13)]


def cargar(cliente, facturas, nombre="Lote de prueba", **extra):
    return cliente.post("/api/lotes", json={"nombre": nombre, "facturas": facturas, **extra})


def test_salud(cliente):
    assert cliente.get("/api/salud").json() == {"estado": "ok", "sistema": "AuditaGlosas HUEM"}


def test_la_documentacion_automatica_esta_disponible(cliente):
    assert cliente.get("/docs").status_code == 200
    rutas = cliente.get("/openapi.json").json()["paths"]
    assert "/api/lotes" in rutas and "/api/reportes/exportar.csv" in rutas


# --- Prueba completa con el lote demo ------------------------------------------
def test_flujo_completo_con_el_lote_demo_da_lo_mismo_que_el_prototipo(cliente, lote_demo_json):
    """Cargar -> validar -> consultar: 12 facturas, 5 aptas, 7 con inconsistencias, $260.000 en riesgo."""
    respuesta = cargar(cliente, lote_demo_json, nombre="Demo por API")
    assert respuesta.status_code == 201
    lote = respuesta.json()
    assert lote["estado"] == "cargado" and lote["periodo"] == "2026-06" and lote["tipo"] == "general"
    assert lote["resumen"]["total_facturas"] == 12 and lote["resumen"]["sin_validar"] == 12

    validado = cliente.post(f"/api/lotes/{lote['id']}/validar").json()
    assert validado["estado"] == "validado" and validado["fecha_validacion"]
    resumen = validado["resumen"]
    assert resumen["total_facturas"] == 12
    assert resumen["aptas"] == 5
    assert resumen["con_inconsistencias"] == 7
    assert resumen["sin_validar"] == 0
    assert resumen["valor_en_riesgo"] == 260000
    assert resumen["porcentaje_aptas"] == 41.7 and resumen["porcentaje_con_inconsistencias"] == 58.3

    resultados = cliente.get(f"/api/lotes/{lote['id']}/resultados").json()
    por_numero = {factura["num_factura"]: factura for factura in resultados["facturas"]}
    assert len(por_numero) == 12
    assert por_numero["FV-1001"]["estado"] == "apta" and por_numero["FV-1001"]["total_hallazgos"] == 0
    assert por_numero["FV-1003"]["reglas"] == ["AU-01", "SO-01"]
    assert por_numero["FV-1003"]["valor_en_riesgo"] == 106000
    assert por_numero["FV-1007"]["total_hallazgos"] == 2 and por_numero["FV-1007"]["reglas"] == ["FA-03"]
    assert sum(factura["valor_en_riesgo"] for factura in resultados["facturas"]) == 260000


def test_resultados_filtrados_por_estado(cliente):
    cliente.post("/api/lotes/1/validar")
    assert len(cliente.get("/api/lotes/1/resultados", params={"estado": "apta"}).json()["facturas"]) == 5
    con_problemas = cliente.get("/api/lotes/1/resultados", params={"estado": "con_inconsistencias"}).json()
    assert len(con_problemas["facturas"]) == 7
    assert cliente.get("/api/lotes/1/resultados", params={"estado": "otro"}).status_code == 422


def test_detalle_de_factura_con_hallazgos(cliente):
    cliente.post("/api/lotes/1/validar")
    facturas = cliente.get("/api/lotes/1/resultados").json()["facturas"]
    id_factura = next(f["id"] for f in facturas if f["num_factura"] == "FV-1003")

    detalle = cliente.get(f"/api/facturas/{id_factura}").json()
    assert detalle["eps_nombre"] == "EPS Beta" and detalle["valor_total"] == 106000
    assert detalle["estado"] == "con_inconsistencias" and detalle["valor_en_riesgo"] == 106000
    assert [item["codigo"] for item in detalle["items"]] == ["890201", "871121"]
    assert detalle["items"][1]["descripcion"] == "Radiografía de tórax"
    assert [servicio["clase"] for servicio in detalle["servicios"]] == ["consulta", "procedimiento"]
    assert sorted(h["regla"] for h in detalle["hallazgos"]) == ["AU-01", "SO-01"]
    assert {h["nombre_grupo"] for h in detalle["hallazgos"]} == {"Soportes", "Autorizaciones"}
    assert all(h["valor_en_riesgo"] == 65000 for h in detalle["hallazgos"])


def test_factura_que_no_existe(cliente):
    respuesta = cliente.get("/api/facturas/9999")
    assert respuesta.status_code == 404 and "No existe" in respuesta.json()["detail"]


def test_ninguna_respuesta_devuelve_el_documento_del_paciente(cliente, lote_demo_json):
    lote = cargar(cliente, lote_demo_json).json()
    cliente.post(f"/api/lotes/{lote['id']}/validar")
    textos = [cliente.get(f"/api/lotes/{lote['id']}/resultados").text, cliente.get("/api/reportes/exportar.csv").text]
    textos += [cliente.get(f"/api/facturas/{n}").text for n in range(1, 25)]
    for texto in textos:
        assert not any(documento in texto for documento in DOCUMENTOS)


# --- Errores de estructura -------------------------------------------------------
def test_campo_obligatorio_faltante_se_explica_en_espanol(cliente, lote_demo_json):
    facturas = copy.deepcopy(lote_demo_json)
    del facturas[3]["valorTotal"]
    respuesta = cargar(cliente, facturas)
    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert "estructura" in cuerpo["detail"]
    assert cuerpo["errores"] == ["Factura n.º 4 (FV-1004) → valorTotal: falta este campo obligatorio."]


def test_tipo_de_dato_equivocado_indica_la_ubicacion_exacta(cliente, lote_demo_json):
    facturas = copy.deepcopy(lote_demo_json)
    facturas[1]["rips"]["usuarios"][0]["servicios"]["procedimientos"][0]["vrServicio"] = "nueve mil"
    facturas[1]["items"][0]["cantidad"] = 0
    errores = cargar(cliente, facturas).json()["errores"]
    assert "Factura n.º 2 (FV-1002) → items[1] → cantidad: debe ser mayor que 0." in errores
    assert (
        "Factura n.º 2 (FV-1002) → rips → usuarios[1] → servicios → procedimientos[1] → vrServicio: "
        "debe ser un número."
    ) in errores


def test_los_errores_no_repiten_los_datos_recibidos(cliente, lote_demo_json):
    facturas = copy.deepcopy(lote_demo_json)
    facturas[0]["rips"]["usuarios"] = "9000000101"       # tipo equivocado con un documento adentro
    respuesta = cargar(cliente, facturas)
    assert respuesta.status_code == 422 and "9000000101" not in respuesta.text


def test_lote_sin_facturas_o_sin_nombre_se_rechaza(cliente):
    assert cargar(cliente, []).json()["errores"] == ["facturas: debe tener al menos 1 elemento(s)."]
    errores = cliente.post("/api/lotes", json={"facturas": []}).json()["errores"]
    assert "nombre: falta este campo obligatorio." in errores


def test_tipo_y_periodo_invalidos_se_rechazan(cliente, lote_demo_json):
    errores = cargar(cliente, lote_demo_json, tipo="experimento", periodo="junio").json()["errores"]
    assert any(error.startswith("tipo: valor no permitido") for error in errores)
    assert "periodo: no tiene el formato esperado." in errores


def test_cuerpo_que_no_es_json(cliente):
    respuesta = cliente.post("/api/lotes", content=b"{esto no es json", headers={"Content-Type": "application/json"})
    assert respuesta.status_code == 422
    assert any("JSON válido" in error for error in respuesta.json()["errores"])


def test_factura_repetida_y_eps_desconocida(cliente, lote_demo_json):
    facturas = copy.deepcopy(lote_demo_json[:2])
    facturas[1]["numFactura"] = "FV-1001"
    facturas[1]["eps"] = "EPS-OMEGA"
    respuesta = cargar(cliente, facturas)
    assert respuesta.status_code == 422
    errores = respuesta.json()["errores"]
    assert any("repetida" in error for error in errores)
    assert any("EPS-OMEGA" in error and "no está registrada" in error for error in errores)
    assert len(cliente.get("/api/lotes").json()) == 1          # no se guardó nada


def test_un_error_de_contenido_no_impide_cargar(cliente, lote_demo_json):
    """Código mal formado y RIPS de otra factura son hallazgos, no errores de estructura."""
    respuesta = cargar(cliente, [lote_demo_json[10], lote_demo_json[11]])
    assert respuesta.status_code == 201
    validado = cliente.post(f"/api/lotes/{respuesta.json()['id']}/validar").json()
    assert validado["resumen"]["con_inconsistencias"] == 2


def test_peticion_demasiado_grande(cliente):
    respuesta = cliente.post(
        "/api/lotes", content=b" " * (20 * 1024 * 1024 + 1), headers={"Content-Type": "application/json"},
    )
    assert respuesta.status_code == 413


# --- Listar, consultar y eliminar -------------------------------------------------
def test_listar_lotes_con_filtros(cliente, lote_demo_json):
    cargar(cliente, lote_demo_json[:3], nombre="Antes", tipo="linea_base", periodo="2026-05")
    cargar(cliente, lote_demo_json[:3], nombre="Después", tipo="piloto", periodo="2026-07")

    todos = cliente.get("/api/lotes").json()
    assert [lote["nombre"] for lote in todos] == ["Después", "Antes", "Lote de demostración (Sprint 0)"]
    assert [lote["nombre"] for lote in cliente.get("/api/lotes", params={"tipo": "piloto"}).json()] == ["Después"]
    assert [lote["nombre"] for lote in cliente.get("/api/lotes", params={"periodo": "2026-05"}).json()] == ["Antes"]
    assert cliente.get("/api/lotes", params={"periodo": "2026-13"}).status_code == 422


def test_consultar_y_eliminar_un_lote(cliente):
    assert cliente.get("/api/lotes/1").json()["resumen"]["total_facturas"] == 12
    assert cliente.delete("/api/lotes/1").status_code == 204
    assert cliente.get("/api/lotes/1").status_code == 404
    assert cliente.get("/api/lotes").json() == []


def test_lote_que_no_existe(cliente):
    for respuesta in (
        cliente.get("/api/lotes/77"), cliente.delete("/api/lotes/77"),
        cliente.post("/api/lotes/77/validar"), cliente.get("/api/lotes/77/resultados"),
    ):
        assert respuesta.status_code == 404 and respuesta.json()["detail"] == "No existe el lote 77."
