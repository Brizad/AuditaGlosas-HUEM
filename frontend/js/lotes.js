/* Tabla de lotes que comparten la página de inicio y la de carga. */
import { h, pesos, numero, porcentaje, periodoLegible, pildoraEstado, TIPOS_LOTE } from "./comun.js";

/**
 * Arma la tabla de lotes.
 * acciones(lote) es opcional: devuelve los botones de la última columna.
 */
export function tablaDeLotes(lotes, acciones) {
  return h("div", { class: "tabla-envoltura" },
    h("table", null,
      h("thead", null, h("tr", null,
        h("th", null, "Lote"), h("th", null, "Periodo"), h("th", null, "Tipo"),
        h("th", { class: "numero" }, "Facturas"), h("th", { class: "numero" }, "Aptas"),
        h("th", { class: "numero" }, "Valor en riesgo"), h("th", null, "Estado"),
        acciones ? h("th", null, h("span", { class: "solo-lectores" }, "Acciones")) : null)),
      h("tbody", null, lotes.map((lote) => {
        const resumen = lote.resumen;
        const validado = lote.estado === "validado";
        return h("tr", { class: "enlazable" },
          h("td", null, h("a", { href: `/resultados?lote=${lote.id}` }, lote.nombre)),
          h("td", null, periodoLegible(lote.periodo)),
          h("td", null, TIPOS_LOTE[lote.tipo] || lote.tipo),
          h("td", { class: "numero" }, numero(resumen.total_facturas)),
          h("td", { class: "numero" }, validado ? `${numero(resumen.aptas)} (${porcentaje(resumen.porcentaje_aptas)})` : "—"),
          h("td", { class: "numero" }, validado ? pesos(resumen.valor_en_riesgo) : "—"),
          h("td", null, pildoraEstado(lote.estado)),
          acciones ? h("td", { class: "derecha" }, acciones(lote)) : null);
      }))));
}
