"""Protecciones agregadas en la revisión final (Fase 10).

El sistema no tiene inicio de sesión, así que estas pruebas cuidan tres cosas:
1. Que otra página abierta en el mismo navegador no pueda modificar datos.
2. Que no se reciban peticiones sin tamaño declarado ni datos que la base de datos no puede guardar.
3. Que los errores salgan en español y sin detalles técnicos.
"""
import copy

import pytest
from sqlalchemy.exc import OperationalError

from app.constantes import VALOR_MAXIMO
from app.rutas.comunes import ID_MAXIMO

MENSAJE_OTRO_SITIO = "Solo se aceptan cambios hechos desde las páginas del sistema."


# --- 1. Cambios que vienen de otro sitio ------------------------------------------
@pytest.mark.parametrize("cabeceras", [
    {"Sec-Fetch-Site": "cross-site"},                      # navegador actual, otra página
    {"Sec-Fetch-Site": "same-site"},                       # mismo equipo pero otro puerto: también es otra página
    {"Origin": "https://sitio-malicioso.example"},         # navegador antiguo: solo envía Origin
    {"Origin": "null"},                                    # archivo local o marco aislado
    {"Sec-Fetch-Site": "cross-site", "Origin": "http://testserver"},
])
def test_un_cambio_pedido_desde_otro_sitio_se_rechaza(cliente, cabeceras):
    respuesta = cliente.post("/api/reglas/SO-01/desactivar", headers=cabeceras)
    assert respuesta.status_code == 403
    assert respuesta.json() == {"detail": MENSAJE_OTRO_SITIO}
    # La regla sigue activa: la petición no llegó a ejecutarse.
    reglas = {regla["codigo"]: regla["activa"] for regla in cliente.get("/api/reglas").json()}
    assert reglas["SO-01"] is True


def test_tampoco_se_puede_eliminar_ni_editar_desde_otro_sitio(cliente):
    otro_sitio = {"Origin": "https://sitio-malicioso.example"}
    assert cliente.delete("/api/lotes/1", headers=otro_sitio).status_code == 403
    assert cliente.put("/api/eps/EPS-ALFA", json={"nombre": "Otro nombre"}, headers=otro_sitio).status_code == 403
    assert cliente.get("/api/lotes/1").status_code == 200


@pytest.mark.parametrize("cabeceras", [
    {},                                                    # curl, scripts y pruebas: sin cabeceras de navegador
    {"Sec-Fetch-Site": "same-origin"},                     # las páginas del propio sistema
    {"Sec-Fetch-Site": "none"},                            # la persona escribió la dirección
    {"Origin": "http://testserver"},                       # navegador antiguo, desde el propio sistema
    # Detrás de un proxy la dirección puede no coincidir; manda lo que dice el navegador.
    {"Sec-Fetch-Site": "same-origin", "Origin": "https://auditaglosas.hospital.example"},
])
def test_los_cambios_hechos_desde_el_propio_sistema_se_aceptan(cliente, cabeceras):
    respuesta = cliente.post("/api/reglas/SO-01/desactivar", headers=cabeceras)
    assert respuesta.status_code == 200 and respuesta.json()["activa"] is False


def test_consultar_desde_otro_sitio_no_se_bloquea(cliente):
    """Solo se protegen los cambios. Las consultas no modifican nada (y el navegador no deja leerlas)."""
    respuesta = cliente.get("/api/reglas", headers={"Sec-Fetch-Site": "cross-site"})
    assert respuesta.status_code == 200


def test_el_rechazo_tambien_lleva_las_cabeceras_de_seguridad(cliente):
    respuesta = cliente.delete("/api/lotes/1", headers={"Sec-Fetch-Site": "cross-site"})
    assert respuesta.status_code == 403
    assert respuesta.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" in respuesta.headers


# --- 2. Tamaño de la petición y datos que no se pueden guardar ----------------------
def test_una_peticion_enviada_por_trozos_debe_decir_su_tamano(cliente):
    def trozos():
        yield b'{"nombre": "Lote", '
        yield b'"facturas": []}'

    respuesta = cliente.post("/api/lotes", content=trozos(), headers={"Content-Type": "application/json"})
    assert respuesta.status_code == 411
    assert respuesta.json() == {"detail": "La petición debe indicar su tamaño (Content-Length)."}


@pytest.mark.parametrize("direccion", [
    f"/api/lotes/{ID_MAXIMO + 1}",
    f"/api/lotes/{ID_MAXIMO + 1}/resultados",
    f"/api/facturas/{ID_MAXIMO + 1}",
    f"/api/reportes/por-eps?lote_id={ID_MAXIMO + 1}",
    "/api/lotes/0",
    "/api/facturas/99999999999999999999999999",
])
def test_un_identificador_imposible_se_rechaza_sin_consultar_la_base(cliente, direccion):
    respuesta = cliente.get(direccion)
    assert respuesta.status_code == 422
    assert respuesta.json()["detail"] == "Los datos enviados no tienen la estructura esperada."


def test_el_mayor_identificador_posible_solo_dice_que_no_existe(cliente):
    assert cliente.get(f"/api/lotes/{ID_MAXIMO}").status_code == 404
    assert cliente.post(f"/api/lotes/{ID_MAXIMO}/validar").status_code == 404
    assert cliente.delete(f"/api/lotes/{ID_MAXIMO}").status_code == 404


