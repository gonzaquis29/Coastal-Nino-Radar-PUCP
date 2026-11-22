// Mide los criterios de la interfaz con la API real corriendo (python -m radar.app) y el Edge instalado, sin
// descargar navegadores: P6 (axe), P7 (6 textos sintéticos de punta a punta), P8 (cifras en pantalla = API), P10, P12,
// U1, U2, U4, U5 y U6, y deja capturas a 375 y 1.280 px en claro y oscuro para la revisión de P11.
//
//   npm run medir                 (RADAR_URL=http://localhost:8000 por defecto)
//   -> ../data/processed/app/interfaz.json   y   medir/capturas/*.png
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";
import { chromium } from "playwright-core";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const BASE = process.env.RADAR_URL ?? "http://localhost:8000";
const FECHA = "2026-11-22"; // fija: el comunicado vigente es el N.° 20 y los resultados esperados no cambian
const CAPTURAS = path.join(AQUI, "capturas");
const SALIDA = path.resolve(AQUI, "../../data/processed/app/interfaz.json");
const AXE = fs.readFileSync(path.resolve(AQUI, "../node_modules/axe-core/axe.min.js"), "utf8");
const ANCHOS = [375, 1280];
const TEMAS = ["light", "dark"];

// P7: textos inventados y el resultado que debe verse (comprobados contra el comunicado N.° 20)
const P7 = [
  { texto: "El ENFEN prevé un Niño costero extraordinario hasta junio de 2027", tipo: "datos", clase: "resultado--coincide", titulo: "Coincide con el ENFEN" },
  { texto: "El ENFEN mantiene la vigilancia de El Niño costero con magnitud débil", tipo: "datos", clase: "resultado--revisar", titulo: "Usa un dato anterior del ENFEN" },
  { texto: "El ENFEN prevé que El Niño costero durará hasta junio de 2028", tipo: "datos", clase: "resultado--no_coincide", titulo: "No coincide con el ENFEN" },
  { texto: "El mar frente a la costa norte sigue más caliente de lo normal y se esperan lluvias por El Niño costero", tipo: "cercania", titulo: "Cercanía: Alta" },
  { texto: "Receta de ceviche con limón, ají y camote", tipo: "cercania", titulo: "Cercanía: Media" },
  { texto: "Nuevo teléfono con cámara de 200 megapíxeles llega a las tiendas", tipo: "cercania", titulo: "Cercanía: Baja" },
];
const JERGA = ["capa", "distancia", "coseno", "umbral", "auc", "nli", "embedding", "origen", "percentil"];
const PROMESAS = ["correcto", "verdadero", "falso", "verdad"];
const ESTADO_RGB = ["rgb(12, 163, 12)", "rgb(250, 178, 25)", "rgb(208, 59, 59)"]; // --bien, --alerta, --mal

const palabras = (t) => new Set(t.toLowerCase().match(/[a-záéíóúüñ]+/g) ?? []);
const resultados = { fecha: new Date().toISOString(), base: BASE, criterios: {} };
const anotar = (id, datos) => {
  resultados.criterios[id] = datos;
  console.log(`[${datos.pasa ? "ok" : "NO"}] ${id}: ${datos.valor} (umbral ${datos.umbral})${datos.detalle ? ` — ${datos.detalle}` : ""}`);
};

fs.mkdirSync(CAPTURAS, { recursive: true });
const navegador = await chromium.launch({ channel: process.env.RADAR_CANAL ?? "msedge" });

async function pagina({ ancho = 1280, tema = "light", zona = "costa_norte" } = {}) {
  const contexto = await navegador.newContext({
    viewport: { width: ancho, height: ancho < 768 ? 812 : 900 },
    colorScheme: tema,
    bypassCSP: true, // solo para inyectar axe; la app no lo necesita
    reducedMotion: "reduce",
    acceptDownloads: true,
  });
  if (zona) await contexto.addInitScript((z) => localStorage.setItem("radar.zona", z), zona);
  // la medición no escribe en el registro de uso real: se responde aquí, sin llegar a la API
  await contexto.route("**/api/eventos", (r) => r.fulfill({ status: 204, body: "" }));
  await contexto.addInitScript(() => {
    navigator.sendBeacon = () => true; // los beacons al cerrar la página no pasan por route
  });
  const p = await contexto.newPage();
  p.setDefaultTimeout(60_000);
  return p;
}

