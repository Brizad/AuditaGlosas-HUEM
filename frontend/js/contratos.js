/* Página «Contratos y tarifas»: EPS, tarifas pactadas, autorizaciones y catálogo de servicios (HU-02, HU-04). */
import { api, h, poner, porId, iniciar, avisar, vacio, pesos, numero } from "./comun.js";

const TIPOS_BASE = ["consulta", "laboratorio", "imagen", "medicamento", "otro"];
let listaEps = [];
let catalogo = { servicios: [], soportes_requeridos: {} };
let codigoElegido = null;     // EPS que se está viendo

/** Ejecuta una acción contra la API y avisa el resultado. Devuelve true si salió bien. */
async function intentar(accion, mensajeOk) {
  try {
    await accion();
    if (mensajeOk) avisar(mensajeOk);
    return true;
  } catch (error) {
    avisar([error.message, ...(error.errores || [])].join(" "), "error");
    return false;
  }
}

const ruta = (codigo) => encodeURIComponent(codigo);

// ---------------------------------------------------------------------
// Lista de EPS
// ---------------------------------------------------------------------
async function cargarEps() {
  listaEps = await api("/eps");
  if (!listaEps.some((eps) => eps.codigo === codigoElegido)) codigoElegido = listaEps[0]?.codigo || null;
  poner(porId("lista-eps"), listaEps.length
    ? listaEps.map((eps) => h("button", {
        type: "button", "aria-pressed": String(eps.codigo === codigoElegido),
        onclick: () => { codigoElegido = eps.codigo; refrescar(); },
      }, h("b", null, eps.nombre),
        h("span", null, `${eps.codigo} · ${numero(eps.total_tarifas)} tarifas · ${numero(eps.total_facturas)} facturas`)))
    : vacio("Sin EPS", "Cree la primera con el formulario."));
}

async function crearEps(evento) {
  evento.preventDefault();
  const codigo = porId("eps-codigo").value.trim().toUpperCase();
  const creada = await intentar(
    () => api("/eps", { metodo: "POST", cuerpo: { codigo, nombre: porId("eps-nombre").value.trim() } }),
    "EPS creada.");
  if (creada) {
    evento.target.reset();
    codigoElegido = codigo;
    await refrescar();
  }
}

// ---------------------------------------------------------------------
// Contrato de la EPS elegida
// ---------------------------------------------------------------------
function filaDeTarifa(eps, tarifa) {
  const entrada = h("input", {
    type: "number", class: "entrada-chica", min: 0, step: "any", value: tarifa.valor,
    "aria-label": `Valor pactado para ${tarifa.codigo_servicio}`,
  });
  const guardar = async () => {
    const valor = Number(entrada.value);
    if (entrada.value === "" || !Number.isFinite(valor) || valor < 0) { avisar("Escriba un valor mayor o igual a cero.", "error"); return; }
    if (await intentar(() => api(`/eps/${ruta(eps.codigo)}/tarifas/${ruta(tarifa.codigo_servicio)}`, { metodo: "PUT", cuerpo: { valor } }),
      `Tarifa de ${tarifa.codigo_servicio} actualizada a ${pesos(valor)}.`)) await refrescar();
  };
  const casilla = h("input", {
    type: "checkbox", role: "switch", checked: tarifa.requiere_autorizacion,
    "aria-label": `Exigir autorización para ${tarifa.codigo_servicio}`,
    onchange: async () => {
      const base = `/eps/${ruta(eps.codigo)}/autorizaciones`;
      await intentar(() => casilla.checked
        ? api(base, { metodo: "POST", cuerpo: { codigo_servicio: tarifa.codigo_servicio } })
        : api(`${base}/${ruta(tarifa.codigo_servicio)}`, { metodo: "DELETE" }),
        casilla.checked ? `${eps.nombre} ahora exige autorización para ${tarifa.codigo_servicio}.` : `${eps.nombre} ya no exige autorización para ${tarifa.codigo_servicio}.`);
      await refrescar();
    },
  });
  return h("tr", null,
    h("td", { class: "mono" }, tarifa.codigo_servicio),
    h("td", null, tarifa.descripcion || h("span", { class: "tenue" }, "No está en el catálogo")),
    h("td", { class: "numero" }, h("span", { class: "valor-editable" }, entrada,
      h("button", { class: "boton chico", type: "button", onclick: guardar }, "Guardar"))),
    h("td", null, h("label", { class: "interruptor" }, casilla, h("span", { class: "riel" }),
      h("span", { class: "texto" }, tarifa.requiere_autorizacion ? "Sí exige" : "No exige"))),
    h("td", { class: "derecha" }, h("button", {
      class: "boton chico peligro", type: "button",
      onclick: async () => {
        if (!confirm(`¿Eliminar la tarifa de ${tarifa.codigo_servicio} en ${eps.nombre}?`)) return;
        if (await intentar(() => api(`/eps/${ruta(eps.codigo)}/tarifas/${ruta(tarifa.codigo_servicio)}`, { metodo: "DELETE" }), "Tarifa eliminada.")) await refrescar();
      },
    }, "Eliminar")));
}

