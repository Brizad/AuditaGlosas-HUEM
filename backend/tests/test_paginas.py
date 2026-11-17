"""Páginas del frontend servidas por FastAPI y cabeceras de seguridad (Fase 5)."""
import re

import pytest

from app.configuracion import CARPETA_FRONTEND
from app.rutas.paginas import PAGINAS

ARCHIVOS_HTML = sorted(CARPETA_FRONTEND.glob("*.html"))
ARCHIVOS_JS = sorted((CARPETA_FRONTEND / "js").glob("*.js"))


@pytest.mark.parametrize("direccion", sorted(PAGINAS))
def test_cada_pagina_responde_con_html_y_cabeceras_de_seguridad(cliente, direccion):
    respuesta = cliente.get(direccion)
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
    assert "<title>" in respuesta.text and "AuditaGlosas HUEM" in respuesta.text
    politica = respuesta.headers["content-security-policy"]
    assert "script-src 'self'" in politica and "style-src 'self'" in politica
    assert respuesta.headers["x-content-type-options"] == "nosniff"
    assert respuesta.headers["x-frame-options"] == "DENY"


def test_todas_las_paginas_html_tienen_su_ruta():
    assert {archivo.name for archivo in ARCHIVOS_HTML} == set(PAGINAS.values())


def test_los_archivos_estaticos_se_sirven(cliente):
    estilos = cliente.get("/static/css/estilos.css")
    assert estilos.status_code == 200 and "text/css" in estilos.headers["content-type"]
    comun = cliente.get("/static/js/comun.js")
    assert comun.status_code == 200 and "javascript" in comun.headers["content-type"]
    assert cliente.get("/static/img/favicon.svg").status_code == 200
    assert cliente.get("/static/js/no-existe.js").status_code == 404


def test_la_documentacion_no_lleva_la_politica_estricta(cliente):
    """/docs carga sus archivos desde internet; con la política estricta no funcionaría."""
    assert "content-security-policy" not in cliente.get("/docs").headers
    assert "content-security-policy" in cliente.get("/api/salud").headers


@pytest.mark.parametrize("archivo", ARCHIVOS_HTML, ids=lambda archivo: archivo.name)
def test_el_html_cumple_la_politica_de_seguridad(archivo):
    """Sin estilos ni scripts dentro del HTML, y todo lo que enlaza existe en la carpeta."""
    html = archivo.read_text(encoding="utf-8")
    assert not re.search(r"\sstyle\s*=", html), "No se permiten estilos en línea (style=...)."
    assert not re.search(r"\son[a-z]+\s*=", html), "No se permiten eventos en línea (onclick=...)."
    assert not re.search(r"<script(?![^>]*\ssrc=)", html), "Los scripts deben ir en archivos aparte."
    assert 'lang="es"' in html and 'name="viewport"' in html

    for enlace in re.findall(r'(?:src|href)="(/static/[^"]+)"', html):
        assert (CARPETA_FRONTEND / enlace.removeprefix("/static/")).is_file(), f"No existe {enlace}"
    for enlace in re.findall(r'href="(/[a-z-]*)"', html):
        assert enlace in PAGINAS or enlace == "/docs", f"Enlace a una página que no existe: {enlace}"


@pytest.mark.parametrize("archivo", ARCHIVOS_HTML + ARCHIVOS_JS, ids=lambda archivo: archivo.name)
def test_los_patrones_de_los_formularios_son_validos_en_el_navegador(archivo):
    """El navegador exige escapar el guion dentro de [ ]; si no, ignora el patrón sin avisar."""
    texto = archivo.read_text(encoding="utf-8")
    for patron in re.findall(r'pattern(?:=|:\s*)"([^"]+)"', texto):
        assert not re.search(r"(?<!\\)-\]", patron), f"Guion sin escapar en el patrón {patron}"


@pytest.mark.parametrize("archivo", ARCHIVOS_JS, ids=lambda archivo: archivo.name)
def test_el_javascript_no_escribe_html_con_datos(archivo):
    """Los datos se escriben con textContent (función h), nunca con innerHTML: evita XSS."""
    codigo = archivo.read_text(encoding="utf-8")
    # Se quitan los comentarios: pueden nombrar estas funciones para explicar por qué no se usan.
    sin_comentarios = re.sub(r"/\*.*?\*/", "", codigo, flags=re.DOTALL)
    sin_comentarios = re.sub(r"^\s*//.*$", "", sin_comentarios, flags=re.MULTILINE)
    for prohibido in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert prohibido not in sin_comentarios, f"{archivo.name} usa {prohibido}"

    for modulo in re.findall(r'from "\./([^"]+)"', codigo):
        assert (archivo.parent / modulo).is_file(), f"{archivo.name} importa un archivo que no existe: {modulo}"