def _cargar(cliente, factura):
    return cliente.post("/api/lotes", json={"nombre": "Lote de prueba", "facturas": [factura]})


def _primera_consulta(factura):
    return factura["rips"]["usuarios"][0]["servicios"]["consultas"][0]


def test_textos_mas_largos_que_su_columna_se_rechazan(cliente, lote_demo_json):
    """PostgreSQL no guarda un texto más largo que la columna; se avisa antes, en español."""
    factura = copy.deepcopy(lote_demo_json[0])
    factura["rips"]["numFactura"] = "F" * 41
    _primera_consulta(factura)["numAutorizacion"] = "A" * 41
    respuesta = _cargar(cliente, factura)
    assert respuesta.status_code == 422
    errores = respuesta.json()["errores"]
    assert len(errores) == 2
    assert all("es demasiado largo (máximo 40 caracteres)" in error for error in errores)
    assert any("rips → numFactura" in error for error in errores)
    assert any("numAutorizacion" in error for error in errores)


def test_nombre_de_medicamento_demasiado_largo_se_rechaza(cliente, lote_demo_json):
    con_medicamento = next(
        factura for factura in lote_demo_json
        if factura["rips"]["usuarios"][0]["servicios"].get("medicamentos")
    )
    factura = copy.deepcopy(con_medicamento)
    factura["rips"]["usuarios"][0]["servicios"]["medicamentos"][0]["nomTecnologiaSalud"] = "M" * 201
    respuesta = _cargar(cliente, factura)
    assert respuesta.status_code == 422
    assert "nomTecnologiaSalud: es demasiado largo (máximo 200 caracteres)." in respuesta.json()["errores"][0]


def test_los_datos_opcionales_pueden_venir_vacios_o_en_el_limite(cliente, lote_demo_json):
    factura = copy.deepcopy(lote_demo_json[0])
    factura["rips"]["numFactura"] = None
    _primera_consulta(factura)["numAutorizacion"] = "A" * 40
    assert _cargar(cliente, factura).status_code == 201


def test_un_texto_con_el_caracter_nulo_se_rechaza(cliente, lote_demo_json):
    factura = copy.deepcopy(lote_demo_json[0])
    factura["soportes"] = ["Historia\x00clínica"]
    _primera_consulta(factura)["numAutorizacion"] = "AUT\x00-1"
    respuesta = _cargar(cliente, factura)
    assert respuesta.status_code == 422
    errores = respuesta.json()["errores"]
    assert errores and all(error.endswith("contiene un carácter no permitido.") for error in errores)
    # El mensaje no repite el dato recibido.
    assert "AUT" not in respuesta.text and "Historia" not in respuesta.text


def test_el_valor_de_un_hallazgo_nunca_supera_el_maximo_que_cabe_en_la_base(cliente, lote_demo_json):
    """Dos servicios con el valor máximo suman más de lo que cabe en la columna: el hallazgo se topa."""
    factura = copy.deepcopy(lote_demo_json[0])
    consultas = factura["rips"]["usuarios"][0]["servicios"]["consultas"]
    consultas.append({"codConsulta": "890201", "vrServicio": VALOR_MAXIMO})
    consultas.append({"codConsulta": "890301", "vrServicio": VALOR_MAXIMO})
    lote = _cargar(cliente, factura).json()
    resultados = cliente.post(f"/api/lotes/{lote['id']}/validar")
    assert resultados.status_code == 200

    id_factura = cliente.get(f"/api/lotes/{lote['id']}/resultados").json()["facturas"][0]["id"]
    detalle = cliente.get(f"/api/facturas/{id_factura}").json()
    valores = {hallazgo["regla"]: hallazgo["valor_en_riesgo"] for hallazgo in detalle["hallazgos"]}
    assert valores["FA-02"] == VALOR_MAXIMO
    assert all(valor <= VALOR_MAXIMO for valor in valores.values())
    # El riesgo de la factura sigue siendo, como mucho, lo que vale la factura.
    assert detalle["valor_en_riesgo"] <= detalle["valor_total"]


# --- 3. Errores en español y sin detalles técnicos ---------------------------------
def test_una_direccion_que_no_existe_responde_en_espanol(cliente):
    respuesta = cliente.get("/api/no-existe")
    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "No existe esa dirección."}
    assert cliente.get("/static/js/no-existe.js").json() == {"detail": "No existe esa dirección."}


def test_una_operacion_no_permitida_responde_en_espanol(cliente):
    respuesta = cliente.delete("/api/salud")
    assert respuesta.status_code == 405
    assert respuesta.json() == {"detail": "Esa operación no está permitida en esta dirección."}
    assert "GET" in respuesta.headers["allow"]


def test_los_mensajes_propios_no_cambian(cliente):
    respuesta = cliente.get("/api/lotes/9999")
    assert respuesta.status_code == 404
    assert "lote" in respuesta.json()["detail"].lower()


def test_si_la_base_de_datos_falla_no_se_muestran_detalles_tecnicos(cliente, monkeypatch):
    def fallar(_sesion):
        raise OperationalError("SELECT * FROM reglas", {}, Exception("contraseña del servidor db-interno"))

    monkeypatch.setattr("app.rutas.reglas.listar_reglas", fallar)
    respuesta = cliente.get("/api/reglas")
    assert respuesta.status_code == 500
    assert respuesta.json()["detail"].startswith("No se pudo completar la operación en la base de datos.")
    assert "SELECT" not in respuesta.text and "db-interno" not in respuesta.text
