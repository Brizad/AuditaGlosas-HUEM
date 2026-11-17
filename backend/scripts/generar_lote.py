"""Generador de lotes sintéticos de facturas con errores conocidos (Fase 7, HU-07).

Para qué sirve: las pruebas y el piloto necesitan muchas facturas, pero el
proyecto NO puede usar datos reales de pacientes (Ley 1581 de 2012). Este
script inventa facturas con la misma estructura del RIPS y les siembra errores
a propósito. Como se sabe qué error tiene cada factura, se puede comprobar que
el motor de reglas los detecta todos (y que no inventa otros).

Uso (desde la carpeta `backend/`):

    python -m scripts.generar_lote
        Genera los dos lotes de demostración en `data/`:
        lote_linea_base_200.json (40 % con errores) y lote_piloto_200.json (15 %).

    python -m scripts.generar_lote --facturas 500 --porcentaje-error 25 \
        --tipo general --periodo 2026-09 --prefijo SEP --semilla 7 --salida ../data/lote_sep.json
        Genera un lote a la medida.

Cada lote sale con un archivo gemelo `..._esperado.json` que dice qué reglas
debe disparar cada factura.

La misma semilla produce siempre el mismo lote: así las pruebas son repetibles.
"""
import argparse
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from app.configuracion import ARCHIVO_CATALOGO, ARCHIVO_CONTRATOS, CARPETA_DATOS
from app.servicios.carga_inicial import leer_json

# ---------------------------------------------------------------------------
# Qué errores se siembran y con qué frecuencia
# ---------------------------------------------------------------------------
# regla -> peso (qué tan frecuente es ese error entre las facturas con error).
# Los soportes y las autorizaciones pesan más porque son las causas más comunes de glosa.
PESOS_DE_ERROR = {
    "SO-01": 24,   # falta el soporte obligatorio
    "TA-01": 20,   # valor distinto a la tarifa pactada
    "AU-01": 16,   # falta el número de autorización
    "FA-02": 10,   # el total no coincide con la suma del RIPS
    "FA-03": 10,   # código de la factura distinto al del RIPS
    "FA-04": 8,    # código mal escrito
    "TA-02": 7,    # servicio sin tarifa pactada
    "FA-01": 5,    # el RIPS es de otra factura
}
# Errores que pueden ir juntos en una misma factura sin estorbarse entre sí.
# (FA-04 y TA-02 van siempre solos: cambian el código y eso apagaría otras reglas.)
COMBINABLES = ("SO-01", "TA-01", "AU-01", "FA-01", "FA-02", "FA-03")
PROBABILIDAD_DE_DOS_ERRORES = 0.15

# Código bien escrito que ninguna EPS de prueba tiene pactado (para TA-02).
CODIGO_SIN_TARIFA = "890701"
VALOR_CODIGO_SIN_TARIFA = 45000

TIPO_CONSULTA, TIPO_MEDICAMENTO = "consulta", "medicamento"


@dataclass
class Linea:
    """Un servicio prestado: se cobra en la factura y se reporta en el RIPS."""

    codigo_rips: str
    codigo_factura: str
    tipo: str | None            # consulta, laboratorio, imagen, medicamento (None si no está en el catálogo)
    cantidad: int
    valor_unitario: float
    autorizacion: str | None = None
    nombre: str | None = None

    @property
    def valor(self) -> float:
        return self.cantidad * self.valor_unitario


@dataclass
class Plan:
    """Una factura todavía sin convertir a JSON. Los errores se siembran sobre el plan."""

    numero: str
    eps: str
    fecha: str
    lineas: list[Linea] = field(default_factory=list)
    soportes: list[str] = field(default_factory=list)
    numero_rips: str = ""
    ajuste_total: float = 0.0       # lo que se le suma al total para descuadrarlo (FA-02)
    errores: list[str] = field(default_factory=list)


