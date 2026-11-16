"""Prueba z de diferencia de dos proporciones (HU-07).

Sirve para responder con respaldo estadístico la pregunta del piloto:
«¿la proporción de facturas glosadas bajó de verdad, o la diferencia pudo
darse por azar?».

Se comparan dos grupos independientes:
    grupo 1 = línea base (antes de usar el sistema)
    grupo 2 = piloto     (usando el sistema)

Fórmulas (son las del curso de estadística; no se usa ninguna librería externa):
    p1 = x1 / n1                     proporción glosada en la línea base
    p2 = x2 / n2                     proporción glosada en el piloto
    p  = (x1 + x2) / (n1 + n2)       proporción combinada (bajo H0 son iguales)
    EE = raíz( p (1 - p) (1/n1 + 1/n2) )   error estándar
    z  = (p1 - p2) / EE

Este archivo no conoce la base de datos: recibe cuatro números y devuelve el
resultado, por eso se puede probar contra un cálculo hecho a mano.
"""
import math
from dataclasses import dataclass, field
from statistics import NormalDist

# Hipótesis alternativas que se pueden probar.
HIPOTESIS_REDUCE = "reduce"        # H1: p_piloto < p_linea_base (una cola). Es la del proyecto.
HIPOTESIS_DIFERENTE = "diferente"  # H1: p_piloto ≠ p_linea_base (dos colas).
HIPOTESIS = (HIPOTESIS_REDUCE, HIPOTESIS_DIFERENTE)

ALFA_POR_DEFECTO = 0.05
# La aproximación normal es confiable si en cada grupo se esperan al menos
# 5 facturas glosadas y 5 no glosadas.
MINIMO_ESPERADO = 5

_NORMAL = NormalDist()   # distribución normal estándar (media 0, desviación 1)


@dataclass(frozen=True)
class ResultadoPruebaZ:
    """Todo lo que se muestra en la pantalla de línea base."""

    total_linea_base: int
    glosadas_linea_base: int
    proporcion_linea_base: float      # p1 (entre 0 y 1)
    total_piloto: int
    glosadas_piloto: int
    proporcion_piloto: float          # p2 (entre 0 y 1)
    diferencia: float                 # p1 - p2 (positiva si el piloto bajó la proporción)
    proporcion_combinada: float       # p
    error_estandar: float             # EE
    z: float
    valor_p: float
    alfa: float
    hipotesis: str
    valor_critico: float              # z a partir del cual se rechaza H0
    se_rechaza_h0: bool
    intervalo_inferior: float         # intervalo de confianza de la diferencia
    intervalo_superior: float
    nivel_confianza: float            # 1 - alfa
    supuestos_cumplidos: bool         # ¿las muestras son suficientemente grandes?
    interpretacion: str
    advertencias: list[str] = field(default_factory=list)


def cola_superior(z: float) -> float:
    """Probabilidad de que una normal estándar sea mayor que z: P(Z > z).

    Se calcula con la función de error complementaria (`math.erfc`), que
    conserva la precisión cuando z es grande y la probabilidad es muy pequeña.
    """
    return 0.5 * math.erfc(z / math.sqrt(2))


def _porcentaje(proporcion: float) -> str:
    """0.4 -> «40,0 %» (con coma decimal, como se escribe en español)."""
    return f"{100 * proporcion:.1f}".replace(".", ",") + " %"


def _decimal(valor: float, decimales: int = 2) -> str:
    return f"{valor:.{decimales}f}".replace(".", ",")


def _texto_valor_p(valor_p: float) -> str:
    return "valor p < 0,001" if valor_p < 0.001 else f"valor p = {_decimal(valor_p, 3)}"


def _interpretar(p1: float, p2: float, z: float, valor_p: float, alfa: float, hipotesis: str, rechaza: bool) -> str:
    """Redacta la conclusión en español sencillo."""
    cifras = f"(z = {_decimal(z)}; {_texto_valor_p(valor_p)})"
    nivel = f"Con un nivel de significancia de {_decimal(alfa)}"
    base, piloto = _porcentaje(p1), _porcentaje(p2)

    if hipotesis == HIPOTESIS_REDUCE:
        if rechaza:
            return (
                f"{nivel} se rechaza la hipótesis nula: la proporción de facturas glosadas en el piloto ({piloto}) "
                f"es significativamente menor que en la línea base ({base}) {cifras}. "
                "La reducción no se explica por el azar."
            )
        if p2 >= p1:
            return (
                f"{nivel} no se rechaza la hipótesis nula: la proporción del piloto ({piloto}) no es menor que la "
                f"de la línea base ({base}) {cifras}. No hay evidencia de que el piloto haya reducido las glosas."
            )
        return (
            f"{nivel} no se rechaza la hipótesis nula: aunque la proporción bajó de {base} a {piloto}, la diferencia "
            f"no es estadísticamente significativa {cifras}. Con estas cantidades de facturas la reducción "
            "podría deberse al azar."
        )

    if rechaza:
        sentido = "menor" if p2 < p1 else "mayor"
        return (
            f"{nivel} se rechaza la hipótesis nula: la proporción de facturas glosadas en el piloto ({piloto}) es "
            f"significativamente {sentido} que en la línea base ({base}) {cifras}."
        )
    return (
        f"{nivel} no se rechaza la hipótesis nula: no hay diferencia estadísticamente significativa entre la "
        f"línea base ({base}) y el piloto ({piloto}) {cifras}."
    )


