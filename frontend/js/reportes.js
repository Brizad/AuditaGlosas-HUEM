/* Página «Reportes»: hallazgos por causal y por EPS, con filtros y exportación a CSV (HU-05). */
import { api, h, poner, porId, iniciar, avisar, vacio, pesos, numero, porcentaje, periodoLegible } from "./comun.js";
import { barras, barrasPorEstado } from "./graficas.js";

/** Arma «?lote_id=1&periodo=2026-06» con los filtros que estén elegidos. */
function consulta() {
  const filtros = new URLSearchParams();
  if (porId("f-lote").value) filtros.set("lote_id", porId("f-lote").value);
  if (porId("f-periodo").value) filtros.set("periodo", porId("f-periodo").value);
  if (porId("f-tipo").value) filtros.set("tipo", porId("f-tipo").value);
  const texto = filtros.toString();
  return texto ? "?" + texto : "";
}

function tablaCausales(reporte) {
  const filas = [];
  for (const grupo of reporte.grupos) {
    filas.push(h("tr", null,
      h("td", null, h("b", null, `${grupo.grupo} · ${grupo.nombre_grupo}`)),
      h("td", { class: "numero" }, h("b", null, numero(grupo.hallazgos))),
      h("td", { class: "numero" }, numero(grupo.facturas_afectadas)),
      h("td", { class: "numero" }, pesos(grupo.valor_hallazgos))));
    for (const regla of grupo.reglas) {
      filas.push(h("tr", { class: "subfila" },
        h("td", null, h("span", { class: "regla" }, regla.codigo), regla.nombre),
        h("td", { class: "numero" }, numero(regla.hallazgos)),
        h("td", { class: "numero" }, numero(regla.facturas_afectadas)),
        h("td", { class: "numero" }, pesos(regla.valor_hallazgos))));
    }
  }
  return h("div", { class: "tabla-envoltura" }, h("table", null,
    h("thead", null, h("tr", null,
      h("th", null, "Causal y regla"), h("th", { class: "numero" }, "Hallazgos"),
      h("th", { class: "numero" }, "Facturas"), h("th", { class: "numero" }, "Valor"))),
    h("tbody", null, filas,
      h("tr", { class: "total" },
        h("td", null, "Total"), h("td", { class: "numero" }, numero(reporte.total_hallazgos)),
        h("td", null, ""), h("td", { class: "numero" }, pesos(reporte.valor_hallazgos))))));
}

function tablaEps(filas) {
  return h("div", { class: "tabla-envoltura" }, h("table", null,
    h("thead", null, h("tr", null,
      h("th", null, "EPS"), h("th", { class: "numero" }, "Facturas"), h("th", { class: "numero" }, "Aptas"),
      h("th", { class: "numero" }, "Con inconsist."), h("th", { class: "numero" }, "% inconsist."),
      h("th", { class: "numero" }, "En riesgo"))),
    h("tbody", null, filas.map((fila) => h("tr", null,
      h("td", null, fila.eps_nombre),
      h("td", { class: "numero" }, numero(fila.total_facturas)),
      h("td", { class: "numero" }, numero(fila.aptas)),
      h("td", { class: "numero" }, numero(fila.con_inconsistencias)),
      h("td", { class: "numero" }, fila.aptas + fila.con_inconsistencias ? porcentaje(fila.porcentaje_con_inconsistencias) : "—"),
      h("td", { class: "numero" }, pesos(fila.valor_en_riesgo)))))));
}

async function mostrar() {
  const filtros = consulta();
  porId("exportar").href = "/api/reportes/exportar.csv" + filtros;
  const [causales, porEps] = await Promise.all([api("/reportes/por-causal" + filtros), api("/reportes/por-eps" + filtros)]);

  // Totales: se suman las filas por EPS (cada factura pertenece a una sola EPS).
  const suma = (campo) => porEps.filas.reduce((total, fila) => total + fila[campo], 0);
  const total = suma("total_facturas"), malas = suma("con_inconsistencias"), aptas = suma("aptas");
  const riesgo = suma("valor_en_riesgo"), facturado = suma("valor_facturado");
  porId("k-total").textContent = numero(total);
  porId("k-total-nota").textContent = suma("sin_validar") ? `${numero(suma("sin_validar"))} sin validar` : `${pesos(facturado)} facturados`;
  porId("k-malas").textContent = numero(malas);
  porId("k-malas-nota").textContent = malas + aptas ? `${porcentaje(100 * malas / (malas + aptas))} de las validadas` : " ";
  porId("k-hallazgos").textContent = numero(causales.total_hallazgos);
  porId("k-hallazgos-nota").textContent = malas ? `${(causales.total_hallazgos / malas).toLocaleString("es-CO", { maximumFractionDigits: 1 })} por factura con inconsistencias` : " ";
  porId("k-riesgo").textContent = pesos(riesgo);
  porId("k-riesgo-nota").textContent = facturado ? `${porcentaje(100 * riesgo / facturado)} de lo facturado` : " ";

  if (!total) {
    const mensaje = () => vacio("No hay facturas con estos filtros", "Quite algún filtro o cargue un lote.");
    poner(porId("g-causales"), mensaje()); poner(porId("t-causales"));
    poner(porId("g-eps"), mensaje()); poner(porId("t-eps"));
    porId("nota-causal").textContent = "";
    return;
  }

  barras(porId("g-causales"), causales.grupos.map((grupo) => ({
    codigo: grupo.grupo,
    nombre: grupo.nombre_grupo,
    valor: grupo.hallazgos,
    cifra: h("b", null, numero(grupo.hallazgos)),
    globo: `${grupo.nombre_grupo}\n${numero(grupo.hallazgos)} hallazgos en ${numero(grupo.facturas_afectadas)} facturas\n${pesos(grupo.valor_hallazgos)}`,
  })));
  poner(porId("t-causales"), tablaCausales(causales));
  porId("nota-causal").textContent = causales.valor_hallazgos > riesgo + 0.5
    ? `La suma de los hallazgos (${pesos(causales.valor_hallazgos)}) es mayor que el valor en riesgo (${pesos(riesgo)}) porque un mismo servicio puede tener varios hallazgos y el riesgo de cada factura no supera su total.`
    : "";

  const conFacturas = porEps.filas.filter((fila) => fila.total_facturas > 0);
  barrasPorEstado(porId("g-eps"), conFacturas.map((fila) => ({
    nombre: fila.eps_nombre, aptas: fila.aptas, con_inconsistencias: fila.con_inconsistencias, sin_validar: fila.sin_validar,
  })));
  poner(porId("t-eps"), tablaEps(conFacturas));
}

iniciar(async () => {
  const lotes = await api("/lotes");
  porId("f-lote").append(...lotes.map((lote) => h("option", { value: lote.id }, lote.nombre)));
  const periodos = [...new Set(lotes.map((lote) => lote.periodo))].sort().reverse();
  porId("f-periodo").append(...periodos.map((periodo) => h("option", { value: periodo }, periodoLegible(periodo))));

  const filtros = ["f-lote", "f-periodo", "f-tipo"].map(porId);
  const actualizar = () => mostrar().catch((error) => { console.error(error); avisar(error.message, "error"); });
  filtros.forEach((filtro) => filtro.addEventListener("change", actualizar));
  porId("limpiar").addEventListener("click", () => { filtros.forEach((filtro) => { filtro.value = ""; }); actualizar(); });
  await mostrar();
});
