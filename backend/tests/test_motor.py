"""Pruebas del motor de reglas, del registro y del contexto que se arma desde la base de datos."""
import pytest
from fabricas import consulta, contexto, procedimiento
from sqlalchemy import select

from app.modelos import Factura
from app.reglas import GRUPOS, ReglaBase, registrar, reglas_registradas, validar_factura
from app.reglas.base import codigo_valido, pesos
from app.servicios.validacion import cargar_datos_referencia, construir_contexto


# --- Registro ---------------------------------------------------------------
def test_todas_las_reglas_registradas_estan_bien_definidas():
    reglas = reglas_registradas()
    codigos = [regla.codigo for regla in reglas]
    assert len(codigos) == len(set(codigos))
    for regla in reglas:
        assert regla.grupo in GRUPOS
        assert regla.codigo.startswith(regla.grupo + "-")
        assert regla.nombre and regla.descripcion


def test_no_se_puede_registrar_dos_veces_el_mismo_codigo():
    with pytest.raises(ValueError, match="Ya existe"):
        @registrar
        class ReglaRepetida(ReglaBase):
            codigo, nombre, grupo, descripcion = "SO-01", "Repetida", "SO", "No debe registrarse."

            def evaluar(self, contexto):
                return []


def test_no_se_puede_registrar_una_regla_con_grupo_desconocido():
    with pytest.raises(ValueError, match="grupo desconocido"):
        @registrar
        class ReglaSinGrupo(ReglaBase):
            codigo, nombre, grupo, descripcion = "XX-01", "Sin grupo", "XX", "No debe registrarse."

            def evaluar(self, contexto):
                return []


# --- Motor ------------------------------------------------------------------
def test_factura_sin_problemas_es_apta():
    resultado = validar_factura(contexto([consulta("890201", 41000)]))
    assert resultado.apta and resultado.hallazgos == [] and resultado.valor_en_riesgo == 0


def test_el_valor_en_riesgo_no_supera_el_total_de_la_factura():
    """Radiografía sin lectura (65.000) y sin autorización (65.000): suma 130.000, pero la factura vale 106.000."""
    factura = contexto([consulta("890201", 41000), procedimiento("871121", 65000)])
    resultado = validar_factura(factura, codigos_activos={"SO-01", "AU-01"})
    assert sorted(h.regla for h in resultado.hallazgos) == ["AU-01", "SO-01"]
    assert resultado.valor_en_riesgo == 106000
    assert not resultado.apta


def test_las_reglas_inactivas_no_se_aplican():
    factura = contexto([consulta("890201", 41000), procedimiento("871121", 65000)])
    resultado = validar_factura(factura, codigos_activos={"AU-01"})
    assert [h.regla for h in resultado.hallazgos] == ["AU-01"]
    assert resultado.valor_en_riesgo == 65000


def test_sin_reglas_activas_toda_factura_es_apta():
    factura = contexto([procedimiento("871121", 65000)])
    assert validar_factura(factura, codigos_activos=set()).apta


# --- Utilidades --------------------------------------------------------------
def test_formato_de_pesos():
    assert pesos(38000) == "$38.000"
    assert pesos(1234567.4) == "$1.234.567"
    assert pesos(0) == "$0"


@pytest.mark.parametrize("codigo, esperado", [
    ("890201", True), ("A1B2C3", True), ("89020", False), ("8902011", False),
    ("89020a", False), ("89 201", False), ("MED-0001", False), ("", False),
])
def test_formato_de_codigo(codigo, esperado):
    assert codigo_valido(codigo) is esperado


# --- Contexto armado desde la base de datos ----------------------------------
def test_contexto_desde_la_base_de_datos(sesion_con_datos):
    referencia = cargar_datos_referencia(sesion_con_datos)
    factura = sesion_con_datos.scalar(select(Factura).where(Factura.num_factura == "FV-1003"))
    ctx = construir_contexto(factura, referencia)

    assert (ctx.num_factura, ctx.rips_num_factura, ctx.valor_total) == ("FV-1003", "FV-1003", 106000)
    assert ctx.nombre_eps == "EPS Beta"
    assert ctx.tarifas["871121"] == 65000
    assert ctx.codigos_con_autorizacion == {"871121", "902210"}
    assert [(s.clase, s.codigo, s.valor) for s in ctx.servicios] == [
        ("consulta", "890201", 41000), ("procedimiento", "871121", 65000),
    ]
    assert ctx.tipos_servicio["871121"] == "imagen"
    assert ctx.soportes_requeridos["imagen"] == ["Lectura o informe del examen"]


def test_factura_fv1003_del_lote_demo_falla_por_soporte_y_autorizacion(sesion_con_datos):
    referencia = cargar_datos_referencia(sesion_con_datos)
    factura = sesion_con_datos.scalar(select(Factura).where(Factura.num_factura == "FV-1003"))
    resultado = validar_factura(construir_contexto(factura, referencia), codigos_activos={"SO-01", "AU-01"})
    assert sorted(h.regla for h in resultado.hallazgos) == ["AU-01", "SO-01"]
    assert resultado.valor_en_riesgo == 106000
