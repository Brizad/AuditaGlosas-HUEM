"""Casos límite de las reglas y del motor (Fase 8).

Aquí van los bordes: el valor exacto de la tolerancia, facturas vacías,
códigos repetidos y combinaciones de varias reglas en una misma factura.
"""
import pytest
from fabricas import consulta, contexto, medicamento, procedimiento

from app.reglas import ItemFacturado, ReglaBase, obtener_regla, registrar, validar_factura
from app.reglas.base import TOLERANCIA, texto_comparable


def codigos(hallazgos) -> list[str]:
    return [hallazgo.regla for hallazgo in hallazgos]


# --- Tolerancia de $0,50 ---------------------------------------------------------------
@pytest.mark.parametrize("diferencia, falla", [(0.5, False), (-0.5, False), (0.51, True), (-0.51, True), (1, True)])
def test_fa02_borde_de_la_tolerancia(diferencia, falla):
    """Hasta 50 centavos de diferencia se acepta (redondeos); un centavo más ya es hallazgo."""
    assert TOLERANCIA == 0.5
    factura = contexto([consulta("890201", 41000)], valor_total=41000 + diferencia)
    assert bool(obtener_regla("FA-02").evaluar(factura)) is falla


@pytest.mark.parametrize("diferencia, falla", [(0.5, False), (-0.5, False), (0.51, True), (-0.51, True)])
def test_ta01_borde_de_la_tolerancia(diferencia, falla):
    factura = contexto([consulta("890201", 41000 + diferencia)])
    assert bool(obtener_regla("TA-01").evaluar(factura)) is falla


# --- FA-01 ---------------------------------------------------------------------------------
@pytest.mark.parametrize("numero_rips", ["fv-9001", "FV-9001 ", "FV9001", ""])
def test_fa01_exige_el_numero_exacto(numero_rips):
    """El número debe ser idéntico: mayúsculas, guiones y espacios cuentan (así lo revisa la EPS)."""
    factura = contexto([consulta("890201", 41000)], rips_num_factura=numero_rips)
    assert codigos(obtener_regla("FA-01").evaluar(factura)) == ["FA-01"]


# --- FA-03 ---------------------------------------------------------------------------------
def test_fa03_el_mismo_codigo_repetido_no_es_un_error():
    """Dos hemogramas el mismo día: el código aparece dos veces en ambos lados y está bien."""
    servicios = [procedimiento("902210", 19500, "AUT-1"), procedimiento("902210", 19500, "AUT-2")]
    assert obtener_regla("FA-03").evaluar(contexto(servicios, soportes=["Resultado de laboratorio"])) == []


def test_fa03_factura_sin_items_reporta_cada_servicio_del_rips():
    factura = contexto([consulta("890201", 41000), consulta("890301", 34000)], items=[])
    hallazgos = obtener_regla("FA-03").evaluar(factura)
    assert [h.titulo for h in hallazgos] == ["Servicio del RIPS no facturado"] * 2
    assert sum(h.valor_en_riesgo for h in hallazgos) == 75000


def test_fa03_rips_sin_servicios_reporta_cada_item_de_la_factura():
    factura = contexto([], items=[ItemFacturado("890201", 1, 41000)], valor_total=41000)
    hallazgos = obtener_regla("FA-03").evaluar(factura)
    assert [h.titulo for h in hallazgos] == ["Código facturado sin registro en el RIPS"]
    assert hallazgos[0].valor_en_riesgo == 41000


# --- FA-04 ---------------------------------------------------------------------------------
@pytest.mark.parametrize("codigo", ["89020", "8902011", "89020a", "89-201", "89 201", " 89020"])
def test_fa04_formatos_invalidos(codigo):
    assert codigos(obtener_regla("FA-04").evaluar(contexto([consulta(codigo, 41000)]))) == ["FA-04"]


@pytest.mark.parametrize("codigo", ["890201", "89020A", "ABCDEF", "000000"])
def test_fa04_formatos_validos(codigo):
    assert obtener_regla("FA-04").evaluar(contexto([consulta(codigo, 41000)])) == []


