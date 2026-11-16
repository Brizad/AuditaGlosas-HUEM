"""Pruebas de la base de datos y de la carga de lotes (Fase 2, HU-01)."""
import pytest
from sqlalchemy import func, select, text

from app.base_datos import Base
from app.configuracion import normalizar_url_base_datos
from app.esquemas import LoteEntrada
from app.modelos import (
    AutorizacionRequerida,
    Eps,
    Factura,
    ItemFactura,
    Lote,
    ServicioCatalogo,
    ServicioRips,
    SoporteFactura,
    SoporteRequerido,
    Tarifa,
)
from app.servicios.carga_inicial import ejecutar_carga_inicial
from app.servicios.lotes import ErrorDeCarga, eliminar_lote, guardar_lote


def contar(sesion, modelo) -> int:
    return sesion.scalar(select(func.count()).select_from(modelo))


def factura_minima(numero="FV-1", eps="EPS-ALFA", documento="1090000001") -> dict:
    """Factura sintética con una sola consulta."""
    return {
        "numFactura": numero, "eps": eps, "fechaExpedicion": "2026-07-03", "valorTotal": 38000,
        "items": [{"codigo": "890201", "cantidad": 1, "valorUnitario": 38000}],
        "soportes": [],
        "rips": {"numFactura": numero, "usuarios": [{
            "tipoDocumentoIdentificacion": "CC", "numDocumentoIdentificacion": documento,
            "servicios": {"consultas": [{"codConsulta": "890201", "vrServicio": 38000, "numAutorizacion": None}]},
        }]},
    }


# --- Carga inicial ---------------------------------------------------------
def test_carga_inicial_crea_contratos_catalogo_y_lote_demo(sesion_con_datos):
    sesion = sesion_con_datos
    assert contar(sesion, Eps) == 3
    assert contar(sesion, Tarifa) == 19           # 7 de Alfa + 6 de Beta + 6 de Gamma
    assert contar(sesion, AutorizacionRequerida) == 3
    assert contar(sesion, ServicioCatalogo) == 7
    assert contar(sesion, SoporteRequerido) == 3
    assert contar(sesion, Lote) == 1
    assert contar(sesion, Factura) == 12


def test_carga_inicial_repetida_no_duplica(sesion_con_datos):
    resumen = ejecutar_carga_inicial(sesion_con_datos)
    assert resumen["lote_demo"] == "ya existía"
    assert contar(sesion_con_datos, Eps) == 3
    assert contar(sesion_con_datos, Tarifa) == 19
    assert contar(sesion_con_datos, Factura) == 12


def test_lote_demo_guarda_items_servicios_y_soportes(sesion_con_datos):
    factura = sesion_con_datos.scalar(select(Factura).where(Factura.num_factura == "FV-1004"))
    assert factura.eps.codigo == "EPS-BETA"
    assert factura.valor_total == 43600
    assert [(i.codigo, i.cantidad, i.valor_unitario) for i in factura.items] == [
        ("890301", 1, 34000), ("MED-0001", 20, 480),
    ]
    medicamento = next(s for s in factura.servicios if s.clase == "medicamento")
    assert (medicamento.codigo, medicamento.cantidad, medicamento.valor_unitario, medicamento.valor_servicio) == (
        "MED-0001", 20, 480, 9600,
    )
    assert [s.nombre for s in factura.soportes] == ["Fórmula médica"]
    assert factura.estado == "sin_validar"


def test_el_periodo_se_deduce_de_las_fechas(sesion_con_datos):
    assert sesion_con_datos.scalar(select(Lote)).periodo == "2026-06"


def test_rips_de_otra_factura_se_guarda_para_que_lo_revise_la_regla(sesion_con_datos):
    factura = sesion_con_datos.scalar(select(Factura).where(Factura.num_factura == "FV-1012"))
    assert factura.rips_num_factura == "FV-1021"


# --- Protección de datos (Ley 1581 de 2012) ---------------------------------
def test_no_se_guarda_el_documento_del_paciente(sesion_con_datos):
    """Ninguna celda de ninguna tabla puede contener un documento del lote demo."""
    documentos = {f"90000001{n:02d}" for n in range(1, 13)}
    for tabla in Base.metadata.sorted_tables:
        for fila in sesion_con_datos.execute(text(f"SELECT * FROM {tabla.name}")):
            for valor in fila:
                assert str(valor) not in documentos, f"Documento de paciente encontrado en {tabla.name}"


def test_ninguna_tabla_tiene_columnas_de_identificacion():
    for tabla in Base.metadata.sorted_tables:
        for columna in tabla.columns:
            assert "documento" not in columna.name.lower()
            assert "paciente" not in columna.name.lower()


# --- Guardar y eliminar lotes -----------------------------------------------
def test_guardar_lote_rechaza_factura_repetida(sesion_con_datos):
    entrada = LoteEntrada(nombre="Repetidas", facturas=[factura_minima("FV-1"), factura_minima("FV-1")])
    with pytest.raises(ErrorDeCarga) as error:
        guardar_lote(sesion_con_datos, entrada)
    assert "repetida" in error.value.errores[0]
    assert contar(sesion_con_datos, Lote) == 1    # solo el lote demo: no se guardó nada


def test_guardar_lote_rechaza_eps_no_registrada(sesion_con_datos):
    entrada = LoteEntrada(nombre="EPS rara", facturas=[factura_minima(eps="EPS-OMEGA")])
    with pytest.raises(ErrorDeCarga) as error:
        guardar_lote(sesion_con_datos, entrada)
    assert "EPS-OMEGA" in error.value.errores[0]


def test_la_misma_factura_puede_estar_en_dos_lotes(sesion_con_datos):
    guardar_lote(sesion_con_datos, LoteEntrada(nombre="Antes", tipo="linea_base", facturas=[factura_minima()]))
    guardar_lote(sesion_con_datos, LoteEntrada(nombre="Después", tipo="piloto", facturas=[factura_minima()]))
    assert contar(sesion_con_datos, Lote) == 3


def test_codigos_numericos_se_convierten_a_texto(sesion_con_datos):
    datos = factura_minima()
    datos["items"][0]["codigo"] = 890201
    datos["rips"]["usuarios"][0]["servicios"]["consultas"][0]["codConsulta"] = 890201
    lote = guardar_lote(sesion_con_datos, LoteEntrada(nombre="Numéricos", facturas=[datos]))
    assert lote.facturas[0].items[0].codigo == "890201"
    assert lote.facturas[0].servicios[0].codigo == "890201"


def test_eliminar_lote_borra_todo_lo_que_depende_de_el(sesion_con_datos):
    lote = sesion_con_datos.scalar(select(Lote))
    eliminar_lote(sesion_con_datos, lote)
    for modelo in (Lote, Factura, ItemFactura, ServicioRips, SoporteFactura):
        assert contar(sesion_con_datos, modelo) == 0
    assert contar(sesion_con_datos, Eps) == 3     # los contratos no se tocan


# --- Configuración ----------------------------------------------------------
def test_sin_database_url_se_usa_sqlite():
    assert normalizar_url_base_datos(None).startswith("sqlite:///")
    assert normalizar_url_base_datos("  ").endswith("auditaglosas.db")


@pytest.mark.parametrize("url", ["postgres://u:c@servidor/bd", "postgresql://u:c@servidor/bd"])
def test_database_url_de_postgresql_usa_psycopg(url):
    assert normalizar_url_base_datos(url) == "postgresql+psycopg://u:c@servidor/bd"