async function verificar(p, texto, fecha = FECHA) {
  await p.goto(`${BASE}/`);
  if (fecha) {
    await p.getByRole("button", { name: "¿Es de otra fecha?" }).click();
    await p.locator("input[type=date]").fill(fecha);
  }
  await p.locator("#texto").fill(texto);
  await p.getByRole("button", { name: "Verificar", exact: true }).click();
  await p.locator("[data-tipo]").waitFor();
  await p.waitForFunction(() => !document.querySelector(".respuesta.atenuado"));
}

async function preguntar(p) {
  await p.goto(`${BASE}/preguntar`);
  await p.getByRole("button", { name: "¿Qué dice el ENFEN sobre la pesca?" }).click();
  await p.locator(".burbuja--respuesta").waitFor();
  await p.locator(".entendido summary").click();
}

async function panorama(p) {
  await p.goto(`${BASE}/panorama`);
  await p.waitForFunction(() => document.querySelectorAll("section.grafico[data-seccion]").length === 6
    && !document.querySelector("section.grafico.atenuado") && document.querySelector(".hallazgo"));
}

async function metodologia(p) {
  await p.goto(`${BASE}/metodologia`);
  await p.locator(".validacion details").first().waitFor();
  await p.locator(".validacion summary").first().click();
}

const ESTADOS = {
  "verificar-inicio": async (p) => {
    await p.goto(`${BASE}/`); // sin zona guardada (ver zonaDe)
    await p.locator(".elegir-zona").waitFor();
  },
  "verificar-datos": async (p) => {
    await verificar(p, P7[1].texto);
    await p.getByRole("button", { name: /Ver por qué/ }).click();
  },
  "verificar-cercania": async (p) => verificar(p, P7[3].texto),
  preguntar,
  panorama,
  metodologia,
};

const zonaDe = (nombre) => (nombre === "verificar-inicio" ? null : "costa_norte");

async function axe(p) {
  await p.addScriptTag({ content: AXE });
  const r = await p.evaluate(async () => {
    // eslint-disable-next-line no-undef
    const salida = await axe.run(document, { resultTypes: ["violations"] });
    return salida.violations.map((v) => ({ id: v.id, impacto: v.impact, nodos: v.nodes.length, ejemplo: v.nodes[0]?.target?.join(" ") }));
  });
  return r.filter((v) => v.impacto === "serious" || v.impacto === "critical");
}

// ---------------------------------------------------------------- P6 y capturas (P11)
{
  const graves = [];
  let corridas = 0;
  for (const ancho of ANCHOS) {
    for (const tema of TEMAS) {
      for (const [nombre, preparar] of Object.entries(ESTADOS)) {
        const p = await pagina({ ancho, tema, zona: zonaDe(nombre) });
        await preparar(p);
        await p.waitForTimeout(250);
        await p.screenshot({ path: path.join(CAPTURAS, `${nombre}-${ancho}-${tema === "light" ? "claro" : "oscuro"}.png`), fullPage: true });
        for (const v of await axe(p)) graves.push({ estado: nombre, ancho, tema, ...v });
        corridas += 1;
        await p.context().close();
      }
    }
  }
  anotar("P6", {
    valor: graves.length,
    umbral: "0",
    pasa: graves.length === 0,
    detalle: `${corridas} pantallas (375 y 1.280 px, claro y oscuro)${graves.length ? `: ${graves.map((g) => `${g.id}@${g.estado}-${g.ancho}-${g.tema} (${g.ejemplo})`).join("; ")}` : ""}`,
  });
}