class Generador:
    """Arma facturas sintéticas a partir de los contratos y el catálogo de `data/`."""

    def __init__(self, contratos: dict, catalogo: dict, semilla: int):
        self.contratos = contratos
        self.servicios = catalogo["servicios"]
        self.soportes_requeridos = catalogo["soportes_requeridos"]
        self.azar = random.Random(semilla)

    # --- Datos del catálogo y del contrato ---------------------------------
    def _tipo(self, codigo: str) -> str | None:
        return self.servicios.get(codigo, {}).get("tipo")

    def _exige_soporte(self, codigo: str) -> bool:
        return bool(self.soportes_requeridos.get(self._tipo(codigo), []))

    def _eps_que_exigen_autorizacion(self) -> list[str]:
        return [codigo for codigo, datos in self.contratos.items() if datos.get("autorizacion")]

    # --- Construcción de una factura correcta --------------------------------
    def _linea(self, eps: str, codigo: str) -> Linea:
        """Línea correcta: valor pactado, y número de autorización si la EPS lo exige."""
        contrato = self.contratos[eps]
        tipo = self._tipo(codigo)
        es_medicamento = tipo == TIPO_MEDICAMENTO
        return Linea(
            codigo_rips=codigo, codigo_factura=codigo, tipo=tipo,
            cantidad=self.azar.choice([10, 14, 20, 21, 30]) if es_medicamento else 1,
            valor_unitario=contrato["tarifas"][codigo],
            autorizacion=f"AUT-{self.azar.randrange(100000, 999999)}" if codigo in contrato.get("autorizacion", []) else None,
            nombre=self.servicios[codigo]["descripcion"] if es_medicamento else None,
        )

    def _plan_correcto(self, numero: str, eps: str, fecha: str, errores: list[str]) -> Plan:
        """Factura sin errores, pero con los servicios que harán falta para sembrar los errores pedidos."""
        contrato = self.contratos[eps]
        pactados = sorted(contrato["tarifas"])
        codigos = self.azar.sample(pactados, k=min(len(pactados), self.azar.choice([1, 1, 2, 2, 3])))

        def asegurar(condicion):
            """Si ningún servicio elegido cumple la condición, agrega uno que sí la cumpla."""
            if not any(condicion(codigo) for codigo in codigos):
                codigos.append(self.azar.choice([codigo for codigo in pactados if condicion(codigo)]))

        if "AU-01" in errores:
            asegurar(lambda codigo: codigo in contrato["autorizacion"])
        if "SO-01" in errores:
            asegurar(self._exige_soporte)
        if "FA-03" in errores or "FA-04" in errores:
            asegurar(lambda codigo: self._tipo(codigo) != TIPO_MEDICAMENTO)

        plan = Plan(numero=numero, eps=eps, fecha=fecha, numero_rips=numero, errores=sorted(errores))
        plan.lineas = [self._linea(eps, codigo) for codigo in codigos]
        return plan

    # --- Siembra de errores (cada función dispara UNA sola regla) ----------
    def _sembrar(self, plan: Plan, regla: str, posicion: int) -> None:
        no_medicamentos = [linea for linea in plan.lineas if linea.tipo != TIPO_MEDICAMENTO]

        if regla == "FA-01":
            # El RIPS trae el número de otra factura.
            plan.numero_rips = f"{plan.numero.split('-')[0]}-{9000 + posicion}"

        elif regla == "FA-02":
            # El total de la factura queda por encima de lo que suma el RIPS.
            plan.ajuste_total = self.azar.choice([1000, 2000, 2500, 5000])

        elif regla == "FA-03":
            # En la factura se digita un código distinto al del RIPS (se cambia el último dígito).
            linea = self.azar.choice(no_medicamentos)
            usados = {otra.codigo_rips for otra in plan.lineas} | set(self.servicios)
            for salto in range(1, 10):
                nuevo = linea.codigo_rips[:-1] + str((int(linea.codigo_rips[-1]) + salto) % 10)
                if nuevo not in usados:
                    linea.codigo_factura = nuevo
                    break

        elif regla == "FA-04":
            # El código queda con 5 caracteres en la factura y en el RIPS.
            linea = self.azar.choice(no_medicamentos)
            linea.codigo_rips = linea.codigo_factura = linea.codigo_rips[:5]

        elif regla == "TA-01":
            # Se cobra por encima de la tarifa pactada.
            linea = self.azar.choice(plan.lineas)
            es_medicamento = linea.tipo == TIPO_MEDICAMENTO
            linea.valor_unitario += self.azar.choice([20, 50, 100]) if es_medicamento else self.azar.choice([2000, 3500, 5000])

        elif regla == "TA-02":
            # Se agrega un servicio bien codificado que la EPS no tiene pactado.
            plan.lineas.append(Linea(
                codigo_rips=CODIGO_SIN_TARIFA, codigo_factura=CODIGO_SIN_TARIFA, tipo=None,
                cantidad=1, valor_unitario=VALOR_CODIGO_SIN_TARIFA,
            ))

        elif regla == "AU-01":
            # Se borra el número de autorización de los servicios que lo exigen.
            for linea in plan.lineas:
                linea.autorizacion = None

    def _soportes(self, plan: Plan) -> list[str]:
        """Soportes que exige cada servicio; ninguno si a la factura le toca el error SO-01."""
        if "SO-01" in plan.errores:
            return []
        soportes: list[str] = []
        for linea in plan.lineas:
            for nombre in self.soportes_requeridos.get(self._tipo(linea.codigo_rips), []):
                if nombre not in soportes:
                    soportes.append(nombre)
        return soportes

    # --- Conversión al JSON del RIPS ---------------------------------------
    def _a_json(self, plan: Plan, posicion: int) -> dict:
        servicios: dict[str, list] = {}
        for linea in plan.lineas:
            if linea.tipo == TIPO_MEDICAMENTO:
                servicios.setdefault("medicamentos", []).append({
                    "codTecnologiaSalud": linea.codigo_rips, "nomTecnologiaSalud": linea.nombre,
                    "cantidadMedicamento": linea.cantidad, "vrUnitMedicamento": linea.valor_unitario,
                    "vrServicio": linea.valor, "numAutorizacion": linea.autorizacion,
                })
            elif linea.tipo in (TIPO_CONSULTA, None):
                servicios.setdefault("consultas", []).append({
                    "codConsulta": linea.codigo_rips, "vrServicio": linea.valor, "numAutorizacion": linea.autorizacion,
                })
            else:   # laboratorio e imagen son procedimientos
                servicios.setdefault("procedimientos", []).append({
                    "codProcedimiento": linea.codigo_rips, "vrServicio": linea.valor,
                    "numAutorizacion": linea.autorizacion,
                })
        return {
            "numFactura": plan.numero,
            "eps": plan.eps,
            "fechaExpedicion": plan.fecha,
            "valorTotal": sum(linea.valor for linea in plan.lineas) + plan.ajuste_total,
            "items": [
                {"codigo": linea.codigo_factura, "cantidad": linea.cantidad, "valorUnitario": linea.valor_unitario}
                for linea in plan.lineas
            ],
            "soportes": plan.soportes,
            "rips": {
                "numDocumentoIdObligado": "800000000",
                "numFactura": plan.numero_rips,
                "tipoNota": None,
                "numNota": None,
                "usuarios": [{
                    # Documento inventado y marcado como sintético: no corresponde a ninguna persona.
                    "tipoDocumentoIdentificacion": "CC",
                    "numDocumentoIdentificacion": f"SINT{posicion:06d}",
                    "tipoUsuario": "01",
                    "servicios": servicios,
                }],
            },
        }

    # --- Lote completo ---------------------------------------------------------
    def _elegir_errores(self) -> list[str]:
        reglas, pesos = list(PESOS_DE_ERROR), list(PESOS_DE_ERROR.values())
        primero = self.azar.choices(reglas, weights=pesos)[0]
        errores = [primero]
        if primero in COMBINABLES and self.azar.random() < PROBABILIDAD_DE_DOS_ERRORES:
            segundo = self.azar.choice([regla for regla in COMBINABLES if regla != primero])
            errores.append(segundo)
        return errores

    def generar(self, cantidad: int, porcentaje_error: float, periodo: str, prefijo: str) -> tuple[list[dict], dict]:
        """Devuelve (facturas, esperado). `esperado` dice qué reglas debe disparar cada factura."""
        con_error = round(cantidad * porcentaje_error / 100)
        posiciones_con_error = set(self.azar.sample(range(1, cantidad + 1), k=con_error))
        todas_las_eps = sorted(self.contratos)
        ancho = max(4, len(str(cantidad)))

        facturas, reglas_por_factura = [], {}
        for posicion in range(1, cantidad + 1):
            errores = self._elegir_errores() if posicion in posiciones_con_error else []
            # AU-01 solo se puede sembrar en una EPS que exija autorizaciones.
            candidatas = self._eps_que_exigen_autorizacion() if "AU-01" in errores else todas_las_eps
            numero = f"{prefijo}-{posicion:0{ancho}d}"
            fecha = f"{periodo}-{1 + (posicion - 1) * 28 // cantidad:02d}"   # repartidas del día 1 al 28

            plan = self._plan_correcto(numero, self.azar.choice(candidatas), fecha, errores)
            for regla in plan.errores:
                self._sembrar(plan, regla, posicion)
            plan.soportes = self._soportes(plan)

            facturas.append(self._a_json(plan, posicion))
            if plan.errores:
                reglas_por_factura[numero] = plan.errores

        por_regla = {regla: 0 for regla in sorted(PESOS_DE_ERROR)}
        for reglas in reglas_por_factura.values():
            for regla in reglas:
                por_regla[regla] += 1
        esperado = {
            "total_facturas": cantidad,
            "con_inconsistencias": con_error,
            "aptas": cantidad - con_error,
            "porcentaje_con_inconsistencias": round(100 * con_error / cantidad, 1),
            "facturas_por_regla": por_regla,
            "reglas_por_factura": reglas_por_factura,
        }
        return facturas, esperado


