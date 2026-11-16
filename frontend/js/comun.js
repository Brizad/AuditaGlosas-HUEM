/* =====================================================================
   Funciones que comparten todas las páginas.

   Regla de seguridad: los datos que vienen del servidor NUNCA se escriben
   con innerHTML. Todo se crea con la función h(), que usa textContent, así
   un dato malicioso dentro de un lote no puede ejecutar código (XSS).
   ===================================================================== */

// ---------------------------------------------------------------------
// 1. Llamadas a la API
// ---------------------------------------------------------------------
export class ErrorApi extends Error {
  constructor(mensaje, estado, errores = []) {
    super(mensaje);
    this.estado = estado;     // código HTTP (0 si no hubo conexión)
    this.errores = errores;   // lista de problemas, cuando el servidor la envía
  }
}

/** Llama a un endpoint de /api y devuelve el JSON. Lanza ErrorApi si algo falla. */
export async function api(ruta, { metodo = "GET", cuerpo } = {}) {
  const opciones = { method: metodo, headers: {} };
  if (cuerpo !== undefined) {
    opciones.headers["Content-Type"] = "application/json";
    opciones.body = JSON.stringify(cuerpo);
  }
  let respuesta;
  try {
    respuesta = await fetch("/api" + ruta, opciones);
  } catch {
    throw new ErrorApi("No se pudo conectar con el servidor. Verifique que esté encendido.", 0);
  }
  if (respuesta.status === 204) return null;
  let datos = null;
  try { datos = await respuesta.json(); } catch { /* respuesta sin JSON */ }
  if (!respuesta.ok) {
    const mensaje = typeof datos?.detail === "string" ? datos.detail : `El servidor respondió con el error ${respuesta.status}.`;
    throw new ErrorApi(mensaje, respuesta.status, Array.isArray(datos?.errores) ? datos.errores : []);
  }
  return datos;
}

// ---------------------------------------------------------------------
// 2. Crear elementos de forma segura
// ---------------------------------------------------------------------
function aplicarAtributos(elemento, atributos) {
  for (const [clave, valor] of Object.entries(atributos || {})) {
    if (valor === null || valor === undefined || valor === false) continue;
    if (clave === "style") Object.assign(elemento.style, valor);                 // estilos como objeto
    else if (clave.startsWith("on")) elemento.addEventListener(clave.slice(2), valor); // onclick, onchange...
    else if (clave === "value" && "value" in elemento) elemento.value = valor;
    else if (valor === true) elemento.setAttribute(clave, "");
    else elemento.setAttribute(clave, valor);
  }
}

