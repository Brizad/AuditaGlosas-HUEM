/* Página «Resultados»: tarjetas, gráficas y tabla de facturas de un lote (HU-05). */
import {
  api, h, poner, porId, iniciar, avisar, vacio, parametro, pesos, numero, porcentaje,
  fechaCorta, periodoLegible, pildoraEstado, etiquetaRegla, TIPOS_LOTE,
} from "./comun.js";
import { barras, barrasPorEstado, barraDeEstados } from "./graficas.js";

let idLote = null;
let facturas = [];   // facturas del lote, para filtrarlas sin volver a pedirlas

// ---------------------------------------------------------------------
// Tabla de facturas con filtros
// ---------------------------------------------------------------------
function mostrarFacturas() {
  const estado = porId("filtro-estado").value;
  const texto = porId("filtro-texto").value.trim().toLowerCase();
  const visibles = facturas.filter((factura) => {
    if (estado && factura.estado !== estado) return false;
    if (!texto) return true;
    return [factura.num_factura, factura.eps_nombre, factura.eps_codigo, ...factura.reglas]
      .some((dato) => dato.toLowerCase().includes(texto));
  });
  porId("conteo-facturas").textContent = `Mostrando ${numero(visibles.length)} de ${numero(facturas.length)} facturas.`;

  if (!visibles.length) {
    poner(porId("facturas"), vacio("Ninguna factura coincide", "Cambie el filtro o el texto de búsqueda."));
    return;
  }
  poner(porId("facturas"), h("div", { class: "tabla-envoltura" },
    h("table", null,
      h("thead", null, h("tr", null,
        h("th", null, "Factura"), h("th", null, "EPS"), h("th", null, "Fecha"),
        h("th", { class: "numero" }, "Valor"), h("th", null, "Reglas incumplidas"),
        h("th", { class: "numero" }, "En riesgo"), h("th", null, "Estado"))),
      h("tbody", null, visibles.map((factura) =>
        h("tr", { class: "enlazable" },
          h("td", null, h("a", { class: "mono", href: `/factura?id=${factura.id}` }, factura.num_factura)),
          h("td", null, factura.eps_nombre),
          h("td", null, fechaCorta(factura.fecha_expedicion)),
          h("td", { class: "numero" }, pesos(factura.valor_total)),
          h("td", null, factura.reglas.length ? factura.reglas.map(etiquetaRegla) : h("span", { class: "tenue" }, "—")),
          h("td", { class: "numero" }, factura.valor_en_riesgo ? pesos(factura.valor_en_riesgo) : "—"),
          h("td", null, pildoraEstado(factura.estado))))))));
}

