/* Página «Cargar lote»: leer el archivo JSON, enviarlo a la API y listar los lotes cargados (HU-01). */
import { api, h, poner, porId, iniciar, avisar, cajaDeError, vacio, numero } from "./comun.js";
import { tablaDeLotes } from "./lotes.js";

const TAMANO_MAXIMO = 20 * 1024 * 1024;   // mismo límite que el servidor
let facturas = null;                       // facturas leídas del archivo elegido

// ---------------------------------------------------------------------
// Leer el archivo en el navegador
// ---------------------------------------------------------------------
/** El archivo puede ser una lista de facturas o un objeto { facturas: [...] }. */
function extraerFacturas(contenido) {
  if (Array.isArray(contenido)) return contenido;
  if (contenido && Array.isArray(contenido.facturas)) return contenido.facturas;
  throw new Error("El archivo debe contener una lista de facturas [ ] o un objeto con la lista «facturas».");
}

/**
 * Si el archivo ya dice el nombre, el tipo y el periodo del lote (así salen los lotes
 * del generador), se copian al formulario para no tener que digitarlos.
 */
function usarDatosDelArchivo(contenido) {
  if (!contenido || Array.isArray(contenido)) return;
  const sinNombre = !porId("nombre").value.trim();   // no se pisa lo que el usuario ya escribió
  if (sinNombre && typeof contenido.nombre === "string" && contenido.nombre.trim()) porId("nombre").value = contenido.nombre.trim().slice(0, 120);
  if (["general", "linea_base", "piloto"].includes(contenido.tipo)) porId("tipo").value = contenido.tipo;
  if (/^\d{4}-(0[1-9]|1[0-2])$/.test(contenido.periodo || "")) porId("periodo").value = contenido.periodo;
}

async function leerArchivo(archivo) {
  const previa = porId("vista-previa");
  facturas = null;
  porId("enviar").disabled = true;
  previa.hidden = false;
  try {
    if (archivo.size > TAMANO_MAXIMO) throw new Error("El archivo pesa más de 20 MB.");
    let contenido;
    try {
      contenido = JSON.parse(await archivo.text());
    } catch (error) {
      throw new Error("El archivo no es un JSON válido: " + error.message);
    }
    facturas = extraerFacturas(contenido);
    if (!facturas.length) throw new Error("El archivo no trae ninguna factura.");

    const eps = [...new Set(facturas.map((factura) => factura?.eps).filter((valor) => typeof valor === "string"))];
    porId("zona-titulo").textContent = archivo.name;
    porId("zona-detalle").textContent = "Haga clic para elegir otro archivo.";
    poner(previa, h("div", { class: "alerta ok arriba" },
      h("b", null, `${numero(facturas.length)} facturas listas para cargar`),
      eps.length ? ` · EPS: ${eps.slice(0, 6).join(", ")}${eps.length > 6 ? "…" : ""}` : ""));
    usarDatosDelArchivo(contenido);
    // Se propone un nombre a partir del archivo, si el usuario no escribió uno.
    if (!porId("nombre").value.trim()) porId("nombre").value = archivo.name.replace(/\.json$/i, "").replace(/[_-]+/g, " ").slice(0, 120);
    porId("enviar").disabled = false;
  } catch (error) {
    poner(previa, h("div", { class: "alerta error arriba", role: "alert" }, h("b", null, "No se pudo leer el archivo. "), error.message));
  }
}

// ---------------------------------------------------------------------
// Enviar el lote
// ---------------------------------------------------------------------
async function enviar(evento) {
  evento.preventDefault();
  const resultado = porId("resultado");
  const nombre = porId("nombre").value.trim();
  if (!facturas) return;
  if (!nombre) {
    poner(resultado, h("div", { class: "alerta error", role: "alert" }, "Escriba un nombre para reconocer el lote."));
    porId("nombre").focus();
    return;
  }
  const boton = porId("enviar");
  boton.disabled = true;
  boton.textContent = "Cargando…";
  try {
    const cuerpo = { nombre, tipo: porId("tipo").value, facturas };
    if (porId("periodo").value) cuerpo.periodo = porId("periodo").value;
    const lote = await api("/lotes", { metodo: "POST", cuerpo });
    if (porId("validar-ya").checked) {
      boton.textContent = "Validando…";
      await api(`/lotes/${lote.id}/validar`, { metodo: "POST" });
    }
    location.href = `/resultados?lote=${lote.id}`;
  } catch (error) {
    poner(resultado, cajaDeError(error));
    boton.disabled = false;
    boton.textContent = "Cargar lote";
  }
}

// ---------------------------------------------------------------------
// Lista de lotes cargados
// ---------------------------------------------------------------------
async function mostrarLotes() {
  const lotes = await api("/lotes");
  if (!lotes.length) {
    poner(porId("lotes"), vacio("Todavía no hay lotes", "El primero que cargue aparecerá aquí."));
    return;
  }
  poner(porId("lotes"), tablaDeLotes(lotes, (lote) => [
    h("a", { class: "boton chico", href: `/resultados?lote=${lote.id}` }, "Ver"),
    h("button", { class: "boton chico peligro", type: "button", onclick: () => eliminar(lote) }, "Eliminar"),
  ]));
}

async function eliminar(lote) {
  if (!confirm(`¿Eliminar el lote «${lote.nombre}» con sus ${lote.resumen.total_facturas} facturas y hallazgos?\nEsta acción no se puede deshacer.`)) return;
  try {
    await api(`/lotes/${lote.id}`, { metodo: "DELETE" });
    avisar("Lote eliminado.");
    await mostrarLotes();
  } catch (error) {
    avisar(error.message, "error");
  }
}

// ---------------------------------------------------------------------
// Arranque
// ---------------------------------------------------------------------
iniciar(async () => {
  const zona = porId("zona");
  porId("archivo").addEventListener("change", (evento) => {
    if (evento.target.files[0]) leerArchivo(evento.target.files[0]);
  });
  // Arrastrar y soltar el archivo sobre la zona.
  for (const tipo of ["dragenter", "dragover"]) {
    zona.addEventListener(tipo, (evento) => { evento.preventDefault(); zona.classList.add("encima"); });
  }
  for (const tipo of ["dragleave", "drop"]) {
    zona.addEventListener(tipo, (evento) => { evento.preventDefault(); zona.classList.remove("encima"); });
  }
  zona.addEventListener("drop", (evento) => {
    if (evento.dataTransfer.files[0]) leerArchivo(evento.dataTransfer.files[0]);
  });
  porId("formulario").addEventListener("submit", enviar);
  await mostrarLotes();
});
