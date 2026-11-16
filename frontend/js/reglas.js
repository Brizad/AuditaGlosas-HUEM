/* Página «Catálogo de reglas»: interruptores para activar y desactivar reglas (HU-06). */
import { api, h, poner, porId, iniciar, avisar } from "./comun.js";

let reglas = [];

function actualizarConteo() {
  const activas = reglas.filter((regla) => regla.activa).length;
  const conteo = porId("conteo");
  conteo.textContent = `${activas} de ${reglas.length} reglas activas`;
  conteo.className = "pildora " + (activas === reglas.length ? "ok" : "aviso");
}

/** Cambia el estado en el servidor; si falla, devuelve el interruptor a como estaba. */
async function cambiar(regla, casilla, texto) {
  const activar = casilla.checked;
  casilla.disabled = true;
  try {
    const respuesta = await api(`/reglas/${regla.codigo}/${activar ? "activar" : "desactivar"}`, { metodo: "POST" });
    regla.activa = respuesta.activa;
    avisar(`Regla ${regla.codigo} ${regla.activa ? "activada" : "desactivada"}. Valide de nuevo los lotes para ver el efecto.`);
  } catch (error) {
    avisar(error.message, "error");
  } finally {
    casilla.checked = regla.activa;
    casilla.disabled = false;
    texto.textContent = regla.activa ? "Activa" : "Inactiva";
    actualizarConteo();
  }
}

function filaDeRegla(regla) {
  const texto = h("span", { class: "texto" }, regla.activa ? "Activa" : "Inactiva");
  const casilla = h("input", {
    type: "checkbox", role: "switch", checked: regla.activa,
    "aria-label": `Regla ${regla.codigo}: ${regla.nombre}`,
    onchange: () => cambiar(regla, casilla, texto),
  });
  return h("tr", null,
    h("td", null, h("span", { class: "regla" }, regla.codigo)),
    h("td", null, h("b", null, regla.nombre), h("div", { class: "apoyo" }, regla.descripcion)),
    h("td", null, h("label", { class: "interruptor" }, casilla, h("span", { class: "riel" }), texto)));
}

iniciar(async () => {
  reglas = await api("/reglas");
  // Se agrupan por grupo de causal, en el orden en que llegan (FA, TA, SO, AU).
  const grupos = new Map();
  for (const regla of reglas) {
    if (!grupos.has(regla.grupo)) grupos.set(regla.grupo, { nombre: regla.nombre_grupo, reglas: [] });
    grupos.get(regla.grupo).reglas.push(regla);
  }
  poner(porId("reglas"), [...grupos.entries()].map(([codigo, grupo]) =>
    h("div", { class: "grupo-reglas" },
      h("h3", null, h("span", { class: "regla" }, codigo), grupo.nombre),
      h("div", { class: "tabla-envoltura" }, h("table", null,
        h("thead", null, h("tr", null, h("th", null, "Regla"), h("th", null, "Qué verifica"), h("th", null, "Estado"))),
        h("tbody", null, grupo.reglas.map(filaDeRegla)))))));
  actualizarConteo();
});
