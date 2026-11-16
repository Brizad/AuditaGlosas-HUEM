"""Carga inicial de datos sintéticos: contratos, catálogo de servicios y lote demo.

Se puede ejecutar varias veces sin duplicar nada: lo que ya existe se actualiza
o se deja como está.
"""
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.configuracion import ARCHIVO_CATALOGO, ARCHIVO_CONTRATOS, ARCHIVO_LOTE_DEMO
from app.esquemas import LoteEntrada
from app.modelos import AutorizacionRequerida, Eps, Lote, ServicioCatalogo, SoporteRequerido, Tarifa
from app.servicios.lotes import guardar_lote

NOMBRE_LOTE_DEMO = "Lote de demostración (Sprint 0)"


def leer_json(ruta: Path):
    """Lee un archivo JSON en UTF-8 (acepta el BOM que agregan algunos editores)."""
    with open(ruta, encoding="utf-8-sig") as archivo:
        return json.load(archivo)


def cargar_contratos(sesion: Session, ruta: Path = ARCHIVO_CONTRATOS) -> int:
    """Crea o actualiza las EPS con sus tarifas y los servicios que exigen autorización."""
    contratos = leer_json(ruta)
    for codigo, datos in contratos.items():
        eps = sesion.scalar(select(Eps).where(Eps.codigo == codigo))
        if eps is None:
            eps = Eps(codigo=codigo, nombre=datos["nombre"])
            sesion.add(eps)
        else:
            eps.nombre = datos["nombre"]

        tarifas_actuales = {t.codigo_servicio: t for t in eps.tarifas}
        for codigo_servicio, valor in datos.get("tarifas", {}).items():
            if codigo_servicio in tarifas_actuales:
                tarifas_actuales[codigo_servicio].valor = valor
            else:
                eps.tarifas.append(Tarifa(codigo_servicio=codigo_servicio, valor=valor))

        ya_exigidos = {a.codigo_servicio for a in eps.autorizaciones}
        for codigo_servicio in datos.get("autorizacion", []):
            if codigo_servicio not in ya_exigidos:
                eps.autorizaciones.append(AutorizacionRequerida(codigo_servicio=codigo_servicio))
    sesion.commit()
    return len(contratos)


def cargar_catalogo(sesion: Session, ruta: Path = ARCHIVO_CATALOGO) -> int:
    """Crea o actualiza el catálogo de servicios y los soportes obligatorios por tipo."""
    catalogo = leer_json(ruta)
    for codigo, datos in catalogo["servicios"].items():
        servicio = sesion.get(ServicioCatalogo, codigo)
        if servicio is None:
            sesion.add(ServicioCatalogo(codigo=codigo, descripcion=datos["descripcion"], tipo=datos["tipo"]))
        else:
            servicio.descripcion, servicio.tipo = datos["descripcion"], datos["tipo"]

    existentes = {(s.tipo_servicio, s.nombre_soporte) for s in sesion.scalars(select(SoporteRequerido))}
    for tipo, soportes in catalogo["soportes_requeridos"].items():
        for nombre in soportes:
            if (tipo, nombre) not in existentes:
                sesion.add(SoporteRequerido(tipo_servicio=tipo, nombre_soporte=nombre))
    sesion.commit()
    return len(catalogo["servicios"])


def cargar_lote_demo(sesion: Session, ruta: Path = ARCHIVO_LOTE_DEMO) -> Lote | None:
    """Carga el lote de 12 facturas del Sprint 0. Devuelve None si ya estaba cargado."""
    if sesion.scalar(select(Lote).where(Lote.nombre == NOMBRE_LOTE_DEMO)) is not None:
        return None
    entrada = LoteEntrada(nombre=NOMBRE_LOTE_DEMO, tipo="general", facturas=leer_json(ruta))
    return guardar_lote(sesion, entrada)


def ejecutar_carga_inicial(sesion: Session) -> dict:
    """Ejecuta las tres cargas en orden y devuelve un resumen para mostrar."""
    total_eps = cargar_contratos(sesion)
    total_servicios = cargar_catalogo(sesion)
    lote = cargar_lote_demo(sesion)
    return {
        "eps": total_eps,
        "servicios_catalogo": total_servicios,
        "lote_demo": "cargado" if lote else "ya existía",
        "facturas_lote_demo": len(lote.facturas) if lote else 0,
    }
