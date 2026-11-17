/* =====================================================================
   Gráficas hechas con HTML, CSS y SVG (sin librerías externas).

   Criterios de diseño:
   - Barras delgadas que nacen de una misma línea base; el valor va escrito
     al final de la barra, así nadie depende solo del color.
   - "Aptas" en verde azulado y "con inconsistencias" en rojo: es un par que
     también distinguen las personas con daltonismo, y siempre lleva texto.
   - Cada barra muestra un globo con el detalle al pasar el ratón o al
     enfocarla con el teclado. Debajo de cada gráfica hay una tabla con los
     mismos datos.
   ===================================================================== */
import { h, svg, poner, numero, porcentaje, pesos } from "./comun.js";

/**
 * Barras horizontales de una sola serie.
 * filas: [{ codigo, nombre, valor, cifra, globo }]
 */
export function barras(contenedor, filas) {
  const maximo = Math.max(1, ...filas.map((fila) => fila.valor));
  poner(contenedor, h("div", { class: "barras", role: "list" }, filas.map((fila) => [
    h("div", { class: "nombre", role: "listitem" }, fila.codigo ? h("b", null, fila.codigo) : null, fila.nombre),
    h("div", { class: "pista" },
      fila.valor > 0
        ? h("div", { class: "trozo", tabindex: 0, "data-globo": fila.globo, style: { width: (100 * fila.valor / maximo) + "%" } })
        : null),
    h("div", { class: "cifra" }, fila.cifra),
  ])));
}

/**
 * Barras de hallazgos por grupo de causal (la usan Inicio, Resultados y Reportes).
 * grupos: [{ grupo, nombre_grupo, hallazgos, facturas_afectadas, valor_hallazgos }]
 */
export function barrasDeCausales(contenedor, grupos) {
  barras(contenedor, grupos.map((grupo) => ({
    codigo: grupo.grupo,
    nombre: grupo.nombre_grupo,
    valor: grupo.hallazgos,
    cifra: h("b", null, numero(grupo.hallazgos)),
    globo: `${grupo.nombre_grupo}\n${numero(grupo.hallazgos)} hallazgos en ${numero(grupo.facturas_afectadas)} facturas\n${pesos(grupo.valor_hallazgos)}`,
  })));
}

/**
 * Barras horizontales apiladas: cada fila se divide en aptas, con inconsistencias y sin validar.
 * filas: [{ nombre, aptas, con_inconsistencias, sin_validar }]
 */
export function barrasPorEstado(contenedor, filas) {
  const total = (fila) => fila.aptas + fila.con_inconsistencias + fila.sin_validar;
  const maximo = Math.max(1, ...filas.map(total));
  const trozo = (fila, clase, cantidad, texto) => cantidad > 0
    ? h("div", {
        class: "trozo " + clase, tabindex: 0,
        "data-globo": `${fila.nombre}\n${numero(cantidad)} ${texto} de ${numero(total(fila))} facturas`,
        style: { width: (100 * cantidad / maximo) + "%" },
      })
    : null;

  poner(contenedor,
    h("div", { class: "barras", role: "list" }, filas.map((fila) => [
      h("div", { class: "nombre", role: "listitem" }, fila.nombre),
      h("div", { class: "pista" },
        trozo(fila, "mal", fila.con_inconsistencias, "con inconsistencias"),
        trozo(fila, "ok", fila.aptas, "aptas"),
        trozo(fila, "neutro", fila.sin_validar, "sin validar")),
      h("div", { class: "cifra" }, h("b", null, numero(fila.con_inconsistencias)), ` de ${numero(total(fila))}`),
    ])),
    leyenda([["mal", "Con inconsistencias"], ["ok", "Aptas"], ["neutro", "Sin validar"]]
      .filter(([clase]) => clase !== "neutro" || filas.some((fila) => fila.sin_validar > 0))),
  );
}

function leyenda(entradas) {
  return h("div", { class: "leyenda" }, entradas.map(([clase, texto, cifra]) =>
    h("span", null, h("i", { class: clase }), texto, cifra !== undefined ? h("b", null, cifra) : null)));
}

/** Vigilantes de tamaño de las barras segmentadas (uno por contenedor). */
const vigilantes = new WeakMap();

/**
 * Barra segmentada: el total de facturas dividido en aptas, con inconsistencias y sin validar.
 * resumen: { total_facturas, aptas, con_inconsistencias, sin_validar }
 */