// ---------------------------------------------------------------- P7 y U6
{
  let bien = 0;
  const fallas = [];
  const promesasOColor = [];
  for (const caso of P7) {
    const p = await pagina();
    await verificar(p, caso.texto);
    const r = await p.evaluate(() => {
      const s = document.querySelector("[data-tipo]");
      return { tipo: s.dataset.tipo, clase: s.className, titulo: s.querySelector("h2").textContent.trim() };
    });
    const ok = r.tipo === caso.tipo && r.titulo === caso.titulo && (!caso.clase || r.clase.includes(caso.clase));
    if (ok) bien += 1;
    else fallas.push(`${caso.titulo} -> ${r.titulo}`);
    if (caso.tipo === "cercania") {
      const u6 = await p.evaluate((rgb) => {
        const raiz = document.querySelector(".respuesta");
        const colores = new Set();
        for (const el of [raiz, ...raiz.querySelectorAll("*")]) {
          const c = getComputedStyle(el);
          for (const prop of ["color", "backgroundColor", "borderLeftColor", "borderTopColor", "fill", "stroke"]) colores.add(c[prop]);
        }
        return { colores: [...colores].filter((c) => rgb.includes(c)), texto: raiz.innerText };
      }, ESTADO_RGB);
      const prom = PROMESAS.filter((w) => palabras(u6.texto).has(w));
      if (u6.colores.length || prom.length) promesasOColor.push(`${caso.titulo}: ${[...u6.colores, ...prom].join(", ")}`);
    }
    await p.context().close();
  }
  anotar("P7", { valor: `${bien}/${P7.length}`, umbral: "6/6", pasa: bien === P7.length, detalle: fallas.join("; ") });
  anotar("U6", {
    valor: promesasOColor.length,
    umbral: "0",
    pasa: promesasOColor.length === 0,
    detalle: `respuestas sin datos revisadas en pantalla: 3${promesasOColor.length ? `; ${promesasOColor.join("; ")}` : ""}`,
  });
}

// ---------------------------------------------------------------- U1: pegar y tocar Verificar, con la zona recordada
{
  const p = await pagina({ ancho: 375 });
  await p.goto(`${BASE}/`);
  let acciones = 0;
  await p.locator("#texto").fill(P7[0].texto);
  acciones += 1;
  await p.getByRole("button", { name: "Verificar", exact: true }).click();
  acciones += 1;
  const visto = await p.locator("[data-tipo]").waitFor({ timeout: 30_000 }).then(() => true, () => false);
  anotar("U1", { valor: visto ? acciones : "sin resultado", umbral: "≤ 2", pasa: visto && acciones <= 2, detalle: "fecha de hoy, zona guardada" });
  await p.context().close();
}

// ---------------------------------------------------------------- U2: sin jerga en Verificar y Preguntar en pantalla
{
  const encontradas = [];
  for (const preparar of [ESTADOS["verificar-datos"], ESTADOS["verificar-cercania"], ESTADOS.preguntar]) {
    const p = await pagina();
    await preparar(p);
    const texto = await p.locator("main").innerText();
    encontradas.push(...JERGA.filter((j) => palabras(texto).has(j)));
    await p.context().close();
  }
  anotar("U2", { valor: encontradas.length, umbral: "0", pasa: encontradas.length === 0, detalle: [...new Set(encontradas)].join(", ") });
}

// ---------------------------------------------------------------- U4: primera carga de Verificar, comprimida
{
  const p = await pagina({ ancho: 375 });
  const respuestas = [];
  p.on("response", (r) => respuestas.push(r));
  await p.goto(`${BASE}/`, { waitUntil: "networkidle" });
  let bytes = 0;
  const archivos = [];
  for (const r of respuestas) {
    const tipo = r.request().resourceType();
    if (!["document", "script", "stylesheet", "image", "font", "fetch", "xhr"].includes(tipo)) continue;
    const cuerpo = await r.body().catch(() => Buffer.alloc(0));
    const gz = zlib.gzipSync(cuerpo, { level: 6 }).length;
    bytes += gz;
    archivos.push(`${new URL(r.url()).pathname} ${(gz / 1024).toFixed(1)} KB`);
  }
  const kb = bytes / 1024;
  const perezosos = archivos.filter((a) => /Panorama|Metodologia|panorama/.test(a));
  anotar("U4", {
    valor: `${kb.toFixed(1).replace(".", ",")} KB`,
    umbral: "≤ 300 KB",
    pasa: kb <= 300 && perezosos.length === 0,
    detalle: `${archivos.length} archivos; Panorama sin cargar: ${perezosos.length === 0 ? "sí" : "no"}`,
  });
  await p.context().close();
}

