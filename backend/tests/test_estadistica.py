"""Prueba z de diferencia de proporciones contra valores calculados a mano (HU-07).

Ejemplo de referencia (se puede seguir con calculadora):
    línea base: 45 glosadas de 100  -> p1 = 0,45
    piloto:     30 glosadas de 100  -> p2 = 0,30
    p  = 75 / 200 = 0,375
    EE = raíz(0,375 × 0,625 × (1/100 + 1/100)) = raíz(0,0046875) = 0,068465
    z  = 0,15 / 0,068465 = 2,1909
    valor p (una cola) = 0,0142   ·   valor p (dos colas) = 0,0285
"""
import math

import pytest

from app.servicios.estadistica import (
    HIPOTESIS_DIFERENTE,
    HIPOTESIS_REDUCE,
    cola_superior,
    prueba_z_dos_proporciones,
)


def test_cola_superior_de_la_normal():
    assert cola_superior(0) == pytest.approx(0.5)
    assert cola_superior(1.6449) == pytest.approx(0.05, abs=1e-4)      # valor crítico de una cola
    assert cola_superior(1.96) == pytest.approx(0.025, abs=1e-4)       # valor crítico de dos colas
    assert cola_superior(-1.96) == pytest.approx(0.975, abs=1e-4)


def test_ejemplo_calculado_a_mano_una_cola():
    r = prueba_z_dos_proporciones(45, 100, 30, 100)

    assert r.proporcion_linea_base == pytest.approx(0.45)
    assert r.proporcion_piloto == pytest.approx(0.30)
    assert r.diferencia == pytest.approx(0.15)
    assert r.proporcion_combinada == pytest.approx(0.375)
    assert r.error_estandar == pytest.approx(math.sqrt(0.0046875))
    assert r.z == pytest.approx(2.1909, abs=1e-4)
    assert r.valor_p == pytest.approx(0.0142, abs=1e-4)
    assert r.valor_critico == pytest.approx(1.6449, abs=1e-4)
    assert r.hipotesis == HIPOTESIS_REDUCE and r.alfa == 0.05
    assert r.se_rechaza_h0 is True
    assert r.supuestos_cumplidos is True and r.advertencias == []
    assert "se rechaza la hipótesis nula" in r.interpretacion
    assert "30,0 %" in r.interpretacion and "45,0 %" in r.interpretacion and "z = 2,19" in r.interpretacion


def test_ejemplo_calculado_a_mano_dos_colas():
    r = prueba_z_dos_proporciones(45, 100, 30, 100, hipotesis=HIPOTESIS_DIFERENTE)

    assert r.z == pytest.approx(2.1909, abs=1e-4)
    assert r.valor_p == pytest.approx(0.0285, abs=1e-4)          # el doble que con una cola
    assert r.valor_critico == pytest.approx(1.96, abs=1e-3)
    assert r.se_rechaza_h0 is True
    assert "significativamente menor" in r.interpretacion


def test_intervalo_de_confianza_de_la_diferencia():
    """IC 95 %: 0,15 ± 1,96 × raíz(0,45×0,55/100 + 0,30×0,70/100) = 0,15 ± 0,1326."""
    r = prueba_z_dos_proporciones(45, 100, 30, 100)
    assert r.intervalo_inferior == pytest.approx(0.0174, abs=1e-4)
    assert r.intervalo_superior == pytest.approx(0.2826, abs=1e-4)
    assert r.nivel_confianza == pytest.approx(0.95)


def test_reduccion_grande_con_200_facturas_por_grupo():
    """El caso de los lotes de demostración: 40 % contra 15 %."""
    r = prueba_z_dos_proporciones(80, 200, 30, 200)
    assert r.z == pytest.approx(5.599, abs=1e-3)
    assert r.valor_p < 0.001
    assert r.se_rechaza_h0 is True
    assert "valor p < 0,001" in r.interpretacion


def test_reduccion_que_no_alcanza_a_ser_significativa():
    """Con muestras pequeñas la misma baja puede deberse al azar: no se rechaza H0."""
    r = prueba_z_dos_proporciones(5, 12, 2, 12)
    assert r.z == pytest.approx(1.347, abs=1e-3)
    assert r.valor_p == pytest.approx(0.0889, abs=1e-3)
    assert r.se_rechaza_h0 is False
    assert r.supuestos_cumplidos is False and len(r.advertencias) == 1
    assert "no se rechaza la hipótesis nula" in r.interpretacion
    assert "podría deberse al azar" in r.interpretacion


def test_si_el_piloto_empeora_una_cola_no_rechaza_pero_dos_colas_si():
    una_cola = prueba_z_dos_proporciones(30, 100, 45, 100)
    assert una_cola.z == pytest.approx(-2.1909, abs=1e-4)
    assert una_cola.valor_p == pytest.approx(0.9858, abs=1e-4)
    assert una_cola.se_rechaza_h0 is False
    assert "no es menor" in una_cola.interpretacion

    dos_colas = prueba_z_dos_proporciones(30, 100, 45, 100, hipotesis=HIPOTESIS_DIFERENTE)
    assert dos_colas.se_rechaza_h0 is True
    assert "significativamente mayor" in dos_colas.interpretacion


def test_proporciones_iguales_dan_z_cero():
    r = prueba_z_dos_proporciones(20, 100, 40, 200)
    assert r.z == pytest.approx(0)
    assert r.valor_p == pytest.approx(0.5)
    assert r.se_rechaza_h0 is False


@pytest.mark.parametrize("glosadas", [0, 10])
def test_sin_variacion_no_se_divide_por_cero(glosadas):
    """Si ninguna (o todas) las facturas están glosadas en ambos grupos, el error estándar es 0."""
    r = prueba_z_dos_proporciones(glosadas, 10, glosadas, 10)
    assert r.error_estandar == 0 and r.z == 0 and r.valor_p == 1
    assert r.se_rechaza_h0 is False
    assert any("no hay variación" in texto for texto in r.advertencias)


def test_alfa_cambia_la_decision():
    """z = 2,19 tiene valor p = 0,014: se rechaza con alfa 0,05 pero no con alfa 0,01."""
    assert prueba_z_dos_proporciones(45, 100, 30, 100, alfa=0.05).se_rechaza_h0 is True
    estricta = prueba_z_dos_proporciones(45, 100, 30, 100, alfa=0.01)
    assert estricta.se_rechaza_h0 is False
    assert estricta.valor_critico == pytest.approx(2.3263, abs=1e-4)


@pytest.mark.parametrize(
    "argumentos",
    [
        (5, 0, 5, 10),        # total en cero
        (5, 10, 5, -1),       # total negativo
        (11, 10, 5, 10),      # más glosadas que facturas
        (-1, 10, 5, 10),      # glosadas negativas
    ],
)
def test_cifras_imposibles_se_rechazan(argumentos):
    with pytest.raises(ValueError):
        prueba_z_dos_proporciones(*argumentos)


def test_alfa_o_hipotesis_invalidos_se_rechazan():
    with pytest.raises(ValueError):
        prueba_z_dos_proporciones(5, 10, 5, 10, alfa=0)
    with pytest.raises(ValueError):
        prueba_z_dos_proporciones(5, 10, 5, 10, alfa=1)
    with pytest.raises(ValueError):
        prueba_z_dos_proporciones(5, 10, 5, 10, hipotesis="aumenta")