function agregarHijos(elemento, hijos) {
  for (const hijo of hijos.flat(Infinity)) {
    if (hijo === null || hijo === undefined || hijo === false) continue;
    elemento.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
}

/** Crea un elemento HTML: h("a", {href: "/carga", class: "boton"}, "Cargar lote"). */
export function h(etiqueta, atributos, ...hijos) {
  const elemento = document.createElement(etiqueta);
  aplicarAtributos(elemento, atributos);
  agregarHijos(elemento, hijos);
  return elemento;
}

/** Igual que h() pero para elementos SVG (las gráficas de columnas). */
export function svg(etiqueta, atributos, ...hijos) {
  const elemento = document.createElementNS("http://www.w3.org/2000/svg", etiqueta);
  aplicarAtributos(elemento, atributos);
  agregarHijos(elemento, hijos);
  return elemento;
}

/** Reemplaza todo el contenido de un elemento. */
export function poner(elemento, ...hijos) {
  elemento.replaceChildren();
  agregarHijos(elemento, hijos);
  return elemento;
}

export const porId = (id) => document.getElementById(id);

/** Lee un parámetro de la dirección: /resultados?lote=3 -> parametro("lote") === "3". */
export const parametro = (nombre) => new URLSearchParams(location.search).get(nombre);

// ---------------------------------------------------------------------
// 3. Formatos
// ---------------------------------------------------------------------
export const pesos = (valor) => "$" + Math.round(valor || 0).toLocaleString("es-CO");
export const numero = (valor) => (valor || 0).toLocaleString("es-CO");
export const porcentaje = (valor) => (valor || 0).toLocaleString("es-CO", { maximumFractionDigits: 1 }) + " %";
/** Elige singular o plural: contar(1, "lote cargado", "lotes cargados") -> "lote cargado". */
export const contar = (cantidad, singular, plural) => (cantidad === 1 ? singular : plural);

/** "2026-06-11" -> "11/06/2026" (sin crear un objeto Date, para no correr la fecha por la zona horaria). */
export function fechaCorta(texto) {
  if (!texto) return "—";
  const [anio, mes, dia] = texto.slice(0, 10).split("-");
  return `${dia}/${mes}/${anio}`;
}

const MESES = ["ene.", "feb.", "mar.", "abr.", "may.", "jun.", "jul.", "ago.", "sep.", "oct.", "nov.", "dic."];
/** "2026-06" -> "jun. 2026". */
export function periodoLegible(periodo) {
  const [anio, mes] = (periodo || "").split("-");
  return MESES[Number(mes) - 1] ? `${MESES[Number(mes) - 1]} ${anio}` : periodo || "—";
}

export const TIPOS_LOTE = { general: "General", linea_base: "Línea base", piloto: "Piloto" };
export const GRUPOS = { FA: "Facturación y codificación", TA: "Tarifas", SO: "Soportes", AU: "Autorizaciones" };

const ESTADOS = {
  apta: ["ok", "Apta para radicar"],
  con_inconsistencias: ["mal", "Corregir antes de radicar"],
  sin_validar: ["espera", "Sin validar"],
  validado: ["ok", "Validado"],
  cargado: ["espera", "Sin validar"],
};
/** Píldora de color con el estado de una factura o de un lote (siempre con texto). */
export function pildoraEstado(estado) {
  const [clase, texto] = ESTADOS[estado] || ["espera", estado];
  return h("span", { class: "pildora " + clase }, texto);
}

export const etiquetaRegla = (codigo) => h("span", { class: "regla" }, codigo);

// ---------------------------------------------------------------------
// 4. Encabezado, navegación y pie (iguales en todas las páginas)
// ---------------------------------------------------------------------
const PAGINAS = [
  ["inicio", "/", "Inicio"],
  ["carga", "/carga", "Cargar lote"],
  ["resultados", "/resultados", "Resultados"],
  ["reportes", "/reportes", "Reportes"],
  ["reglas", "/reglas", "Reglas"],
  ["contratos", "/contratos", "Contratos y tarifas"],
];

function logotipo() {
  // Escudo sencillo con una marca de verificación (no es el logo oficial del hospital).
  return svg("svg", { viewBox: "0 0 32 32", "aria-hidden": "true" },
    svg("rect", { x: 2, y: 2, width: 28, height: 28, rx: 8, fill: "#fff" }),
    svg("path", { d: "M9 16.5l4.5 4.5L23 11.5", fill: "none", stroke: "#c8102e", "stroke-width": 3.2, "stroke-linecap": "round", "stroke-linejoin": "round" }),
  );
}

/** Dibuja el encabezado y el pie. Cada página la llama una vez al cargar. */
export function montarPagina() {
  const actual = document.body.dataset.pagina;
  poner(porId("encabezado"),
    h("div", { class: "encabezado-interno" },
      h("a", { class: "marca", href: "/" }, logotipo(),
        h("span", null, h("small", null, "Hospital Universitario Erasmo Meoz"), "AuditaGlosas")),
      h("nav", { class: "navegacion", "aria-label": "Secciones" },
        PAGINAS.map(([clave, ruta, texto]) =>
          h("a", { href: ruta, "aria-current": clave === actual ? "page" : null }, texto))),
    ));
  poner(porId("pie"),
    "AuditaGlosas HUEM · proyecto académico de la Universidad de Pamplona · solo datos sintéticos (Ley 1581 de 2012) · ",
    "los resultados no constituyen una auditoría oficial · ",
    h("a", { href: "/docs" }, "Documentación de la API"));
  activarGlobos();
}

// ---------------------------------------------------------------------
// 5. Avisos, errores y globos de ayuda
// ---------------------------------------------------------------------
/** Aviso flotante que desaparece solo. tipo: "" o "error". */
export function avisar(mensaje, tipo = "") {
  let zona = porId("avisos");
  if (!zona) {
    zona = h("div", { id: "avisos", class: "avisos", role: "status", "aria-live": "polite" });
    document.body.append(zona);
  }
  const aviso = h("div", { class: "aviso-flotante " + tipo }, mensaje);
  zona.append(aviso);
  setTimeout(() => aviso.remove(), tipo === "error" ? 8000 : 4500);
}

/** Caja roja con el mensaje de un error y, si la hay, la lista de problemas. */
export function cajaDeError(error) {
  const errores = error.errores || [];
  return h("div", { class: "alerta error", role: "alert" },
    h("b", null, error.message || "Ocurrió un error."),
    errores.length ? h("ul", null, errores.map((texto) => h("li", null, texto))) : null);
}

/** Texto centrado para cuando todavía no hay datos. */
export function vacio(titulo, texto, accion) {
  return h("div", { class: "vacio" }, h("b", null, titulo), texto, accion ? h("p", { style: { marginTop: "12px" } }, accion) : null);
}

/** Muestra un globo con el texto de `data-globo` al pasar el ratón o al enfocar con el teclado. */
function activarGlobos() {
  const globo = h("div", { class: "globo", role: "tooltip", hidden: true });
  document.body.append(globo);
  const mostrar = (objetivo, x, y) => {
    globo.textContent = objetivo.dataset.globo;
    globo.hidden = false;
    const ancho = globo.offsetWidth, alto = globo.offsetHeight;
    globo.style.left = Math.max(8, Math.min(x + 12, innerWidth - ancho - 8)) + "px";
    globo.style.top = (y - alto - 12 < 8 ? y + 16 : y - alto - 12) + "px";
  };
  const objetivoDe = (evento) => evento.target instanceof Element ? evento.target.closest("[data-globo]") : null;
  document.addEventListener("mousemove", (evento) => {
    const objetivo = objetivoDe(evento);
    if (objetivo) mostrar(objetivo, evento.clientX, evento.clientY); else globo.hidden = true;
  });
  document.addEventListener("focusin", (evento) => {
    const objetivo = objetivoDe(evento);
    if (!objetivo) return;
    const caja = objetivo.getBoundingClientRect();
    mostrar(objetivo, caja.left + caja.width / 2, caja.top);
  });
  document.addEventListener("focusout", () => { globo.hidden = true; });
  document.addEventListener("scroll", () => { globo.hidden = true; }, true);
}

/** Ejecuta la función principal de una página y muestra el error si falla. */
export async function iniciar(funcion) {
  montarPagina();
  try {
    await funcion();
  } catch (error) {
    console.error(error);
    porId("contenido").prepend(cajaDeError(error));
  }
}