# --- SO-01 y AU-01 -------------------------------------------------------------------------
def test_so01_un_solo_soporte_sirve_para_varios_servicios_del_mismo_tipo():
    servicios = [procedimiento("902210", 19500, "AUT-1"), procedimiento("903841", 10200)]
    assert obtener_regla("SO-01").evaluar(contexto(servicios, soportes=["Resultado de laboratorio"])) == []


def test_so01_las_tildes_si_cuentan_al_comparar_el_nombre_del_soporte():
    """Se ignoran mayúsculas y espacios, pero no las tildes: «Formula medica» no es «Fórmula médica»."""
    assert texto_comparable("  FÓRMULA   médica ") == texto_comparable("Fórmula médica")
    factura = contexto([medicamento("MED-0001", 20, 480)], soportes=["Formula medica"])
    assert codigos(obtener_regla("SO-01").evaluar(factura)) == ["SO-01"]


@pytest.mark.parametrize("numero", ["   ", "", None])
def test_au01_autorizacion_vacia_o_en_blanco(numero):
    factura = contexto([procedimiento("871121", 65000, numero)], soportes=["Lectura o informe del examen"])
    assert codigos(obtener_regla("AU-01").evaluar(factura)) == ["AU-01"]


# --- Motor ---------------------------------------------------------------------------------
def test_factura_de_valor_cero_no_tiene_valor_en_riesgo_pero_no_es_apta():
    """Con total 0 no hay dinero en riesgo, pero los hallazgos siguen existiendo."""
    factura = contexto([consulta("890201", 41000)], valor_total=0)
    resultado = validar_factura(factura)
    assert not resultado.apta and resultado.valor_en_riesgo == 0
    assert "FA-02" in codigos(resultado.hallazgos)


def test_factura_sin_servicios_ni_items_y_valor_cero_es_apta():
    resultado = validar_factura(contexto([]))
    assert resultado.apta and resultado.valor_en_riesgo == 0


def test_factura_con_errores_de_los_cuatro_grupos():
    """Una sola factura puede incumplir reglas de facturación, tarifas, soportes y autorizaciones a la vez."""
    servicios = [
        consulta("890201", 46000),               # TA-01: lo pactado es 41.000
        procedimiento("871121", 65000),          # SO-01 (sin lectura) y AU-01 (sin autorización)
    ]
    factura = contexto(servicios, rips_num_factura="FV-0000", valor_total=120000)   # FA-01 y FA-02
    resultado = validar_factura(factura)

    assert codigos(resultado.hallazgos) == ["FA-01", "FA-02", "TA-01", "SO-01", "AU-01"]
    assert {hallazgo.grupo for hallazgo in resultado.hallazgos} == {"FA", "TA", "SO", "AU"}
    # FA-01 por sí sola ya pone en riesgo toda la factura: el tope es el total.
    assert resultado.valor_en_riesgo == 120000


def test_las_reglas_se_aplican_en_orden_fa_ta_so_au():
    factura = contexto([procedimiento("871121", 70000)])       # TA-01, SO-01 y AU-01
    assert codigos(validar_factura(factura).hallazgos) == ["TA-01", "SO-01", "AU-01"]


def test_solo_se_aplican_las_reglas_indicadas_como_activas():
    factura = contexto([procedimiento("871121", 70000)])
    assert codigos(validar_factura(factura, codigos_activos={"AU-01"}).hallazgos) == ["AU-01"]
    assert validar_factura(factura, codigos_activos=set()).apta


def test_un_hallazgo_nunca_tiene_valor_negativo():
    hallazgo = obtener_regla("SO-01").hallazgo(detalle="Prueba", valor_en_riesgo=-500)
    assert hallazgo.valor_en_riesgo == 0


def test_no_se_puede_registrar_una_regla_incompleta():
    with pytest.raises(ValueError, match="código, nombre y descripción"):
        @registrar
        class ReglaSinNombre(ReglaBase):
            codigo, nombre, grupo, descripcion = "FA-99", "", "FA", "Le falta el nombre."

            def evaluar(self, contexto):
                return []
    assert obtener_regla("FA-99") is None
