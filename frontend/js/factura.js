/* Página «Detalle de factura»: lo cobrado, lo reportado en el RIPS y cada hallazgo (HU-05). */
import {
  api, h, poner, porId, iniciar, parametro, pesos, numero, fechaCorta, pildoraEstado, etiquetaRegla, ErrorApi,
} from "./comun.js";

const CLASES = { consulta: "Consulta", procedimiento: "Procedimiento", medicamento: "Medicamento" };

function tabla(encabezados, filas, total) {
  return h("div", { class: "tabla-envoltura" },
    h("table", null,
      h("thead", null, h("tr", null, encabezados.map(([texto, clase]) => h("th", { class: clase }, texto)))),
      h("tbody", null, filas, total)));
}

const dato = (rotulo, valor) => h("div", null, h("dt", null, rotulo), h("dd", null, valor));

iniciar(async () => {
  const id = Number(parametro("id"));
  if (!Number.isInteger(id) || id < 1) throw new ErrorApi("Falta indicar la factura. Vuelva a Resultados y elija una.", 400);
  const factura = await api(`/facturas/${id}`);
  const validada = factura.estado !== "sin_validar";

  document.title = `${factura.num_factura} · AuditaGlosas HUEM`;
  poner(porId("migas"), h("a", { href: `/resultados?lote=${factura.lote_id}` }, `← ${factura.lote_nombre}`));
  porId("titulo").textContent = `Factura ${factura.num_factura}`;
  porId("subtitulo").textContent = `${factura.eps_nombre} · expedida el ${fechaCorta(factura.fecha_expedicion)}`;
  poner(porId("estado"), pildoraEstado(factura.estado));

  const mismoNumero = factura.rips_num_factura === factura.num_factura;
  poner(porId("datos"),
    dato("Valor de la factura", pesos(factura.valor_total)),
    dato("Valor en riesgo de glosa", validada ? pesos(factura.valor_en_riesgo) : "Sin validar"),
    dato("EPS", `${factura.eps_nombre} (${factura.eps_codigo})`),
    dato("Factura que reporta el RIPS", h("span", { class: "mono" }, factura.rips_num_factura || "(vacío)", mismoNumero ? "" : " ≠ " + factura.num_factura)),
    dato("Hallazgos", validada ? numero(factura.hallazgos.length) : "—"));

  // Hallazgos
  porId("titulo-hallazgos").textContent = factura.hallazgos.length
    ? `Qué corregir antes de radicar (${factura.hallazgos.length})` : "Hallazgos";
  const suma = factura.hallazgos.reduce((total, hallazgo) => total + hallazgo.valor_en_riesgo, 0);
  porId("nota-hallazgos").textContent = suma > factura.valor_en_riesgo + 0.5
    ? `Los hallazgos suman ${pesos(suma)}, pero el valor en riesgo se limita al total de la factura (${pesos(factura.valor_total)}): no se puede glosar más de lo facturado.`
    : "";
  if (!validada) {
    poner(porId("hallazgos"), h("li", { class: "hallazgo sin" },
      h("div", { class: "titulo" }, "Factura sin validar"),
      h("div", { class: "detalle" }, "Valide el lote para saber si tiene inconsistencias.")));
  } else if (!factura.hallazgos.length) {
    poner(porId("hallazgos"), h("li", { class: "hallazgo sin" },
      h("div", { class: "titulo" }, "Sin inconsistencias"),
      h("div", { class: "detalle" }, "La factura cumple todas las reglas activas del catálogo. Está lista para radicar.")));
  } else {
    poner(porId("hallazgos"), factura.hallazgos.map((hallazgo) =>
      h("li", { class: "hallazgo" },
        h("div", { class: "titulo" }, etiquetaRegla(hallazgo.regla), hallazgo.titulo),
        h("div", { class: "riesgo" }, h("span", { class: "apoyo" }, "En riesgo"), h("b", null, pesos(hallazgo.valor_en_riesgo))),
        h("div", { class: "detalle" }, hallazgo.detalle, h("span", { class: "tenue" }, ` · Causal: ${hallazgo.nombre_grupo}`)))));
  }

  // Lo facturado
  poner(porId("items"), tabla(
    [["Código"], ["Descripción"], ["Cant.", "numero"], ["Valor unit.", "numero"], ["Valor", "numero"]],
    factura.items.map((item) => h("tr", null,
      h("td", { class: "mono" }, item.codigo),
      h("td", null, item.descripcion || h("span", { class: "tenue" }, "No está en el catálogo")),
      h("td", { class: "numero" }, numero(item.cantidad)),
      h("td", { class: "numero" }, pesos(item.valor_unitario)),
      h("td", { class: "numero" }, pesos(item.valor)))),
    h("tr", { class: "total" }, h("td", { colspan: 4 }, "Total de la factura"), h("td", { class: "numero" }, pesos(factura.valor_total)))));

  // Lo reportado en el RIPS
  const sumaRips = factura.servicios.reduce((total, servicio) => total + servicio.valor_servicio, 0);
  poner(porId("servicios"), factura.servicios.length ? tabla(
    [["Tipo"], ["Código"], ["Descripción"], ["Autorización"], ["Valor", "numero"]],
    factura.servicios.map((servicio) => h("tr", null,
      h("td", null, CLASES[servicio.clase] || servicio.clase),
      h("td", { class: "mono" }, servicio.codigo),
      h("td", null, servicio.descripcion || h("span", { class: "tenue" }, "No está en el catálogo"),
        servicio.cantidad !== 1 ? h("span", { class: "tenue" }, ` · ${numero(servicio.cantidad)} × ${pesos(servicio.valor_unitario)}`) : null),
      h("td", { class: "mono" }, servicio.num_autorizacion || h("span", { class: "tenue" }, "—")),
      h("td", { class: "numero" }, pesos(servicio.valor_servicio)))),
    h("tr", { class: "total" }, h("td", { colspan: 4 }, "Suma del RIPS"), h("td", { class: "numero" }, pesos(sumaRips))))
    : h("p", { class: "vacio" }, "El RIPS no reporta servicios."));

  poner(porId("soportes"), factura.soportes.length
    ? h("ul", { class: "lista-simple" }, factura.soportes.map((soporte) => h("li", null, soporte)))
    : h("p", { class: "apoyo" }, "La factura no declara soportes adjuntos."));

  porId("cuerpo").hidden = false;
});