# ---------------------------------------------------------------------------
# Archivos
# ---------------------------------------------------------------------------
def escribir_json(ruta: Path, contenido) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="\n") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=1)
        archivo.write("\n")


def generar_lote(
    cantidad: int, porcentaje_error: float, semilla: int, periodo: str, prefijo: str, nombre: str, tipo: str,
) -> tuple[dict, dict]:
    """Genera un lote listo para cargar y su archivo de resultados esperados."""
    if cantidad < 1 or cantidad > 5000:
        raise ValueError("La cantidad de facturas debe estar entre 1 y 5000.")
    if not 0 <= porcentaje_error <= 100:
        raise ValueError("El porcentaje de facturas con error debe estar entre 0 y 100.")

    generador = Generador(leer_json(ARCHIVO_CONTRATOS), leer_json(ARCHIVO_CATALOGO), semilla)
    facturas, esperado = generador.generar(cantidad, porcentaje_error, periodo, prefijo)
    # El archivo trae nombre, tipo y periodo: se puede cargar tal cual por la página o por la API.
    lote = {"nombre": nombre, "tipo": tipo, "periodo": periodo, "facturas": facturas}
    esperado = {
        "descripcion": "Reglas que debe disparar cada factura del lote. Datos sintéticos (Ley 1581 de 2012).",
        "lote": nombre, "tipo": tipo, "periodo": periodo, "semilla": semilla, **esperado,
    }
    return lote, esperado