// ---------------------------------------------------------------------
// Pintar todo el lote
// ---------------------------------------------------------------------
async function mostrarLote() {
  const [resultados, causales, porEps] = await Promise.all([
    api(`/lotes/${idLote}/resultados`),
    api(`/reportes/por-causal?lote_id=${idLote}`),
    api(`/reportes/por-eps?lote_id=${idLote}`),
  ]);
  const lote = resultados.lote, resumen = lote.resumen;
  const validado = lote.estado === "validado";
  facturas = resultados.facturas;

  document.title = `${lote.nombre} · AuditaGlosas HUEM`;
  porId("titulo").textContent = lote.nombre;
  poner(porId("subtitulo"),
    `${TIPOS_LOTE[lote.tipo] || lote.tipo} · ${periodoLegible(lote.periodo)} · `,
    validado ? `validado el ${fechaCorta(lote.fecha_validacion)} a las ${lote.fecha_validacion.slice(11, 16)}` : "cargado, aún sin validar");
  porId("validar").textContent = validado ? "Validar de nuevo" : "Validar antes de radicar";
  porId("exportar").href = `/api/reportes/exportar.csv?lote_id=${idLote}`;

  poner(porId("aviso-lote"), validado ? null : h("div", { class: "alerta aviso" },
    h("b", null, "Este lote todavía no se ha validado. "), "Pulse «Validar antes de radicar» para aplicar las reglas activas."));

  // Tarjetas
  porId("k-total").textContent = numero(resumen.total_facturas);
  porId("k-total-nota").textContent = `${pesos(resumen.valor_facturado)} facturados`;
  porId("k-aptas").textContent = validado ? numero(resumen.aptas) : "—";
  porId("k-aptas-nota").textContent = validado ? `${porcentaje(resumen.porcentaje_aptas)} del lote` : "Sin validar";
  porId("k-malas").textContent = validado ? numero(resumen.con_inconsistencias) : "—";
  porId("k-malas-nota").textContent = validado ? `${porcentaje(resumen.porcentaje_con_inconsistencias)} del lote` : "Sin validar";
  porId("k-riesgo").textContent = validado ? pesos(resumen.valor_en_riesgo) : "—";
  porId("k-riesgo-nota").textContent = validado && resumen.valor_facturado
    ? `${porcentaje(100 * resumen.valor_en_riesgo / resumen.valor_facturado)} de lo facturado` : " ";

  // Gráficas
  barraDeEstados(porId("g-estados"), resumen);
  if (causales.total_hallazgos) {
    barras(porId("g-causales"), causales.grupos.map((grupo) => ({
      codigo: grupo.grupo,
      nombre: grupo.nombre_grupo,
      valor: grupo.hallazgos,
      cifra: h("b", null, numero(grupo.hallazgos)),
      globo: `${grupo.nombre_grupo}\n${numero(grupo.hallazgos)} hallazgos en ${numero(grupo.facturas_afectadas)} facturas\n${pesos(grupo.valor_hallazgos)}`,
    })));
  } else {
    poner(porId("g-causales"), vacio(validado ? "Sin hallazgos" : "Sin validar",
      validado ? "Ninguna factura incumple las reglas activas." : "Valide el lote para ver los hallazgos."));
  }
  barrasPorEstado(porId("g-eps"), porEps.filas.filter((fila) => fila.total_facturas > 0).map((fila) => ({
    nombre: fila.eps_nombre, aptas: fila.aptas, con_inconsistencias: fila.con_inconsistencias, sin_validar: fila.sin_validar,
  })));

  mostrarFacturas();
  porId("cuerpo").hidden = false;
}

async function validar() {
  const boton = porId("validar");
  boton.disabled = true;
  boton.textContent = "Validando…";
  try {
    const lote = await api(`/lotes/${idLote}/validar`, { metodo: "POST" });
    avisar(`Validación terminada: ${lote.resumen.aptas} de ${lote.resumen.total_facturas} facturas aptas.`);
    await mostrarLote();
  } catch (error) {
    avisar(error.message, "error");
  } finally {
    boton.disabled = false;
  }
}

// ---------------------------------------------------------------------
// Arranque
// ---------------------------------------------------------------------
iniciar(async () => {
  const lotes = await api("/lotes");
  if (!lotes.length) {
    poner(porId("aviso-lote"), h("div", { class: "tarjeta" },
      vacio("Todavía no hay lotes", "Cargue un lote para ver aquí sus resultados.",
        h("a", { class: "boton primario", href: "/carga" }, "Cargar un lote"))));
    return;
  }
  // Se muestra el lote de la dirección (?lote=3); si no viene o no existe, el más reciente.
  const pedido = Number(parametro("lote"));
  idLote = lotes.some((lote) => lote.id === pedido) ? pedido : lotes[0].id;

  const selector = porId("selector-lote");
  poner(selector, lotes.map((lote) => h("option", { value: lote.id }, `${lote.nombre} (${periodoLegible(lote.periodo)})`)));
  selector.value = idLote;
  selector.addEventListener("change", () => { location.href = `/resultados?lote=${selector.value}`; });

  porId("validar").addEventListener("click", validar);
  porId("filtro-estado").addEventListener("change", mostrarFacturas);
  porId("filtro-texto").addEventListener("input", mostrarFacturas);
  porId("acciones").hidden = false;
  await mostrarLote();
});