async function mostrarDetalle() {
  const zona = porId("detalle");
  if (!codigoElegido) { poner(zona, vacio("Sin EPS", "Cree una EPS para registrar su contrato.")); return; }
  const eps = await api(`/eps/${ruta(codigoElegido)}`);

  // Cambiar nombre y eliminar
  const nombre = h("input", { type: "text", value: eps.nombre, maxlength: 120, "aria-label": "Nombre de la EPS" });
  const renombrar = async (evento) => {
    evento.preventDefault();
    if (await intentar(() => api(`/eps/${ruta(eps.codigo)}`, { metodo: "PUT", cuerpo: { nombre: nombre.value.trim() } }), "Nombre actualizado.")) await refrescar();
  };
  const eliminar = async () => {
    if (!confirm(`¿Eliminar ${eps.nombre} con todas sus tarifas?`)) return;
    if (await intentar(() => api(`/eps/${ruta(eps.codigo)}`, { metodo: "DELETE" }), "EPS eliminada.")) { codigoElegido = null; await refrescar(); }
  };

  // Agregar tarifa: se sugieren los códigos del catálogo que aún no tienen tarifa.
  const conTarifa = new Set(eps.tarifas.map((tarifa) => tarifa.codigo_servicio));
  const sugerencias = h("datalist", { id: "codigos-catalogo" },
    catalogo.servicios.filter((servicio) => !conTarifa.has(servicio.codigo))
      .map((servicio) => h("option", { value: servicio.codigo }, servicio.descripcion)));
  const nuevoCodigo = h("input", { type: "text", required: true, maxlength: 20, pattern: "[A-Za-z0-9._\\-]{1,20}", list: "codigos-catalogo", placeholder: "Código" });
  const nuevoValor = h("input", { type: "number", required: true, min: 0, step: "any", placeholder: "Valor pactado" });
  const agregar = async (evento) => {
    evento.preventDefault();
    const cuerpo = { codigo_servicio: nuevoCodigo.value.trim(), valor: Number(nuevoValor.value) };
    if (await intentar(() => api(`/eps/${ruta(eps.codigo)}/tarifas`, { metodo: "POST", cuerpo }), "Tarifa agregada.")) await refrescar();
  };

  // Autorizaciones exigidas para códigos que no tienen tarifa (caso poco común, pero posible).
  const sueltas = eps.autorizaciones.filter((autorizacion) => !conTarifa.has(autorizacion.codigo_servicio));

  poner(zona,
    h("div", { class: "cabecera-tarjeta" },
      h("div", null, h("h2", null, eps.nombre),
        h("span", { class: "apoyo" }, `${eps.codigo} · ${numero(eps.total_facturas)} facturas cargadas`)),
      h("form", { class: "acciones", onsubmit: renombrar }, nombre,
        h("button", { class: "boton", type: "submit" }, "Cambiar nombre"),
        h("button", { class: "boton peligro", type: "button", onclick: eliminar }, "Eliminar EPS"))),
    eps.tarifas.length
      ? h("div", { class: "tabla-envoltura" }, h("table", null,
          h("thead", null, h("tr", null,
            h("th", null, "Código"), h("th", null, "Servicio"), h("th", { class: "numero" }, "Valor pactado"),
            h("th", null, "Autorización"), h("th", null, h("span", { class: "solo-lectores" }, "Acciones")))),
          h("tbody", null, eps.tarifas.map((tarifa) => filaDeTarifa(eps, tarifa)))))
      : vacio("Sin tarifas pactadas", "Agregue la primera con el formulario de abajo."),
    sueltas.length ? h("p", { class: "apoyo arriba-chico" }, "También exige autorización para: ",
      sueltas.map((autorizacion) => h("span", { class: "regla" }, autorizacion.codigo_servicio))) : null,
    h("h3", { class: "arriba" }, "Agregar tarifa"),
    h("form", { class: "formulario arriba-chico", onsubmit: agregar },
      h("label", { class: "campo" }, h("span", null, "Código del servicio"), nuevoCodigo, sugerencias),
      h("label", { class: "campo" }, h("span", null, "Valor pactado ($)"), nuevoValor),
      h("button", { class: "boton primario", type: "submit" }, "Agregar tarifa")));
}