// ---------------------------------------------------------------- U5: controles de 44 × 44 px o más, a 375 px
{
  const chicos = [];
  let total = 0;
  for (const [nombre, preparar] of Object.entries(ESTADOS)) {
    const p = await pagina({ ancho: 375, zona: zonaDe(nombre) });
    await preparar(p);
    if (nombre === "panorama") await p.locator("[data-seccion=linea] [aria-pressed]").click(); // con una tabla abierta
    const r = await p.evaluate(() => {
      const sel = "a[href], button, input, select, textarea, summary, [role=button]";
      const salida = [];
      for (const el of document.querySelectorAll(sel)) {
        const caja = el.getBoundingClientRect();
        const estilo = getComputedStyle(el);
        if (!caja.width || !caja.height || estilo.visibility === "hidden" || el.closest("[hidden]")) continue;
        if (el.classList.contains("saltar") && caja.bottom < 0) continue; // el enlace para saltar solo aparece con el foco
        salida.push({ ok: caja.width >= 43.5 && caja.height >= 43.5, que: `${el.tagName.toLowerCase()} "${(el.textContent || el.getAttribute("aria-label") || "").trim().slice(0, 30)}" ${Math.round(caja.width)}×${Math.round(caja.height)}` });
      }
      return salida;
    });
    total += r.length;
    chicos.push(...r.filter((x) => !x.ok).map((x) => `${nombre}: ${x.que}`));
    await p.context().close();
  }
  anotar("U5", {
    valor: `${((1 - chicos.length / total) * 100).toFixed(1).replace(".", ",")} %`,
    umbral: "100 %",
    pasa: chicos.length === 0,
    detalle: `${total} controles${chicos.length ? `; ${chicos.slice(0, 12).join("; ")}` : ""}`,
  });
}

