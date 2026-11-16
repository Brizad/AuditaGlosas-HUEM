"""API de contratos: EPS, tarifas, autorizaciones y catálogo de servicios (HU-02, HU-04)."""


def estado_de(cliente, num_factura: str) -> dict:
    facturas = cliente.get("/api/lotes/1/resultados").json()["facturas"]
    return next(factura for factura in facturas if factura["num_factura"] == num_factura)


# --- EPS -----------------------------------------------------------------------
def test_listar_eps_con_sus_totales(cliente):
    eps = {fila["codigo"]: fila for fila in cliente.get("/api/eps").json()}
    assert list(eps) == ["EPS-ALFA", "EPS-BETA", "EPS-GAMMA"]
    alfa = eps["EPS-ALFA"]
    assert (alfa["nombre"], alfa["total_tarifas"], alfa["total_autorizaciones"], alfa["total_facturas"]) == (
        "EPS Alfa", 7, 1, 5,
    )


def test_crear_consultar_editar_y_eliminar_una_eps(cliente):
    creada = cliente.post("/api/eps", json={"codigo": "eps-delta", "nombre": "EPS Delta"})
    assert creada.status_code == 201
    assert creada.json() == {
        "codigo": "EPS-DELTA", "nombre": "EPS Delta",
        "total_tarifas": 0, "total_autorizaciones": 0, "total_facturas": 0,
    }

    detalle = cliente.get("/api/eps/EPS-DELTA").json()
    assert detalle["tarifas"] == [] and detalle["autorizaciones"] == []

    editada = cliente.put("/api/eps/EPS-DELTA", json={"nombre": "EPS Delta Salud"})
    assert editada.json()["nombre"] == "EPS Delta Salud"

    assert cliente.delete("/api/eps/EPS-DELTA").status_code == 204
    assert cliente.get("/api/eps/EPS-DELTA").status_code == 404


def test_no_se_puede_crear_una_eps_repetida_ni_con_codigo_invalido(cliente):
    repetida = cliente.post("/api/eps", json={"codigo": "EPS-ALFA", "nombre": "Otra Alfa"})
    assert repetida.status_code == 409 and "Ya existe" in repetida.json()["detail"]

    invalida = cliente.post("/api/eps", json={"codigo": "EPS con espacios", "nombre": "X"})
    assert invalida.status_code == 422
    assert "codigo: no tiene el formato esperado." in invalida.json()["errores"]


def test_no_se_puede_eliminar_una_eps_con_facturas(cliente):
    respuesta = cliente.delete("/api/eps/EPS-ALFA")
    assert respuesta.status_code == 409 and "5 factura(s)" in respuesta.json()["detail"]
    assert cliente.get("/api/eps/EPS-ALFA").status_code == 200


def test_eps_que_no_existe(cliente):
    for respuesta in (
        cliente.get("/api/eps/EPS-NADA"), cliente.put("/api/eps/EPS-NADA", json={"nombre": "Nada"}),
        cliente.delete("/api/eps/EPS-NADA"), cliente.get("/api/eps/EPS-NADA/tarifas"),
    ):
        assert respuesta.status_code == 404


# --- Tarifas ---------------------------------------------------------------------
def test_detalle_de_eps_trae_tarifas_con_descripcion_y_autorizacion(cliente):
    tarifas = {t["codigo_servicio"]: t for t in cliente.get("/api/eps/EPS-BETA").json()["tarifas"]}
    assert len(tarifas) == 6
    assert tarifas["871121"] == {
        "codigo_servicio": "871121", "descripcion": "Radiografía de tórax",
        "valor": 65000, "requiere_autorizacion": True,
    }
    assert tarifas["890201"]["requiere_autorizacion"] is False


def test_crear_editar_y_eliminar_una_tarifa(cliente):
    creada = cliente.post("/api/eps/EPS-GAMMA/tarifas", json={"codigo_servicio": "890301", "valor": 31000})
    assert creada.status_code == 201 and creada.json()["descripcion"] == "Consulta de control por medicina general"

    repetida = cliente.post("/api/eps/EPS-GAMMA/tarifas", json={"codigo_servicio": "890301", "valor": 1})
    assert repetida.status_code == 409

    editada = cliente.put("/api/eps/EPS-GAMMA/tarifas/890301", json={"valor": 32000})
    assert editada.json()["valor"] == 32000
    assert len(cliente.get("/api/eps/EPS-GAMMA/tarifas").json()) == 7

    assert cliente.delete("/api/eps/EPS-GAMMA/tarifas/890301").status_code == 204
    assert cliente.delete("/api/eps/EPS-GAMMA/tarifas/890301").status_code == 404
    assert cliente.put("/api/eps/EPS-GAMMA/tarifas/890301", json={"valor": 1}).status_code == 404


