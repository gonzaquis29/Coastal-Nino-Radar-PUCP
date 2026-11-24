// Ajustes de diseño (docs/app/definicion.md, sección 15): D1 a D7 con la API real corriendo y el Edge instalado,
// y capturas para comparar antes y después. La medición no escribe en el registro de uso (bloquea /api/eventos).
//
//   node medir/diseno.mjs antes|despues     (RADAR_URL=http://localhost:8000 por defecto)
//   -> ../data/processed/app/diseno-<fase>.json   y   medir/capturas-diseno/<fase>/*.png
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const BASE = process.env.RADAR_URL ?? "http://localhost:8000";
const FASE = process.argv[2] ?? "despues";
const CAPTURAS = path.join(AQUI, "capturas-diseno", FASE);
const SALIDA = path.resolve(AQUI, `../../data/processed/app/diseno-${FASE}.json`);
// Texto inventado con cercanía: muestra el texto citado del ENFEN y «Qué hacer en tu zona»
const CERCANIA = "El mar frente a la costa norte sigue más caliente de lo normal y se esperan lluvias por El Niño costero";
const PANTALLAS = ["hoy", "verificar", "preguntar", "panorama", "metodologia"];
// La línea vertical de la línea de tiempo es su eje, no un adorno (sección 15.3, regla 2)
const EJES = ".linea-tiempo, .linea-tiempo *";
const FLOTANTES = ".glosario__hoja, .emergente, [role=dialog], [role=dialog] *";

const resultados = { fase: FASE, fecha: new Date().toISOString(), base: BASE, criterios: {} };
const anotar = (id, datos) => {
  resultados.criterios[id] = datos;
  console.log(`[${datos.pasa ? "ok" : "NO"}] ${id}: ${datos.valor} (umbral ${datos.umbral})${datos.detalle ? ` — ${datos.detalle}` : ""}`);
};

fs.mkdirSync(CAPTURAS, { recursive: true });
const navegador = await chromium.launch({ channel: process.env.RADAR_CANAL ?? "msedge" });

async function pagina({ ancho = 1280, tema = "light" } = {}) {
  const contexto = await navegador.newContext({
    viewport: { width: ancho, height: ancho < 768 ? 812 : 900 },
    colorScheme: tema,
    reducedMotion: "reduce",
  });
  await contexto.addInitScript(() => localStorage.setItem("radar.zona", "costa_norte"));
  await contexto.addInitScript((t) => localStorage.setItem("radar.tema", t), tema === "dark" ? "oscuro" : "claro");
  await contexto.route("**/api/eventos", (r) => r.fulfill({ status: 204, body: "" }));
  await contexto.addInitScript(() => {
    navigator.sendBeacon = () => true;
  });
  const p = await contexto.newPage();
  p.setDefaultTimeout(60_000);
  return p;
}

async function abrir(p, pantalla) {
  if (pantalla === "verificar") {
    await p.goto(`${BASE}/`);
    await p.locator("#texto").fill(CERCANIA);
    await p.getByRole("button", { name: "Comparar con el ENFEN", exact: true }).click();
    await p.locator("[data-tipo]").waitFor();
    await p.waitForFunction(() => !document.querySelector(".respuesta.atenuado"));
  } else if (pantalla === "preguntar") {
    await p.goto(`${BASE}/preguntar`);
    await p.locator("input, textarea").first().fill("¿Qué recomienda el ENFEN para la pesca?");
    await p.getByRole("button", { name: "Preguntar", exact: true }).click();
    await p.locator(".burbuja--respuesta").first().waitFor();
  } else {
    await p.goto(`${BASE}/${pantalla === "hoy" ? "" : pantalla}`);
    await p.waitForLoadState("networkidle");
  }
  await p.waitForTimeout(300);
}

// ---------------------------------------------------------------- D1: niveles del Senamhi con el mismo ancho
{
  const anchos = [];
  let filas = 0;
  for (const ancho of [360, 375, 1280])
    for (const tema of ["light", "dark"]) {
      const p = await pagina({ ancho, tema });
      await abrir(p, "hoy");
      const w = await p.$$eval(".avisos__nivel", (els) => els.map((e) => e.getBoundingClientRect().width));
      filas = Math.max(filas, w.length);
      anchos.push(...w);
      await p.context().close();
    }
  const dif = anchos.length ? Math.max(...anchos) - Math.min(...anchos) : 0;
  anotar("D1", {
    valor: `${dif.toFixed(1)} px`,
    umbral: "0 px",
    pasa: anchos.length > 0 && dif < 0.5,
    detalle: `${filas} avisos vigentes; anchos ${[...new Set(anchos.map((x) => Math.round(x)))].join(", ")} px`,
  });
}