def prueba_z_dos_proporciones(
    glosadas_linea_base: int,
    total_linea_base: int,
    glosadas_piloto: int,
    total_piloto: int,
    alfa: float = ALFA_POR_DEFECTO,
    hipotesis: str = HIPOTESIS_REDUCE,
) -> ResultadoPruebaZ:
    """Compara la proporción de facturas glosadas de la línea base contra la del piloto.

    H0: las dos proporciones son iguales.
    H1: la del piloto es menor (`reduce`) o simplemente distinta (`diferente`).
    Se rechaza H0 cuando el valor p es menor que alfa.
    """
    for nombre, glosadas, total in (
        ("línea base", glosadas_linea_base, total_linea_base),
        ("piloto", glosadas_piloto, total_piloto),
    ):
        if total <= 0:
            raise ValueError(f"El total de facturas de {nombre} debe ser mayor que cero.")
        if not 0 <= glosadas <= total:
            raise ValueError(f"Las facturas glosadas de {nombre} deben estar entre 0 y el total ({total}).")
    if not 0 < alfa < 1:
        raise ValueError("El nivel de significancia (alfa) debe estar entre 0 y 1.")
    if hipotesis not in HIPOTESIS:
        raise ValueError(f"Hipótesis desconocida: {hipotesis}.")

    n1, x1, n2, x2 = total_linea_base, glosadas_linea_base, total_piloto, glosadas_piloto
    p1, p2 = x1 / n1, x2 / n2
    combinada = (x1 + x2) / (n1 + n2)
    error_estandar = math.sqrt(combinada * (1 - combinada) * (1 / n1 + 1 / n2))
    advertencias: list[str] = []

    if error_estandar == 0:
        # Pasa cuando en los dos grupos todas (o ninguna) de las facturas están glosadas:
        # no hay variación, así que no hay nada que comparar.
        z, valor_p = 0.0, 1.0
        advertencias.append(
            "Las dos proporciones son iguales y no hay variación entre los grupos; la prueba no puede detectar diferencias."
        )
    else:
        z = (p1 - p2) / error_estandar
        valor_p = cola_superior(z) if hipotesis == HIPOTESIS_REDUCE else 2 * cola_superior(abs(z))
        valor_p = min(1.0, valor_p)

    # Valor crítico: z que deja alfa (una cola) o alfa/2 (dos colas) a la derecha.
    valor_critico = _NORMAL.inv_cdf(1 - alfa) if hipotesis == HIPOTESIS_REDUCE else _NORMAL.inv_cdf(1 - alfa / 2)
    se_rechaza = valor_p < alfa

    # Intervalo de confianza de la diferencia (aquí cada grupo usa su propia proporción).
    margen = _NORMAL.inv_cdf(1 - alfa / 2) * math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    diferencia = p1 - p2

    esperados = [n1 * combinada, n1 * (1 - combinada), n2 * combinada, n2 * (1 - combinada)]
    supuestos = min(esperados) >= MINIMO_ESPERADO
    if not supuestos:
        advertencias.append(
            "Las muestras son pequeñas para la aproximación normal (se esperan menos de 5 facturas en alguna "
            "categoría). Tome el resultado como orientativo y, si puede, use más facturas."
        )

    return ResultadoPruebaZ(
        total_linea_base=n1, glosadas_linea_base=x1, proporcion_linea_base=p1,
        total_piloto=n2, glosadas_piloto=x2, proporcion_piloto=p2,
        diferencia=diferencia, proporcion_combinada=combinada, error_estandar=error_estandar,
        z=z, valor_p=valor_p, alfa=alfa, hipotesis=hipotesis, valor_critico=valor_critico,
        se_rechaza_h0=se_rechaza,
        intervalo_inferior=max(-1.0, diferencia - margen), intervalo_superior=min(1.0, diferencia + margen),
        nivel_confianza=1 - alfa, supuestos_cumplidos=supuestos,
        interpretacion=_interpretar(p1, p2, z, valor_p, alfa, hipotesis, se_rechaza),
        advertencias=advertencias,
    )
