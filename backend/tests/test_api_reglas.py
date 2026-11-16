"""API del catálogo de reglas: listar, activar y desactivar (HU-06)."""


def test_listar_las_ocho_reglas_con_su_grupo(cliente):
    reglas = cliente.get("/api/reglas").json()
    assert [regla["codigo"] for regla in reglas] == [
        "FA-01", "FA-02", "FA-03", "FA-04", "TA-01", "TA-02", "SO-01", "AU-01",
    ]
    assert all(regla["activa"] for regla in reglas)
    primera = reglas[0]
    assert primera["grupo"] == "FA" and primera["nombre_grupo"] == "Facturación y codificación"
    assert primera["nombre"] and primera["descripcion"]


def test_desactivar_y_activar(cliente):
    respuesta = cliente.post("/api/reglas/SO-01/desactivar")
    assert respuesta.status_code == 200 and respuesta.json()["activa"] is False
    estados = {regla["codigo"]: regla["activa"] for regla in cliente.get("/api/reglas").json()}
    assert estados["SO-01"] is False and estados["AU-01"] is True

    assert cliente.post("/api/reglas/SO-01/activar").json()["activa"] is True


def test_el_codigo_se_acepta_en_minusculas(cliente):
    assert cliente.post("/api/reglas/ta-02/desactivar").json()["codigo"] == "TA-02"


def test_regla_que_no_existe(cliente):
    for accion in ("activar", "desactivar"):
        respuesta = cliente.post(f"/api/reglas/ZZ-99/{accion}")
        assert respuesta.status_code == 404 and respuesta.json()["detail"] == "No existe la regla ZZ-99."


def test_desactivar_una_regla_y_revalidar_cambia_el_resultado(cliente):
    """Sin SO-01 ni AU-01, la factura FV-1003 queda apta: 6 aptas y $154.000 en riesgo."""
    assert cliente.post("/api/lotes/1/validar").json()["resumen"]["valor_en_riesgo"] == 260000

    cliente.post("/api/reglas/SO-01/desactivar")
    cliente.post("/api/reglas/AU-01/desactivar")
    # Mientras no se valide de nuevo, el resultado guardado no cambia.
    assert cliente.get("/api/lotes/1").json()["resumen"]["valor_en_riesgo"] == 260000

    resumen = cliente.post("/api/lotes/1/validar").json()["resumen"]
    assert (resumen["aptas"], resumen["con_inconsistencias"], resumen["valor_en_riesgo"]) == (6, 6, 154000)

    cliente.post("/api/reglas/SO-01/activar")
    cliente.post("/api/reglas/AU-01/activar")
    resumen = cliente.post("/api/lotes/1/validar").json()["resumen"]
    assert (resumen["aptas"], resumen["con_inconsistencias"], resumen["valor_en_riesgo"]) == (5, 7, 260000)
