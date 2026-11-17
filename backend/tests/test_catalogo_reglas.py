"""Catálogo de reglas configurable y validación guardada en la base de datos (HU-06)."""
from sqlalchemy import func, select

from app.modelos import Factura, Hallazgo, Lote, Regla
from app.servicios.catalogo_reglas import cambiar_estado_regla, codigos_activos, listar_reglas, sincronizar_reglas
from app.servicios.lotes import resumir_lote
from app.servicios.validacion import validar_lote

LAS_OCHO = ["FA-01", "FA-02", "FA-03", "FA-04", "TA-01", "TA-02", "SO-01", "AU-01"]


def lote_demo(sesion) -> Lote:
    return sesion.scalar(select(Lote))


def total_hallazgos(sesion) -> int:
    return sesion.scalar(select(func.count()).select_from(Hallazgo))


def estado_de(sesion, num_factura: str) -> str:
    return sesion.scalar(select(Factura.estado).where(Factura.num_factura == num_factura))


# --- Sincronización entre el código y la tabla -------------------------------
def test_sincronizar_crea_las_ocho_reglas_activas(sesion):
    assert sincronizar_reglas(sesion) == 8
    reglas = listar_reglas(sesion)
    assert [regla.codigo for regla in reglas] == LAS_OCHO
    assert all(regla.activa for regla in reglas)
    assert codigos_activos(sesion) == set(LAS_OCHO)


def test_sincronizar_dos_veces_no_duplica(sesion):
    sincronizar_reglas(sesion)
    assert sincronizar_reglas(sesion) == 0
    assert sesion.scalar(select(func.count()).select_from(Regla)) == 8


def test_sincronizar_respeta_las_reglas_desactivadas(sesion):
    sincronizar_reglas(sesion)
    cambiar_estado_regla(sesion, "TA-01", activa=False)
    sincronizar_reglas(sesion)                      # como si se reiniciara el servidor
    assert sesion.get(Regla, "TA-01").activa is False


def test_sincronizar_actualiza_la_descripcion_si_cambio_en_el_codigo(sesion):
    sincronizar_reglas(sesion)
    sesion.get(Regla, "SO-01").descripcion = "Texto viejo"
    sesion.commit()
    sincronizar_reglas(sesion)
    assert sesion.get(Regla, "SO-01").descripcion.startswith("La factura incluye los soportes")


# --- Activar y desactivar ------------------------------------------------------
def test_desactivar_y_activar_una_regla(sesion):
    sincronizar_reglas(sesion)
    assert cambiar_estado_regla(sesion, "AU-01", activa=False).activa is False
    assert "AU-01" not in codigos_activos(sesion)
    assert cambiar_estado_regla(sesion, "AU-01", activa=True).activa is True
    assert "AU-01" in codigos_activos(sesion)


def test_cambiar_una_regla_que_no_existe_devuelve_none(sesion):
    sincronizar_reglas(sesion)
    assert cambiar_estado_regla(sesion, "ZZ-99", activa=False) is None


# --- Validación guardada --------------------------------------------------------
def test_validar_lote_demo_guarda_el_mismo_resultado_del_prototipo(sesion_con_datos):
    lote = validar_lote(sesion_con_datos, lote_demo(sesion_con_datos))
    resumen = resumir_lote(sesion_con_datos, lote.id)

    assert lote.estado == "validado" and lote.fecha_validacion is not None
    assert resumen.total_facturas == 12
    assert resumen.aptas == 5
    assert resumen.con_inconsistencias == 7
    assert resumen.sin_validar == 0
    assert resumen.valor_en_riesgo == 260000
    assert resumen.valor_facturado == 664800
    assert resumen.porcentaje_aptas == 41.7
    assert total_hallazgos(sesion_con_datos) == 9


def test_antes_de_validar_todas_las_facturas_estan_sin_validar(sesion_con_datos):
    resumen = resumir_lote(sesion_con_datos, lote_demo(sesion_con_datos).id)
    assert (resumen.total_facturas, resumen.sin_validar, resumen.aptas) == (12, 12, 0)
    assert resumen.porcentaje_aptas == 0


def test_revalidar_no_duplica_hallazgos(sesion_con_datos):
    lote = lote_demo(sesion_con_datos)
    validar_lote(sesion_con_datos, lote)
    validar_lote(sesion_con_datos, lote)
    assert total_hallazgos(sesion_con_datos) == 9
    assert resumir_lote(sesion_con_datos, lote.id).valor_en_riesgo == 260000


def test_desactivar_una_regla_cambia_el_resultado_al_revalidar(sesion_con_datos):
    """Sin TA-01, la factura FV-1005 (tarifa distinta, $5.000) pasa a ser apta."""
    lote = lote_demo(sesion_con_datos)
    validar_lote(sesion_con_datos, lote)
    assert estado_de(sesion_con_datos, "FV-1005") == "con_inconsistencias"

    cambiar_estado_regla(sesion_con_datos, "TA-01", activa=False)
    validar_lote(sesion_con_datos, lote)
    resumen = resumir_lote(sesion_con_datos, lote.id)
    assert estado_de(sesion_con_datos, "FV-1005") == "apta"
    assert (resumen.aptas, resumen.con_inconsistencias, resumen.valor_en_riesgo) == (6, 6, 255000)
    assert total_hallazgos(sesion_con_datos) == 8

    cambiar_estado_regla(sesion_con_datos, "TA-01", activa=True)
    validar_lote(sesion_con_datos, lote)
    resumen = resumir_lote(sesion_con_datos, lote.id)
    assert (resumen.aptas, resumen.con_inconsistencias, resumen.valor_en_riesgo) == (5, 7, 260000)


def test_con_todas_las_reglas_apagadas_todo_el_lote_queda_apto(sesion_con_datos):
    sincronizar_reglas(sesion_con_datos)
    for codigo in LAS_OCHO:
        cambiar_estado_regla(sesion_con_datos, codigo, activa=False)
    lote = validar_lote(sesion_con_datos, lote_demo(sesion_con_datos))
    resumen = resumir_lote(sesion_con_datos, lote.id)
    assert (resumen.aptas, resumen.con_inconsistencias, resumen.valor_en_riesgo) == (12, 0, 0)
    assert total_hallazgos(sesion_con_datos) == 0


def test_los_hallazgos_guardan_regla_grupo_detalle_y_valor(sesion_con_datos):
    validar_lote(sesion_con_datos, lote_demo(sesion_con_datos))
    factura = sesion_con_datos.scalar(select(Factura).where(Factura.num_factura == "FV-1005"))
    assert factura.valor_en_riesgo == 5000
    hallazgo = factura.hallazgos[0]
    assert (hallazgo.regla_codigo, hallazgo.grupo, hallazgo.valor_en_riesgo) == ("TA-01", "TA", 5000)
    assert hallazgo.titulo == "Tarifa distinta a la pactada"
    assert "EPS Gamma" in hallazgo.detalle
