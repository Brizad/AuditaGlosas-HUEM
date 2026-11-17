"""Prueba integral del motor con `data/lote_demo.json`.

El resultado debe ser idéntico al del prototipo del Sprint 0 (`index.html`):
12 facturas, 5 aptas, 7 con inconsistencias y $260.000 en riesgo.
"""
import pytest
from sqlalchemy import select

from app.modelos import Factura, Lote
from app.reglas import reglas_registradas, validar_factura
from app.servicios.validacion import cargar_datos_referencia, construir_contexto

# Lo que debe encontrar el motor en cada factura: (reglas que se disparan, valor en riesgo).
ESPERADO = {
    "FV-1001": ([], 0),
    "FV-1002": ([], 0),
    "FV-1003": (["AU-01", "SO-01"], 106000),   # radiografía sin lectura y sin autorización (tope: total factura)
    "FV-1004": ([], 0),
    "FV-1005": (["TA-01"], 5000),              # cobró 41.000, pactado 36.000
    "FV-1006": (["TA-02"], 32000),             # servicio sin tarifa pactada
    "FV-1007": (["FA-03", "FA-03"], 36000),    # código facturado distinto al del RIPS
    "FV-1008": ([], 0),
    "FV-1009": (["FA-02"], 2000),              # total ≠ suma del RIPS
    "FV-1010": ([], 0),
    "FV-1011": (["FA-04"], 41000),             # código de 5 dígitos
    "FV-1012": (["FA-01"], 38000),             # RIPS de otra factura
}


@pytest.fixture()
def resultados(sesion_con_datos):
    """Valida las 12 facturas del lote demo con todas las reglas."""
    referencia = cargar_datos_referencia(sesion_con_datos)
    lote = sesion_con_datos.scalar(select(Lote))
    return {
        factura.num_factura: validar_factura(construir_contexto(factura, referencia))
        for factura in lote.facturas
    }


def test_estan_las_ocho_reglas_del_prototipo():
    assert [regla.codigo for regla in reglas_registradas()] == [
        "FA-01", "FA-02", "FA-03", "FA-04", "TA-01", "TA-02", "SO-01", "AU-01",
    ]


def test_totales_iguales_al_prototipo(resultados):
    aptas = [numero for numero, resultado in resultados.items() if resultado.apta]
    con_inconsistencias = [numero for numero, resultado in resultados.items() if not resultado.apta]

    assert len(resultados) == 12
    assert len(aptas) == 5
    assert len(con_inconsistencias) == 7
    assert sum(resultado.valor_en_riesgo for resultado in resultados.values()) == 260000


@pytest.mark.parametrize("num_factura", sorted(ESPERADO))
def test_hallazgos_de_cada_factura(resultados, num_factura):
    reglas_esperadas, riesgo_esperado = ESPERADO[num_factura]
    resultado = resultados[num_factura]
    assert sorted(h.regla for h in resultado.hallazgos) == reglas_esperadas
    assert resultado.valor_en_riesgo == riesgo_esperado


def test_hallazgos_por_grupo_de_causal(resultados):
    por_grupo = {}
    for resultado in resultados.values():
        for hallazgo in resultado.hallazgos:
            por_grupo[hallazgo.grupo] = por_grupo.get(hallazgo.grupo, 0) + 1
    assert por_grupo == {"FA": 5, "TA": 2, "SO": 1, "AU": 1}


def test_las_facturas_guardadas_no_se_modifican_al_validar_en_memoria(sesion_con_datos, resultados):
    """El motor solo calcula; quien guarda el resultado es el servicio de validación."""
    estados = set(sesion_con_datos.scalars(select(Factura.estado)))
    assert estados == {"sin_validar"}
