"""FA-01 a FA-04 · Concordancia entre la factura y su RIPS (HU-03)."""
import pytest
from fabricas import consulta, contexto, medicamento, procedimiento

from app.reglas import ItemFacturado, obtener_regla

FA01, FA02, FA03, FA04 = (obtener_regla(codigo) for codigo in ("FA-01", "FA-02", "FA-03", "FA-04"))


@pytest.mark.parametrize("regla, codigo", [(FA01, "FA-01"), (FA02, "FA-02"), (FA03, "FA-03"), (FA04, "FA-04")])
def test_datos_de_las_reglas(regla, codigo):
    assert (regla.codigo, regla.grupo) == (codigo, "FA")
    assert regla.nombre and regla.descripcion


# ===========================================================================
# FA-01 · El RIPS corresponde a la factura
# ===========================================================================
def test_fa01_mismo_numero_cumple():
    assert FA01.evaluar(contexto([consulta("890201", 41000)])) == []


def test_fa01_rips_de_otra_factura_pone_en_riesgo_todo_el_valor():
    factura = contexto([consulta("890201", 38000)], num_factura="FV-1012", rips_num_factura="FV-1021")
    hallazgos = FA01.evaluar(factura)
    assert len(hallazgos) == 1
    assert (hallazgos[0].regla, hallazgos[0].grupo, hallazgos[0].valor_en_riesgo) == ("FA-01", "FA", 38000)
    assert "FV-1012" in hallazgos[0].detalle and "FV-1021" in hallazgos[0].detalle


def test_fa01_rips_sin_numero_de_factura_falla():
    hallazgos = FA01.evaluar(contexto([consulta("890201", 38000)], rips_num_factura=None))
    assert len(hallazgos) == 1 and "(vacío)" in hallazgos[0].detalle


# ===========================================================================
# FA-02 · Total de la factura = suma del RIPS
# ===========================================================================
def test_fa02_total_igual_a_la_suma_cumple():
    assert FA02.evaluar(contexto([consulta("890201", 38000), medicamento("MED-0002", 21, 1200)])) == []


def test_fa02_diferencia_de_centavos_se_tolera():
    factura = contexto([consulta("890201", 38000)], valor_total=38000.4)
    assert FA02.evaluar(factura) == []


def test_fa02_total_mayor_pone_en_riesgo_la_diferencia():
    """Caso FV-1009 del lote demo: factura 65.200, RIPS 63.200."""
    factura = contexto([consulta("890201", 38000), medicamento("MED-0002", 21, 1200)], valor_total=65200)
    hallazgos = FA02.evaluar(factura)
    assert [h.valor_en_riesgo for h in hallazgos] == [2000]
    assert "$65.200" in hallazgos[0].detalle and "$63.200" in hallazgos[0].detalle


def test_fa02_total_menor_tambien_falla():
    factura = contexto([consulta("890201", 38000)], valor_total=30000)
    assert [h.valor_en_riesgo for h in FA02.evaluar(factura)] == [8000]


def test_fa02_rips_sin_servicios_pone_en_riesgo_todo():
    factura = contexto([], valor_total=38000, items=[ItemFacturado("890201", 1, 38000)])
    assert [h.valor_en_riesgo for h in FA02.evaluar(factura)] == [38000]


# ===========================================================================
# FA-03 · Códigos facturados ↔ códigos del RIPS
# ===========================================================================
def test_fa03_mismos_codigos_cumple():
    assert FA03.evaluar(contexto([consulta("890201", 41000), procedimiento("902210", 19500, "AUT-1")])) == []


def test_fa03_codigo_distinto_genera_hallazgo_en_los_dos_sentidos():
    """Caso FV-1007 del lote demo: se facturó 902212 pero el RIPS trae 902210."""
    factura = contexto(
        [consulta("890201", 38000), procedimiento("902210", 18000)],
        items=[ItemFacturado("890201", 1, 38000), ItemFacturado("902212", 1, 18000)],
    )
    hallazgos = FA03.evaluar(factura)
    assert [h.titulo for h in hallazgos] == [
        "Código facturado sin registro en el RIPS", "Servicio del RIPS no facturado",
    ]
    assert [h.valor_en_riesgo for h in hallazgos] == [18000, 18000]
    assert "902212" in hallazgos[0].detalle and "902210" in hallazgos[1].detalle


def test_fa03_item_facturado_que_no_esta_en_el_rips():
    factura = contexto(
        [consulta("890201", 41000)],
        items=[ItemFacturado("890201", 1, 41000), ItemFacturado("MED-0001", 10, 480)],
    )
    hallazgos = FA03.evaluar(factura)
    assert len(hallazgos) == 1 and hallazgos[0].valor_en_riesgo == 4800    # cantidad × valor unitario


def test_fa03_servicio_del_rips_que_no_se_facturo():
    factura = contexto(
        [consulta("890201", 41000), procedimiento("903841", 10200)],
        items=[ItemFacturado("890201", 1, 41000)],
    )
    hallazgos = FA03.evaluar(factura)
    assert len(hallazgos) == 1 and hallazgos[0].valor_en_riesgo == 10200


# ===========================================================================
# FA-04 · Formato de los códigos
# ===========================================================================
def test_fa04_codigos_de_seis_caracteres_cumplen():
    assert FA04.evaluar(contexto([consulta("890201", 41000), procedimiento("A1B2C3", 5000)])) == []


def test_fa04_no_revisa_medicamentos():
    assert FA04.evaluar(contexto([medicamento("MED-0001", 20, 480)])) == []


@pytest.mark.parametrize("codigo", ["89020", "8902011", "89020a", "89-201"])
def test_fa04_codigo_mal_formado_pone_en_riesgo_el_servicio(codigo):
    hallazgos = FA04.evaluar(contexto([consulta(codigo, 41000)]))
    assert len(hallazgos) == 1
    assert (hallazgos[0].regla, hallazgos[0].valor_en_riesgo) == ("FA-04", 41000)
    assert codigo in hallazgos[0].detalle


def test_fa04_revisa_tambien_los_procedimientos():
    assert len(FA04.evaluar(contexto([procedimiento("9022", 19500, "AUT-1")]))) == 1
