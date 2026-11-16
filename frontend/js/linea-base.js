/* Página «Línea base y piloto»: porcentaje de facturas glosadas y prueba z (HU-07). */
import { api, h, poner, porId, iniciar, avisar, vacio, cajaDeError, numero, porcentaje, periodoLegible, contar } from "./comun.js";
import { barras, columnas } from "./graficas.js";

let porTipo = {};   // cifras de los lotes de cada tipo: { linea_base: {...}, piloto: {...} }

/** Número con decimales fijos y coma decimal: 5.599 -> "5,60". */
const decimal = (valor, decimales = 2) =>
  valor.toLocaleString("es-CO", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
const valorP = (valor) => (valor < 0.001 ? "< 0,001" : decimal(valor, 3));

// ---------------------------------------------------------------------
// Indicador: tarjetas, por periodo y por causal
// ---------------------------------------------------------------------
function tarjetaDeTipo(prefijo, cifras) {
  const hay = cifras && cifras.validadas > 0;
  porId(prefijo).textContent = hay ? porcentaje(cifras.porcentaje_glosadas) : "—";
  porId(prefijo + "-nota").textContent = hay
    ? `${numero(cifras.glosadas)} de ${numero(cifras.validadas)} facturas · ${numero(cifras.lotes)}${contar(cifras.lotes, " lote", " lotes")}`
    : "Sin lotes validados de este tipo";
}

function tablaPeriodos(filas) {
  return h("div", { class: "tabla-envoltura" }, h("table", null,
    h("thead", null, h("tr", null,
      h("th", null, "Periodo"), h("th", { class: "numero" }, "Validadas"),
      h("th", { class: "numero" }, "Glosadas"), h("th", { class: "numero" }, "% glosadas"))),
    h("tbody", null, filas.map((fila) => h("tr", null,
      h("td", null, periodoLegible(fila.periodo)),
      h("td", { class: "numero" }, numero(fila.validadas)),
      h("td", { class: "numero" }, numero(fila.glosadas)),
      h("td", { class: "numero" }, h("b", null, porcentaje(fila.porcentaje_glosadas))))))));
}

function tablaCausales(grupos) {
  const filas = [];
  for (const grupo of grupos) {
    filas.push(h("tr", null,
      h("td", null, h("b", null, `${grupo.grupo} · ${grupo.nombre_grupo}`)),
      h("td", { class: "numero" }, numero(grupo.facturas_afectadas)),
      h("td", { class: "numero" }, h("b", null, porcentaje(grupo.porcentaje_facturas)))));
    for (const regla of grupo.reglas) {
      filas.push(h("tr", { class: "subfila" },
        h("td", null, h("span", { class: "regla" }, regla.codigo), regla.nombre),
        h("td", { class: "numero" }, numero(regla.facturas_afectadas)),
        h("td", { class: "numero" }, porcentaje(regla.porcentaje_facturas))));
    }
  }
  return h("div", { class: "tabla-envoltura" }, h("table", null,
    h("thead", null, h("tr", null,
      h("th", null, "Causal y regla"), h("th", { class: "numero" }, "Facturas"), h("th", { class: "numero" }, "% de las validadas"))),
    h("tbody", null, filas)));
}

async function mostrarIndicador() {
  const tipo = porId("f-tipo").value;
  const datos = await api("/indicadores/glosas" + (tipo ? `?tipo=${tipo}` : ""));
  porTipo = Object.fromEntries(datos.por_tipo.map((fila) => [fila.tipo, fila]));

  const total = datos.total;
  porId("k-validadas").textContent = numero(total.validadas);
  porId("k-validadas-nota").textContent = `${numero(total.glosadas)} con inconsistencias`;
  porId("k-porcentaje").textContent = total.validadas ? porcentaje(total.porcentaje_glosadas) : "—";
  porId("k-porcentaje-nota").textContent = total.validadas ? "de las facturas validadas" : "Aún no hay facturas validadas";
  tarjetaDeTipo("k-base", porTipo.linea_base);
  tarjetaDeTipo("k-piloto", porTipo.piloto);

  if (!total.validadas) {
    const mensaje = () => vacio("Sin facturas validadas", "Cargue y valide un lote para ver el indicador.",
      h("a", { class: "boton primario", href: "/carga" }, "Cargar un lote"));
    poner(porId("g-periodos"), mensaje()); poner(porId("t-periodos"));
    poner(porId("g-causales"), mensaje()); poner(porId("t-causales"));
    return;
  }

  const periodos = datos.por_periodo.filter((fila) => fila.validadas > 0);
  columnas(porId("g-periodos"), periodos.map((fila) => ({
    etiqueta: periodoLegible(fila.periodo),
    valor: fila.porcentaje_glosadas,
    globo: `${periodoLegible(fila.periodo)}\n${numero(fila.glosadas)} de ${numero(fila.validadas)} facturas glosadas (${porcentaje(fila.porcentaje_glosadas)})`,
  })), "Porcentaje de facturas glosadas por periodo");
  poner(porId("t-periodos"), tablaPeriodos(periodos));

  barras(porId("g-causales"), datos.por_causal.map((grupo) => ({
    codigo: grupo.grupo,
    nombre: grupo.nombre_grupo,
    valor: grupo.porcentaje_facturas,
    cifra: h("b", null, porcentaje(grupo.porcentaje_facturas)),
    globo: `${grupo.nombre_grupo}\n${numero(grupo.facturas_afectadas)} de ${numero(total.validadas)} facturas (${porcentaje(grupo.porcentaje_facturas)})`,
  })));
  poner(porId("t-causales"), tablaCausales(datos.por_causal));
}

// ---------------------------------------------------------------------
// Prueba z
// ---------------------------------------------------------------------
const CAMPOS = {
  baseTotal: "z-base-total", baseGlosadas: "z-base-glosadas",
  pilotoTotal: "z-piloto-total", pilotoGlosadas: "z-piloto-glosadas",
};

/** Copia en el formulario las cifras de los lotes marcados como línea base y piloto. */
function usarLotes() {
  const base = porTipo.linea_base, piloto = porTipo.piloto;
  const hayBase = base?.validadas > 0, hayPiloto = piloto?.validadas > 0;
  if (hayBase) { porId(CAMPOS.baseTotal).value = base.validadas; porId(CAMPOS.baseGlosadas).value = base.glosadas; }
  if (hayPiloto) { porId(CAMPOS.pilotoTotal).value = piloto.validadas; porId(CAMPOS.pilotoGlosadas).value = piloto.glosadas; }

  const falta = [!hayBase && "línea base", !hayPiloto && "piloto"].filter(Boolean);
  porId("z-origen").textContent = falta.length
    ? `No hay lotes validados de tipo ${falta.join(" ni de ")}: digite esas cifras o cargue un lote indicando su tipo.`
    : "Cifras tomadas de los lotes validados de línea base y de piloto. Puede cambiarlas para probar otros escenarios.";
  return hayBase && hayPiloto;
}

/** Lee un campo que debe ser un número entero; devuelve null si no lo es. */
function entero(id) {
  const texto = porId(id).value.trim();
  return /^\d+$/.test(texto) ? Number(texto) : null;
}

function leerFormulario() {
  const baseTotal = entero(CAMPOS.baseTotal), baseGlosadas = entero(CAMPOS.baseGlosadas);
  const pilotoTotal = entero(CAMPOS.pilotoTotal), pilotoGlosadas = entero(CAMPOS.pilotoGlosadas);
  if ([baseTotal, baseGlosadas, pilotoTotal, pilotoGlosadas].includes(null)) throw new Error("Escriba las cuatro cifras con números enteros.");
  if (baseTotal < 1 || pilotoTotal < 1) throw new Error("El total de facturas de cada grupo debe ser mayor que cero.");
  if (baseGlosadas > baseTotal || pilotoGlosadas > pilotoTotal) throw new Error("Las facturas glosadas no pueden ser más que el total de su grupo.");
  return {
    linea_base: { total_facturas: baseTotal, facturas_glosadas: baseGlosadas },
    piloto: { total_facturas: pilotoTotal, facturas_glosadas: pilotoGlosadas },
    alfa: Number(porId("z-alfa").value),
    hipotesis: porId("z-hipotesis").value,
  };
}

function dato(rotulo, valor, nota) {
  return h("div", null, h("dt", null, rotulo), h("dd", null, valor), nota ? h("span", { class: "apoyo" }, nota) : null);
}

function mostrarResultado(r) {
  const unaCola = r.hipotesis === "reduce";
  const confianza = porcentaje(100 * r.nivel_confianza);
  const titulo = r.se_rechaza_h0
    ? (unaCola ? "Se rechaza H0: la reducción es estadísticamente significativa." : "Se rechaza H0: las proporciones son distintas.")
    : "No se rechaza H0: la diferencia no es estadísticamente significativa.";

  const comparacion = h("div");
  columnas(comparacion, [
    { etiqueta: "Línea base", valor: 100 * r.proporcion_linea_base, globo: `Línea base\n${numero(r.glosadas_linea_base)} de ${numero(r.total_linea_base)} facturas glosadas` },
    { etiqueta: "Piloto", valor: 100 * r.proporcion_piloto, globo: `Piloto\n${numero(r.glosadas_piloto)} de ${numero(r.total_piloto)} facturas glosadas` },
  ], "Porcentaje de facturas glosadas: línea base contra piloto");

  poner(porId("z-resultado"),
    h("div", { class: "alerta " + (r.se_rechaza_h0 ? "ok" : "aviso"), role: "status" },
      h("b", null, titulo), h("p", { class: "arriba-chico" }, r.interpretacion)),
    r.advertencias.length
      ? h("div", { class: "alerta aviso arriba-chico" }, h("b", null, "Tenga en cuenta"), h("ul", null, r.advertencias.map((texto) => h("li", null, texto))))
      : null,
    h("div", { class: "rejilla-2 arriba" },
      h("dl", { class: "resultado-z" },
        dato("Línea base", porcentaje(100 * r.proporcion_linea_base), `${numero(r.glosadas_linea_base)} de ${numero(r.total_linea_base)}`),
        dato("Piloto", porcentaje(100 * r.proporcion_piloto), `${numero(r.glosadas_piloto)} de ${numero(r.total_piloto)}`),
        dato("Diferencia", `${decimal(100 * r.diferencia, 1)} pp`, `IC ${confianza}: ${decimal(100 * r.intervalo_inferior, 1)} a ${decimal(100 * r.intervalo_superior, 1)} pp`),
        dato("Estadístico z", decimal(r.z), `valor crítico ${unaCola ? "" : "±"}${decimal(r.valor_critico)}`),
        dato("Valor p", valorP(r.valor_p), `${unaCola ? "una cola" : "dos colas"} · alfa ${decimal(r.alfa)}`),
        dato("Decisión", r.se_rechaza_h0 ? "Rechazar H0" : "No rechazar H0", r.se_rechaza_h0 ? "valor p menor que alfa" : "valor p mayor o igual que alfa")),
      h("div", null, comparacion)),
    h("details", { class: "arriba" },
      h("summary", null, "¿Cómo se calculó?"),
      h("ol", { class: "apoyo" },
        h("li", null, `Proporción de la línea base: p1 = ${numero(r.glosadas_linea_base)} / ${numero(r.total_linea_base)} = ${decimal(r.proporcion_linea_base, 4)}.`),
        h("li", null, `Proporción del piloto: p2 = ${numero(r.glosadas_piloto)} / ${numero(r.total_piloto)} = ${decimal(r.proporcion_piloto, 4)}.`),
        h("li", null, `Proporción combinada: p = (${numero(r.glosadas_linea_base)} + ${numero(r.glosadas_piloto)}) / (${numero(r.total_linea_base)} + ${numero(r.total_piloto)}) = ${decimal(r.proporcion_combinada, 4)}.`),
        h("li", null, `Error estándar: EE = √[ p (1 − p) (1/n1 + 1/n2) ] = ${decimal(r.error_estandar, 4)}.`),
        h("li", null, `Estadístico: z = (p1 − p2) / EE = ${decimal(r.z)}.`),
        h("li", null, `Valor p (${unaCola ? "una cola" : "dos colas"}) = ${valorP(r.valor_p)}. Se rechaza H0 si es menor que alfa = ${decimal(r.alfa)}.`)),
      h("p", { class: "apoyo" }, "pp = puntos porcentuales. IC = intervalo de confianza de la diferencia entre las dos proporciones.")));
}

async function calcular(evento) {
  evento?.preventDefault();
  let cuerpo;
  try {
    cuerpo = leerFormulario();
  } catch (error) {
    poner(porId("z-resultado"), h("div", { class: "alerta error", role: "alert" }, error.message));
    return;
  }
  const boton = porId("z-calcular");
  boton.disabled = true;
  try {
    mostrarResultado(await api("/indicadores/prueba-z", { metodo: "POST", cuerpo }));
  } catch (error) {
    poner(porId("z-resultado"), cajaDeError(error));
  } finally {
    boton.disabled = false;
  }
}

// ---------------------------------------------------------------------
// Arranque
// ---------------------------------------------------------------------
iniciar(async () => {
  porId("f-tipo").addEventListener("change", () => mostrarIndicador().catch((error) => { console.error(error); avisar(error.message, "error"); }));
  porId("form-z").addEventListener("submit", calcular);
  porId("z-usar-lotes").addEventListener("click", () => { if (usarLotes()) calcular(); });

  await mostrarIndicador();
  // Si ya hay lotes de línea base y de piloto, la prueba se calcula de una vez.
  if (usarLotes()) await calcular();
});