// ---------------------------------------------------------------- P8 (pantalla = API), P10 y P12
{
  const p = await pagina();
  await panorama(p);
  const api = await p.evaluate(async () => {
    const s = ["hallazgos", "linea", "magnitudes", "reaccion", "temas", "citas", "youtube"];
    return Object.fromEntries(await Promise.all(s.map(async (x) => [x, await (await fetch(`/api/panorama/${x}`)).json()])));
  });

  // P8: hallazgos, filas de cada tabla, totales de A y valores de E y F tal como se muestran
  const diferencias = [];
  const valores = await p.locator(".hallazgo__valor").allInnerTexts();
  if (JSON.stringify(valores) !== JSON.stringify(api.hallazgos.map((h) => h.valor))) diferencias.push("hallazgos");
  const filasEsperadas = {
    linea: api.linea.semanas.length,
    magnitudes: api.magnitudes.puntos.length,
    reaccion: api.reaccion.comunicados.length,
    temas: api.temas.meses.length,
    citas: api.citas.medios.length,
    youtube: api.youtube.puntos.length,
  };
  const formato = new Intl.NumberFormat("es", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const pct = { format: (v) => formato.format(v).replace(/\s?%/, " %") };
  let revisadas = valores.length;
  for (const [seccion, n] of Object.entries(filasEsperadas)) {
    const g = p.locator(`[data-seccion=${seccion}]`);
    await g.getByRole("button", { name: "Ver tabla" }).click();
    const filas = await g.locator("tbody tr").count();
    revisadas += 1;
    if (filas !== n) diferencias.push(`${seccion}: ${filas} filas, API ${n}`);
    if (seccion === "linea") {
      for (const grupo of ["coinciden", "difieren", "sin_datos"]) {
        const celdas = await g.locator(`td[data-columna=${grupo}]`).allInnerTexts();
        const suma = celdas.reduce((a, c) => a + Number(c.replace(/\D/g, "")), 0);
        const esperado = api.linea.semanas.reduce((a, s) => a + s[grupo], 0);
        revisadas += 1;
        if (suma !== esperado) diferencias.push(`A ${grupo}: ${suma} vs ${esperado}`);
      }
    }
    if (seccion === "citas") {
      for (const actor of api.citas.actores) {
        const celdas = await g.locator(`td[data-columna=${actor}]`).allInnerTexts();
        const esperado = api.citas.medios.map((m) => pct.format(m[actor]));
        revisadas += celdas.length;
        if (JSON.stringify(celdas) !== JSON.stringify(esperado)) diferencias.push(`E ${actor}`);
      }
    }
    await g.getByRole("button", { name: "Ver gráfico" }).click();
  }
  const tasa = await p.locator("[data-indicador=tasa] .indicador__valor").allInnerTexts();
  revisadas += tasa.length;
  if (JSON.stringify(tasa) !== JSON.stringify(api.youtube.indicador_tasa.map((i) => pct.format(i.mediana)))) diferencias.push("F indicador 1");
  anotar("P8", { valor: diferencias.length ? `${diferencias.length} diferencias` : "100 %", umbral: "100 %", pasa: diferencias.length === 0, detalle: [`${revisadas} cifras revisadas contra la API`, ...diferencias].join("; ") });

  // P10: emergente, tabla con descarga y "Cómo leer" en cada gráfico; "Descriptivo" solo en C
  const SOBRE = { linea: ".zona-toque", magnitudes: "circle.punto", reaccion: ".zona-toque", temas: "svg", citas: ".medidores__fila", youtube: "circle.punto" };
  const faltas = [];
  for (const [seccion, sel] of Object.entries(SOBRE)) {
    const g = p.locator(`[data-seccion=${seccion}]`);
    await g.scrollIntoViewIfNeeded();
    if (!(await g.locator("[data-como-leer]").count())) faltas.push(`${seccion}: sin Cómo leer`);
    const objetivo = g.locator(sel).nth(sel === "svg" ? 0 : 1);
    const caja = await objetivo.boundingBox();
    await p.mouse.move(caja.x + caja.width / 2, caja.y + Math.min(caja.height / 2, 60));
    await p.waitForTimeout(80);
    if (!(await g.locator(".emergente").count())) faltas.push(`${seccion}: sin emergente`);
    const [descarga] = await Promise.all([p.waitForEvent("download"), g.locator("[data-descargar]").click()]);
    const csv = fs.readFileSync(await descarga.path(), "utf8");
    if (csv.trim().split("\n").length < 2) faltas.push(`${seccion}: CSV vacío`);
  }
  const descriptivos = await p.evaluate(() => [...document.querySelectorAll("section.grafico")].filter((g) => g.querySelector("[data-descriptivo]")).map((g) => g.dataset.seccion));
  if (JSON.stringify(descriptivos) !== JSON.stringify(["reaccion"])) faltas.push(`Descriptivo en: ${descriptivos.join(", ")}`);
  const tarjetaDescriptiva = await p.evaluate(() => [...document.querySelectorAll(".hallazgo")].filter((h) => h.querySelector("[data-descriptivo]")).map((h) => h.className));
  if (tarjetaDescriptiva.length !== 1 || !tarjetaDescriptiva[0].includes("reaccion")) faltas.push("Descriptivo en los hallazgos");
  anotar("P10", { valor: faltas.length ? `${6 - new Set(faltas.map((f) => f.split(":")[0])).size}/6` : "6/6", umbral: "100 %", pasa: faltas.length === 0, detalle: faltas.join("; ") });

  // P12: E en orden alfabético, F en orden fijo de tipos, B sin el medio (ni en la tabla ni en la API)
  const p12 = [];
  const medios = await p.locator("[data-medio]").evaluateAll((els) => els.map((e) => e.dataset.medio));
  if (JSON.stringify(medios) !== JSON.stringify([...medios].sort((a, b) => a.localeCompare(b, "es")))) p12.push("E no alfabético");
  const tipos = await p.locator("[data-indicador=tasa] [data-tipo]").evaluateAll((els) => els.map((e) => e.dataset.tipo));
  if (JSON.stringify(tipos) !== JSON.stringify(["medio", "oficial", "otros"])) p12.push("F fuera del orden fijo");
  const clavesB = new Set(api.magnitudes.puntos.flatMap((x) => Object.keys(x)));
  if (clavesB.has("medio")) p12.push("B trae el medio en la API");
  const clavesF = new Set(api.youtube.puntos.flatMap((x) => Object.keys(x)));
  if ([...clavesF].some((k) => /id|canal|nombre|titulo/.test(k))) p12.push("F trae identificadores");
  const b = p.locator("[data-seccion=magnitudes]");
  await b.getByRole("button", { name: "Ver tabla" }).click();
  if ((await b.locator("th").allInnerTexts()).some((t) => /medio/i.test(t))) p12.push("B muestra el medio");
  anotar("P12", { valor: p12.length, umbral: "0", pasa: p12.length === 0, detalle: p12.join("; ") || "E alfabético, F en orden fijo, B y F sin medio ni ids" });
  await p.context().close();
}

await navegador.close();
fs.mkdirSync(path.dirname(SALIDA), { recursive: true });
fs.writeFileSync(SALIDA, `${JSON.stringify(resultados, null, 1)}\n`);
console.log(`\nResultados en ${SALIDA}\nCapturas en ${CAPTURAS}`);