export function barraDeEstados(contenedor, resumen) {
  const total = resumen.total_facturas || 0;
  const partes = [
    ["ok", "Aptas para radicar", resumen.aptas],
    ["mal", "Con inconsistencias", resumen.con_inconsistencias],
    ["neutro", "Sin validar", resumen.sin_validar],
  ].filter(([, , cantidad]) => cantidad > 0);

  const bloques = partes.map(([clase, nombre, cantidad]) => {
    const parte = porcentaje(100 * cantidad / total);
    return h("div", {
      class: "parte " + clase, tabindex: 0,
      "data-globo": `${nombre}\n${numero(cantidad)} de ${numero(total)} facturas (${parte})`,
      style: { flex: `${cantidad} 1 0` },
    }, h("span", null, parte));
  });

  poner(contenedor,
    h("div", { class: "segmentada", role: "img", "aria-label": partes.map(([, nombre, cantidad]) => `${nombre}: ${cantidad}`).join(", ") }, bloques),
    leyenda(partes.map(([clase, nombre, cantidad]) => [clase, nombre, numero(cantidad)])));

  // Si el porcentaje no cabe dentro de su bloque, se quita (queda en la leyenda y en el globo).
  const ajustar = () => bloques.forEach((bloque) => {
    const texto = bloque.firstElementChild;
    bloque.classList.remove("sin-texto");
    texto.hidden = false;
    if (texto.offsetWidth + 16 > bloque.clientWidth) {
      texto.hidden = true;
      bloque.classList.add("sin-texto");
    }
  });
  requestAnimationFrame(ajustar);
  // Un solo vigilante de tamaño por contenedor: si la gráfica se vuelve a dibujar, se cambia el anterior.
  vigilantes.get(contenedor)?.disconnect();
  const vigilante = new ResizeObserver(ajustar);
  vigilante.observe(contenedor);
  vigilantes.set(contenedor, vigilante);
}

/**
 * Columnas con un porcentaje por categoría (por ejemplo, % de facturas glosadas por periodo).
 * puntos: [{ etiqueta, valor (0 a 100), globo, clase }]
 */
export function columnas(contenedor, puntos, descripcion) {
  const ANCHO = 640, ALTO = 240, IZQ = 40, DER = 12, ARRIBA = 22, ABAJO = 30;
  const altoUtil = ALTO - ARRIBA - ABAJO, anchoUtil = ANCHO - IZQ - DER;
  const maximo = Math.max(10, Math.ceil(Math.max(...puntos.map((p) => p.valor), 0) / 10) * 10);
  const y = (valor) => ARRIBA + altoUtil * (1 - valor / maximo);
  const franja = anchoUtil / Math.max(1, puntos.length);
  const grosor = Math.min(24, franja * 0.6);

  const lienzo = svg("svg", { class: "columnas", viewBox: `0 0 ${ANCHO} ${ALTO}`, role: "img", "aria-label": descripcion });
  // Líneas guía en 0 %, mitad y máximo.
  for (const marca of [0, maximo / 2, maximo]) {
    lienzo.append(
      svg("line", { class: marca === 0 ? "eje" : "guia", x1: IZQ, x2: ANCHO - DER, y1: y(marca), y2: y(marca) }),
      svg("text", { x: IZQ - 6, y: y(marca) + 4, "text-anchor": "end" }, `${marca} %`));
  }
  puntos.forEach((punto, indice) => {
    const centro = IZQ + franja * (indice + 0.5);
    const alto = Math.max(0, y(0) - y(punto.valor));
    const izquierda = centro - grosor / 2;
    // Columna con la punta redondeada y la base recta.
    const radio = Math.min(4, alto);
    const forma = `M${izquierda},${y(0)} V${y(punto.valor) + radio} q0,-${radio} ${radio},-${radio} h${grosor - 2 * radio} q${radio},0 ${radio},${radio} V${y(0)} Z`;
    lienzo.append(
      // Zona invisible más ancha que la columna, para que sea fácil pasar el ratón.
      svg("rect", { class: "zona", x: centro - franja / 2, y: ARRIBA, width: franja, height: altoUtil, tabindex: 0, "data-globo": punto.globo }),
      alto > 0 ? svg("path", { class: "columna " + (punto.clase || ""), d: forma }) : null,
      svg("text", { class: "valor", x: centro, y: y(punto.valor) - 6, "text-anchor": "middle" }, porcentaje(punto.valor)),
      svg("text", { x: centro, y: ALTO - 10, "text-anchor": "middle" }, punto.etiqueta));
  });
  poner(contenedor, lienzo);
}
