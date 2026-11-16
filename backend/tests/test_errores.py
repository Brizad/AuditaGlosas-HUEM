"""Traducción de los errores de estructura a mensajes claros en español (Fase 8)."""
from app.errores import MAXIMO_ERRORES, mensaje_legible, traducir_errores, ubicacion_legible


def test_ubicacion_con_el_numero_de_la_factura():
    cuerpo = {"facturas": [{}, {}, {}, {"numFactura": "FV-1004"}]}
    ubicacion = ("body", "facturas", 3, "rips", "numFactura")
    assert ubicacion_legible(ubicacion, cuerpo) == "Factura n.º 4 (FV-1004) → rips → numFactura"


def test_ubicacion_dentro_de_listas_cuenta_desde_uno():
    ubicacion = ("body", "facturas", 0, "rips", "usuarios", 0, "servicios", "consultas", 1, "vrServicio")
    assert ubicacion_legible(ubicacion) == "Factura n.º 1 → rips → usuarios[1] → servicios → consultas[2] → vrServicio"


def test_ubicacion_cuando_el_cuerpo_no_tiene_la_forma_esperada():
    """Si lo enviado no es un lote (o la factura no es un objeto), no se intenta leer el número."""
    ubicacion = ("body", "facturas", 0, "valorTotal")
    for cuerpo in (None, [], "texto", {"facturas": "no es lista"}, {"facturas": ["no es objeto"]}, {"facturas": []}):
        assert ubicacion_legible(ubicacion, cuerpo) == "Factura n.º 1 → valorTotal"


def test_el_numero_de_factura_solo_se_muestra_si_es_texto_o_numero():
    ubicacion = ("body", "facturas", 0, "eps")
    assert ubicacion_legible(ubicacion, {"facturas": [{"numFactura": 1004}]}) == "Factura n.º 1 (1004) → eps"
    assert ubicacion_legible(ubicacion, {"facturas": [{"numFactura": {"a": 1}}]}) == "Factura n.º 1 → eps"
    assert ubicacion_legible(ubicacion, {"facturas": [{"numFactura": True}]}) == "Factura n.º 1 → eps"
    # Un número de factura larguísimo se recorta para no devolver textos enormes.
    largo = ubicacion_legible(ubicacion, {"facturas": [{"numFactura": "X" * 500}]})
    assert largo == f"Factura n.º 1 ({'X' * 40}) → eps"


def test_ubicacion_vacia():
    assert ubicacion_legible(("body",)) == "Archivo"
    assert ubicacion_legible(()) == "Archivo"


def test_mensajes_traducidos_con_su_limite():
    assert mensaje_legible({"type": "missing"}) == "falta este campo obligatorio"
    assert mensaje_legible({"type": "greater_than", "ctx": {"gt": 0.0}}) == "debe ser mayor que 0"
    assert mensaje_legible({"type": "less_than_equal", "ctx": {"le": 5000}}) == "debe ser menor o igual a 5000"
    assert mensaje_legible({"type": "int_from_float"}) == "debe ser un número entero (sin decimales)"


def test_mensaje_de_un_tipo_desconocido_o_sin_contexto():
    assert mensaje_legible({"type": "tipo_nuevo", "msg": "Mensaje original"}) == "Mensaje original"
    assert mensaje_legible({}) == "valor no válido"
    # Si falta el dato para completar la plantilla, se devuelve la plantilla tal cual (no se cae).
    assert mensaje_legible({"type": "greater_than"}) == "debe ser mayor que {gt}"


def test_se_muestran_como_maximo_cincuenta_errores():
    errores = [{"type": "missing", "loc": ("body", "facturas", n, "eps")} for n in range(MAXIMO_ERRORES + 10)]
    mensajes = traducir_errores(errores)
    assert len(mensajes) == MAXIMO_ERRORES + 1
    assert mensajes[0] == "Factura n.º 1 → eps: falta este campo obligatorio."
    assert mensajes[-1] == "… y 10 errores más."


def test_un_lote_con_muchos_errores_responde_con_la_lista_recortada(cliente):
    facturas = [{"numFactura": f"F-{n}"} for n in range(40)]      # a cada una le faltan 4 campos
    respuesta = cliente.post("/api/lotes", json={"nombre": "Lote dañado", "facturas": facturas})
    assert respuesta.status_code == 422
    errores = respuesta.json()["errores"]
    assert len(errores) == MAXIMO_ERRORES + 1 and errores[-1].startswith("… y ")
    assert errores[0].startswith("Factura n.º 1 (F-0) → ")
