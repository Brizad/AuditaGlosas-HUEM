/* Página de inicio: indicadores generales y últimos lotes. */
import { api, h, poner, porId, iniciar, vacio, pesos, numero, porcentaje, contar } from "./comun.js";
import { barrasDeCausales, barraDeEstados } from "./graficas.js";
import { tablaDeLotes } from "./lotes.js";

iniciar(async () => {
  const datos = await api("/indicadores");
  const resumen = datos.resumen;
  const validadas = resumen.aptas + resumen.con_inconsistencias;

  // Tarjetas de indicadores
  porId("k-validadas").textContent = numero(validadas);
  porId("k-validadas-nota").textContent = resumen.sin_validar
    ? `${numero(resumen.sin_validar)} cargadas sin validar`
    : `de ${numero(resumen.total_facturas)} cargadas`;
  porId("k-aptas").textContent = numero(resumen.aptas);
  porId("k-aptas-nota").textContent = validadas ? `${porcentaje(resumen.porcentaje_aptas)} de las validadas` : "Aún no hay validaciones";
  porId("k-malas").textContent = numero(resumen.con_inconsistencias);
  porId("k-malas-nota").textContent = validadas ? `${porcentaje(resumen.porcentaje_con_inconsistencias)} de las validadas` : "Aún no hay validaciones";
  porId("k-riesgo").textContent = pesos(resumen.valor_en_riesgo);
  porId("k-riesgo-nota").textContent = `de ${pesos(resumen.valor_facturado)} facturados`;

  poner(porId("minis"),
    h("span", null, h("b", null, numero(datos.total_lotes)), contar(datos.total_lotes, " lote cargado", " lotes cargados")),
    h("span", null, h("b", null, `${datos.reglas_activas} de ${datos.total_reglas}`), " reglas activas · ", h("a", { href: "/reglas" }, "configurar")),
    h("span", null, h("b", null, numero(datos.eps_registradas)), " EPS con contrato · ", h("a", { href: "/contratos" }, "ver tarifas")));

  if (!datos.total_lotes) {
    const mensaje = () => vacio("Todavía no hay lotes", "Cargue un archivo JSON con facturas y su RIPS para empezar.",
      h("a", { class: "boton primario", href: "/carga" }, "Cargar el primer lote"));
    poner(porId("g-estados"), mensaje());
    poner(porId("g-causales"), vacio("Sin hallazgos todavía", "Aparecerán aquí cuando valide un lote."));
    poner(porId("lotes"), vacio("Sin lotes", "Los lotes que cargue se listan aquí."));
    return;
  }

  barraDeEstados(porId("g-estados"), resumen);
  barrasDeCausales(porId("g-causales"), datos.hallazgos_por_grupo);
  poner(porId("lotes"), tablaDeLotes(datos.ultimos_lotes));
});
