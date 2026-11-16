"""AU-01 · Número de autorización cuando la EPS lo exige (HU-02)."""
from fabricas import consulta, contexto, procedimiento

from app.reglas import obtener_regla

REGLA = obtener_regla("AU-01")
CON_LECTURA = ["Lectura o informe del examen"]


def test_datos_de_la_regla():
    assert (REGLA.codigo, REGLA.grupo) == ("AU-01", "AU")
    assert REGLA.nombre and REGLA.descripcion


# --- Casos que cumplen -----------------------------------------------------
def test_servicio_que_no_exige_autorizacion_cumple():
    assert REGLA.evaluar(contexto([consulta("890201", 41000)])) == []


def test_servicio_con_numero_de_autorizacion_cumple():
    factura = contexto([procedimiento("871121", 65000, "AUT-55821")], soportes=CON_LECTURA)
    assert REGLA.evaluar(factura) == []


def test_eps_que_no_exige_autorizaciones_cumple():
    factura = contexto([procedimiento("871121", 60000)], codigos_con_autorizacion=set(), nombre_eps="EPS Gamma")
    assert REGLA.evaluar(factura) == []


# --- Casos que fallan ------------------------------------------------------
def test_servicio_sin_autorizacion_genera_hallazgo_por_su_valor():
    hallazgos = REGLA.evaluar(contexto([consulta("890201", 41000), procedimiento("871121", 65000)]))
    assert len(hallazgos) == 1
    hallazgo = hallazgos[0]
    assert (hallazgo.regla, hallazgo.grupo, hallazgo.valor_en_riesgo) == ("AU-01", "AU", 65000)
    assert "EPS Beta" in hallazgo.detalle and "871121" in hallazgo.detalle


def test_autorizacion_en_blanco_cuenta_como_faltante():
    assert len(REGLA.evaluar(contexto([procedimiento("902210", 19500, "   ")]))) == 1


def test_un_hallazgo_por_cada_servicio_sin_autorizar():
    factura = contexto([procedimiento("871121", 65000), procedimiento("902210", 19500)])
    assert [h.valor_en_riesgo for h in REGLA.evaluar(factura)] == [65000, 19500]