def test_tarifa_con_valor_negativo_se_rechaza(cliente):
    respuesta = cliente.post("/api/eps/EPS-GAMMA/tarifas", json={"codigo_servicio": "890301", "valor": -5})
    assert respuesta.status_code == 422
    assert respuesta.json()["errores"] == ["valor: debe ser mayor o igual a 0."]


def test_cambiar_una_tarifa_cambia_el_resultado_de_la_validacion(cliente):
    """FV-1005 cobra 41.000 a EPS Gamma (pactado 36.000). Si se pacta 41.000, queda apta."""
    cliente.post("/api/lotes/1/validar")
    assert estado_de(cliente, "FV-1005")["reglas"] == ["TA-01"]

    cliente.put("/api/eps/EPS-GAMMA/tarifas/890201", json={"valor": 41000})
    cliente.post("/api/lotes/1/validar")
    assert estado_de(cliente, "FV-1005")["estado"] == "apta"
    # La otra factura de Gamma con esa consulta (FV-1010, cobrada a 36.000) ahora incumple.
    assert estado_de(cliente, "FV-1010")["reglas"] == ["TA-01"]


def test_agregar_la_tarifa_que_faltaba_corrige_ta02(cliente):
    cliente.post("/api/lotes/1/validar")
    assert estado_de(cliente, "FV-1006")["reglas"] == ["TA-02"]
    cliente.post("/api/eps/EPS-GAMMA/tarifas", json={"codigo_servicio": "890301", "valor": 32000})
    cliente.post("/api/lotes/1/validar")
    assert estado_de(cliente, "FV-1006")["estado"] == "apta"


# --- Autorizaciones ---------------------------------------------------------------
def test_listar_agregar_y_quitar_autorizaciones(cliente):
    assert [a["codigo_servicio"] for a in cliente.get("/api/eps/EPS-BETA/autorizaciones").json()] == [
        "871121", "902210",
    ]
    creada = cliente.post("/api/eps/EPS-GAMMA/autorizaciones", json={"codigo_servicio": "871121"})
    assert creada.status_code == 201 and creada.json()["descripcion"] == "Radiografía de tórax"
    assert cliente.post("/api/eps/EPS-GAMMA/autorizaciones", json={"codigo_servicio": "871121"}).status_code == 409

    assert cliente.delete("/api/eps/EPS-GAMMA/autorizaciones/871121").status_code == 204
    assert cliente.delete("/api/eps/EPS-GAMMA/autorizaciones/871121").status_code == 404


def test_exigir_autorizacion_cambia_el_resultado_de_la_validacion(cliente):
    """FV-1010 (EPS Gamma, radiografía sin autorización) está apta hasta que Gamma exija autorizarla."""
    cliente.post("/api/lotes/1/validar")
    assert estado_de(cliente, "FV-1010")["estado"] == "apta"
    cliente.post("/api/eps/EPS-GAMMA/autorizaciones", json={"codigo_servicio": "871121"})
    cliente.post("/api/lotes/1/validar")
    assert estado_de(cliente, "FV-1010")["reglas"] == ["AU-01"]


# --- Catálogo de servicios ----------------------------------------------------------
def test_ver_catalogo(cliente):
    catalogo = cliente.get("/api/catalogo").json()
    assert len(catalogo["servicios"]) == 7
    assert catalogo["servicios"][0] == {
        "codigo": "871121", "descripcion": "Radiografía de tórax", "tipo": "imagen",
    }
    assert catalogo["soportes_requeridos"] == {
        "laboratorio": ["Resultado de laboratorio"],
        "imagen": ["Lectura o informe del examen"],
        "medicamento": ["Fórmula médica"],
    }


def test_crear_actualizar_y_quitar_un_servicio_del_catalogo(cliente):
    nuevo = cliente.put("/api/catalogo/servicios/881302", json={"descripcion": "Ecografía abdominal", "tipo": "Imagen"})
    assert nuevo.status_code == 200
    assert nuevo.json() == {"codigo": "881302", "descripcion": "Ecografía abdominal", "tipo": "imagen"}

    cambiado = cliente.put(
        "/api/catalogo/servicios/881302", json={"descripcion": "Ecografía de abdomen total", "tipo": "imagen"},
    )
    assert cambiado.json()["descripcion"] == "Ecografía de abdomen total"
    assert len(cliente.get("/api/catalogo").json()["servicios"]) == 8

    assert cliente.delete("/api/catalogo/servicios/881302").status_code == 204
    assert cliente.delete("/api/catalogo/servicios/881302").status_code == 404


def test_servicio_de_catalogo_con_datos_invalidos(cliente):
    assert cliente.put("/api/catalogo/servicios/881302", json={"descripcion": "", "tipo": "imagen"}).status_code == 422
    assert cliente.put("/api/catalogo/servicios/881302", json={"descripcion": "Eco", "tipo": "1"}).status_code == 422
