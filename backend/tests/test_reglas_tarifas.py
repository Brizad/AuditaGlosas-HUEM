"""TA-01 y TA-02 · Tarifas pactadas con la EPS (HU-04)."""
from fabricas import consulta, contexto, medicamento, procedimiento

from app.reglas import obtener_regla

TA01, TA02 = obtener_regla("TA-01"), obtener_regla("TA-02")
TARIFAS_GAMMA = {"871121": 60000, "890201": 36000, "902210": 17000, "903841": 9000, "MED-0001": 430, "MED-0002": 1100}


def test_datos_de_las_reglas():
    assert (TA01.codigo, TA01.grupo) == ("TA-01", "TA")
    assert (TA02.codigo, TA02.grupo) == ("TA-02", "TA")
    assert TA01.nombre and TA01.descripcion and TA02.nombre and TA02.descripcion


# ===========================================================================
# TA-01 · Valor unitario = tarifa pactada
# ===========================================================================
def test_ta01_valor_igual_a_la_tarifa_cumple():
    factura = contexto([consulta("890201", 41000), medicamento("MED-0001", 20, 480)], soportes=["Fórmula médica"])
    assert TA01.evaluar(factura) == []


def test_ta01_diferencia_de_centavos_se_tolera():
    assert TA01.evaluar(contexto([consulta("890201", 41000.5)])) == []


def test_ta01_valor_mayor_pone_en_riesgo_la_diferencia():
    """Caso FV-1005 del lote demo: se cobró 41.000 y EPS Gamma pactó 36.000."""
    factura = contexto([consulta("890201", 41000)], tarifas=TARIFAS_GAMMA, nombre_eps="EPS Gamma")
    hallazgos = TA01.evaluar(factura)
    assert len(hallazgos) == 1
    assert (hallazgos[0].regla, hallazgos[0].grupo, hallazgos[0].valor_en_riesgo) == ("TA-01", "TA", 5000)
    assert "$41.000" in hallazgos[0].detalle and "$36.000" in hallazgos[0].detalle and "EPS Gamma" in hallazgos[0].detalle


def test_ta01_valor_menor_tambien_se_reporta():
    hallazgos = TA01.evaluar(contexto([consulta("890201", 40000)]))
    assert [h.valor_en_riesgo for h in hallazgos] == [1000]


def test_ta01_en_medicamentos_la_diferencia_se_multiplica_por_la_cantidad():
    hallazgos = TA01.evaluar(contexto([medicamento("MED-0001", 20, 500)]))
    assert [h.valor_en_riesgo for h in hallazgos] == [400]      # (500 - 480) × 20


def test_ta01_no_reporta_servicios_sin_tarifa():
    assert TA01.evaluar(contexto([consulta("890301", 32000)], tarifas=TARIFAS_GAMMA)) == []


# ===========================================================================
# TA-02 · El servicio tiene tarifa pactada
# ===========================================================================
def test_ta02_servicio_con_tarifa_cumple():
    assert TA02.evaluar(contexto([consulta("890201", 41000)])) == []


def test_ta02_servicio_sin_tarifa_pone_en_riesgo_su_valor():
    """Caso FV-1006 del lote demo: EPS Gamma no tiene pactada la consulta de control 890301."""
    factura = contexto([consulta("890301", 32000)], tarifas=TARIFAS_GAMMA, nombre_eps="EPS Gamma")
    hallazgos = TA02.evaluar(factura)
    assert len(hallazgos) == 1
    assert (hallazgos[0].regla, hallazgos[0].grupo, hallazgos[0].valor_en_riesgo) == ("TA-02", "TA", 32000)
    assert "890301" in hallazgos[0].detalle and "EPS Gamma" in hallazgos[0].detalle


def test_ta02_medicamento_sin_tarifa_falla():
    """EPS Beta no tiene pactada la amoxicilina (MED-0002)."""
    hallazgos = TA02.evaluar(contexto([medicamento("MED-0002", 21, 1200)]))
    assert [h.valor_en_riesgo for h in hallazgos] == [25200]


def test_ta02_no_repite_el_error_de_un_codigo_mal_formado():
    """Un código de 5 dígitos ya lo reporta FA-04; TA-02 no lo cuenta otra vez."""
    assert TA02.evaluar(contexto([consulta("89020", 41000)])) == []


def test_ta02_procedimiento_bien_formado_pero_desconocido_falla():
    assert len(TA02.evaluar(contexto([procedimiento("999999", 5000)]))) == 1


def test_ta02_eps_sin_contrato_reporta_todos_los_servicios():
    factura = contexto([consulta("890201", 41000), procedimiento("903841", 10200)], tarifas={})
    assert [h.valor_en_riesgo for h in TA02.evaluar(factura)] == [41000, 10200]