// ---------------------------------------------------------------- D2, D3 y D7 en todas las pantallas, claro y oscuro
{
  const franjas = [];
  const estirables = [];
  const sombras = [];
  for (const tema of ["light", "dark"])
    for (const ancho of [375, 1280])
      for (const pantalla of PANTALLAS) {
        const p = await pagina({ ancho, tema });
        await abrir(p, pantalla);
        const r = await p.evaluate(
          ({ EJES, FLOTANTES }) => {
            const salida = { franjas: [], estirables: [], sombras: [] };
            for (const el of document.querySelectorAll("body *")) {
              const c = getComputedStyle(el);
              const caja = el.getBoundingClientRect();
              if (!caja.width || !caja.height) continue;
              const nombre = `${el.tagName.toLowerCase()}.${[...el.classList].join(".")}`;
              const color = c.borderLeftColor;
              // franja: el borde izquierdo de 2 px o más, distinto del derecho (un borde en los cuatro lados no lo es)
              const unLado = parseFloat(c.borderRightWidth) < parseFloat(c.borderLeftWidth) || c.borderRightColor !== color;
              if (parseFloat(c.borderLeftWidth) >= 2 && c.borderLeftStyle !== "none" && !color.endsWith(", 0)")
                  && unLado && !el.matches(EJES))
                salida.franjas.push(nombre);
              if (el.tagName === "TEXTAREA" && c.resize !== "none") salida.estirables.push(nombre);
              const externas = c.boxShadow !== "none" && c.boxShadow.split(/,(?![^(]*\))/).some((s) => !s.includes("inset"));
              if (externas && !el.matches(FLOTANTES) && el !== document.activeElement) salida.sombras.push(nombre);
            }
            return salida;
          },
          { EJES, FLOTANTES },
        );
        const lugar = `${pantalla} ${ancho} ${tema === "dark" ? "oscuro" : "claro"}`;
        franjas.push(...r.franjas.map((x) => `${lugar}: ${x}`));
        estirables.push(...r.estirables.map((x) => `${lugar}: ${x}`));
        if (pantalla === "preguntar" || pantalla === "panorama") sombras.push(...r.sombras.map((x) => `${lugar}: ${x}`));
        await p.screenshot({ path: path.join(CAPTURAS, `${pantalla}-${ancho}-${tema === "dark" ? "oscuro" : "claro"}.png`), fullPage: true });
        await p.context().close();
      }
  const unicos = (xs) => [...new Set(xs.map((x) => x.split(": ")[1]))];
  anotar("D2", { valor: franjas.length, umbral: "0", pasa: franjas.length === 0, detalle: unicos(franjas).slice(0, 8).join("; ") });
  anotar("D3", { valor: estirables.length, umbral: "0", pasa: estirables.length === 0, detalle: unicos(estirables).join("; ") });
  anotar("D7", { valor: sombras.length, umbral: "0", pasa: sombras.length === 0, detalle: unicos(sombras).slice(0, 8).join("; ") });
}

// ---------------------------------------------------------------- D4: un solo fondo en Hoy
{
  const distintos = [];
  for (const tema of ["light", "dark"]) {
    const p = await pagina({ ancho: 1280, tema });
    await abrir(p, "hoy");
    const r = await p.evaluate(() => {
      const fondo = (el) => {
        for (let e = el; e; e = e.parentElement) {
          const c = getComputedStyle(e).backgroundColor;
          if (c !== "rgba(0, 0, 0, 0)" && c !== "transparent") return c;
        }
        return "";
      };
      return { pagina: fondo(document.body), mensaje: fondo(document.querySelector(".hoy__mensaje")) };
    });
    if (r.pagina !== r.mensaje) distintos.push(`${tema === "dark" ? "oscuro" : "claro"}: ${r.mensaje} sobre ${r.pagina}`);
    await p.context().close();
  }
  anotar("D4", { valor: distintos.length ? "distinto" : "igual", umbral: "igual", pasa: !distintos.length, detalle: distintos.join("; ") });
}

// ---------------------------------------------------------------- D5: interlineado del párrafo de la zona
{
  const difs = [];
  for (const ancho of [375, 1280]) {
    const p = await pagina({ ancho });
    await abrir(p, "hoy");
    const pasos = await p.evaluate(() => {
      const par = [...document.querySelectorAll(".zona p")].find((e) => e.querySelector(".palabra"));
      if (!par) return [];
      const rango = document.createRange();
      rango.selectNodeContents(par);
      const tops = [...new Set([...rango.getClientRects()].filter((r) => r.height > 4 && r.height < 40).map((r) => Math.round(r.bottom)))].sort((a, b) => a - b);
      const lineas = [];
      for (const t of tops) if (!lineas.length || t - lineas.at(-1) > 6) lineas.push(t);
      return lineas.slice(1).map((t, i) => t - lineas[i]);
    });
    if (pasos.length) difs.push({ ancho, pasos, dif: Math.max(...pasos) - Math.min(...pasos) });
    await p.context().close();
  }
  const peor = difs.length ? Math.max(...difs.map((d) => d.dif)) : 0;
  anotar("D5", {
    valor: `${peor} px`,
    umbral: "≤ 2 px",
    pasa: difs.length > 0 && peor <= 2,
    detalle: difs.map((d) => `${d.ancho} px: pasos ${d.pasos.join(", ")}`).join("; "),
  });
}

// ---------------------------------------------------------------- D6: títulos de avisos a 375 px
{
  const p = await pagina({ ancho: 375 });
  await abrir(p, "hoy");
  const lineas = await p.$$eval(".avisos__texto > a, .avisos__texto > span:first-child", (els) =>
    els.map((e) => {
      const rango = document.createRange();
      rango.selectNodeContents(e);
      return [...new Set([...rango.getClientRects()].map((r) => Math.round(r.top)))].length;
    }),
  );
  await p.context().close();
  const peor = lineas.length ? Math.max(...lineas) : 0;
  anotar("D6", { valor: peor, umbral: "≤ 3", pasa: lineas.length > 0 && peor <= 3, detalle: `líneas por título: ${lineas.join(", ")}` });
}

await navegador.close();
fs.writeFileSync(SALIDA, JSON.stringify(resultados, null, 2));
console.log(`\nResultados en ${SALIDA}\nCapturas en ${CAPTURAS}`);