def ruta_del_esperado(ruta_lote: Path) -> Path:
    return ruta_lote.with_name(ruta_lote.stem + "_esperado.json")


# Los dos lotes de demostración que se guardan en `data/`.
LOTES_DE_DEMOSTRACION = [
    {
        "archivo": "lote_linea_base_200.json", "cantidad": 200, "porcentaje_error": 40, "semilla": 2284,
        "periodo": "2026-07", "prefijo": "LB", "nombre": "Línea base sintética (200 facturas)", "tipo": "linea_base",
    },
    {
        "archivo": "lote_piloto_200.json", "cantidad": 200, "porcentaje_error": 15, "semilla": 2275,
        "periodo": "2026-08", "prefijo": "PI", "nombre": "Piloto sintético (200 facturas)", "tipo": "piloto",
    },
]


def guardar(ruta: Path, lote: dict, esperado: dict) -> None:
    escribir_json(ruta, lote)
    escribir_json(ruta_del_esperado(ruta), esperado)
    print(f"  {ruta.name}: {esperado['total_facturas']} facturas, "
          f"{esperado['con_inconsistencias']} con errores sembrados ({esperado['porcentaje_con_inconsistencias']} %)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera lotes sintéticos de facturas con errores conocidos.")
    parser.add_argument("--facturas", type=int, help="Cantidad de facturas (1 a 5000).")
    parser.add_argument("--porcentaje-error", type=float, default=30, help="Porcentaje de facturas con error (0 a 100).")
    parser.add_argument("--semilla", type=int, default=1, help="Misma semilla = mismo lote.")
    parser.add_argument("--periodo", default="2026-09", help="Mes de las facturas, AAAA-MM.")
    parser.add_argument("--prefijo", default="FS", help="Prefijo del número de factura.")
    parser.add_argument("--tipo", default="general", choices=["general", "linea_base", "piloto"])
    parser.add_argument("--nombre", help="Nombre del lote.")
    parser.add_argument("--salida", type=Path, help="Archivo .json de salida.")
    opciones = parser.parse_args()

    if opciones.facturas is None:
        print("Generando los lotes de demostración en data/:")
        for definicion in LOTES_DE_DEMOSTRACION:
            parametros = {clave: valor for clave, valor in definicion.items() if clave != "archivo"}
            guardar(CARPETA_DATOS / definicion["archivo"], *generar_lote(**parametros))
        return

    salida = opciones.salida or CARPETA_DATOS / f"lote_{opciones.prefijo.lower()}_{opciones.facturas}.json"
    nombre = opciones.nombre or f"Lote sintético {opciones.prefijo} ({opciones.facturas} facturas)"
    print("Generando lote a la medida:")
    guardar(salida, *generar_lote(
        cantidad=opciones.facturas, porcentaje_error=opciones.porcentaje_error, semilla=opciones.semilla,
        periodo=opciones.periodo, prefijo=opciones.prefijo, nombre=nombre, tipo=opciones.tipo,
    ))


if __name__ == "__main__":
    main()