// ---------------------------------------------------------------------
// Catálogo de servicios
// ---------------------------------------------------------------------
async function cargarCatalogo() {
  catalogo = await api("/catalogo");
  const tipos = [...new Set([...TIPOS_BASE, ...Object.keys(catalogo.soportes_requeridos), ...catalogo.servicios.map((s) => s.tipo)])];
  const selector = porId("srv-tipo");
  const elegido = selector.value;
  poner(selector, tipos.map((tipo) => h("option", { value: tipo }, tipo)));
  if (tipos.includes(elegido)) selector.value = elegido;

  poner(porId("catalogo"), catalogo.servicios.length
    ? h("div", { class: "tabla-envoltura" }, h("table", null,
        h("thead", null, h("tr", null,
          h("th", null, "Código"), h("th", null, "Descripción"), h("th", null, "Tipo"),
          h("th", null, "Soportes obligatorios"), h("th", null, h("span", { class: "solo-lectores" }, "Acciones")))),
        h("tbody", null, catalogo.servicios.map((servicio) => {
          const soportes = catalogo.soportes_requeridos[servicio.tipo] || [];
          return h("tr", null,
            h("td", { class: "mono" }, servicio.codigo),
            h("td", null, servicio.descripcion),
            h("td", null, servicio.tipo),
            h("td", null, soportes.length ? soportes.join(", ") : h("span", { class: "tenue" }, "Ninguno")),
            h("td", { class: "derecha" },
              h("button", { class: "boton chico", type: "button", onclick: () => {
                porId("srv-codigo").value = servicio.codigo;
                porId("srv-descripcion").value = servicio.descripcion;
                porId("srv-tipo").value = servicio.tipo;
                porId("srv-descripcion").focus();
              } }, "Editar"),
              h("button", { class: "boton chico peligro", type: "button", onclick: async () => {
                if (!confirm(`¿Quitar ${servicio.codigo} (${servicio.descripcion}) del catálogo?`)) return;
                if (await intentar(() => api(`/catalogo/servicios/${ruta(servicio.codigo)}`, { metodo: "DELETE" }), "Servicio quitado del catálogo.")) await refrescar();
              } }, "Quitar")));
        }))))
    : vacio("Catálogo vacío", "Agregue servicios con el formulario."));
}

async function guardarServicio(evento) {
  evento.preventDefault();
  const codigo = porId("srv-codigo").value.trim();
  const cuerpo = { descripcion: porId("srv-descripcion").value.trim(), tipo: porId("srv-tipo").value };
  if (await intentar(() => api(`/catalogo/servicios/${ruta(codigo)}`, { metodo: "PUT", cuerpo }), `Servicio ${codigo} guardado.`)) {
    evento.target.reset();
    await refrescar();
  }
}

// ---------------------------------------------------------------------
// Arranque
// ---------------------------------------------------------------------
async function refrescar() {
  await cargarCatalogo();
  await cargarEps();
  await mostrarDetalle();
}

iniciar(async () => {
  porId("form-eps").addEventListener("submit", crearEps);
  porId("form-servicio").addEventListener("submit", guardarServicio);
  await refrescar();
});
