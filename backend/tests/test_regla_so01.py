"""SO-01 · Soportes obligatorios según el tipo de servicio (HU-02)."""
from fabricas import consulta, contexto, medicamento, procedimiento

from app.reglas import obtener_regla

REGLA = obtener_regla("SO-01")


def test_datos_de_la_regla():
    assert (REGLA.codigo, REGLA.grupo) == ("SO-01", "SO")
    assert REGLA.nombre and REGLA.descripcion


# --- Casos que cumplen -----------------------------------------------------
def test_consulta_no_exige_soportes():
    assert REGLA.evaluar(contexto([consulta("890201", 41000)])) == []


def test_laboratorio_con_su_resultado_cumple():
    factura = contexto([procedimiento("903841", 10200)], soportes=["Resultado de laboratorio"])
    assert REGLA.evaluar(factura) == []


def test_el_nombre_del_soporte_no_distingue_mayusculas_ni_espacios():
    factura = contexto([procedimiento("903841", 10200)], soportes=["  resultado de  LABORATORIO "])
    assert REGLA.evaluar(factura) == []


def test_servicio_que_no_esta_en_el_catalogo_no_exige_soportes():
    assert REGLA.evaluar(contexto([procedimiento("999999", 5000)])) == []


# --- Casos que fallan ------------------------------------------------------
def test_imagen_sin_lectura_genera_hallazgo_por_el_valor_del_servicio():
    hallazgos = REGLA.evaluar(contexto([consulta("890201", 41000), procedimiento("871121", 65000, "AUT-1")]))
    assert len(hallazgos) == 1
    hallazgo = hallazgos[0]
    assert (hallazgo.regla, hallazgo.grupo, hallazgo.valor_en_riesgo) == ("SO-01", "SO", 65000)
    assert "871121" in hallazgo.detalle and "Lectura o informe del examen" in hallazgo.detalle


def test_medicamento_sin_formula_pone_en_riesgo_cantidad_por_valor_unitario():
    hallazgos = REGLA.evaluar(contexto([medicamento("MED-0001", 20, 480)]))
    assert [h.valor_en_riesgo for h in hallazgos] == [9600]


def test_soporte_de_otro_tipo_no_sirve():
    factura = contexto([procedimiento("871121", 65000, "AUT-1")], soportes=["Resultado de laboratorio"])
    assert len(REGLA.evaluar(factura)) == 1


def test_un_hallazgo_por_cada_servicio_sin_soporte():
    factura = contexto([procedimiento("903841", 10200), procedimiento("902210", 19500, "AUT-1")])
    assert [h.valor_en_riesgo for h in REGLA.evaluar(factura)] == [10200, 19500]


def test_tipo_con_dos_soportes_exige_los_dos():
    factura = contexto(
        [procedimiento("871121", 65000, "AUT-1")],
        soportes=["Lectura o informe del examen"],
        soportes_requeridos={"imagen": ["Lectura o informe del examen", "Orden médica"]},
    )
    hallazgos = REGLA.evaluar(factura)
    assert len(hallazgos) == 1 and "Orden médica" in hallazgos[0].detalle
