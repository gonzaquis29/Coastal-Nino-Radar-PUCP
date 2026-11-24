"use strict";
// Centro de Monitoreo: mapa satelital (MapLibre) + panel. Se comunica con Streamlit (src/centro.py) por postMessage.
const $ = s => document.querySelector(s), NS = "http://www.w3.org/2000/svg";
const IC = {
  todo: "M4 6h16M4 12h16M4 18h16",
  calor: "M12 8a4 4 0 100 8 4 4 0 000-8M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5",
  "lluvias e inundaciones": "M7 14a4 4 0 01.5-8 5 5 0 019.5 1.5A3.3 3.3 0 0117 14M8 17l-1 4M13 17l-1 4M18 17l-1 4",
  viento: "M3 9h11a3 3 0 10-3-3M3 14h15a3 3 0 11-3 3M3 19h7",
  "frío y heladas": "M12 2v20M3.500 7l17 10M20.500 7l-17 10",
  "oleaje anómalo": "M2 10c3-4 5-4 8 0s5 4 8 0l4-2M2 17c3-4 5-4 8 0s5 4 8 0l4-2",
  sismo: "M2 12h4l2-6 4 13 3-10 2 3h5",
  "El Niño Costero": "M10 4v10a4 4 0 104 0V4a2 2 0 00-4 0M12 9v8",
  otro: "M12 8v.1M12 11v6"
};
const NOM = { todo: "Todos los avisos", calor: "Calor", "lluvias e inundaciones": "Lluvias", viento: "Viento", "frío y heladas": "Frío", "oleaje anómalo": "Oleaje", sismo: "Sismos", "El Niño Costero": "El Niño Costero", otro: "Otros" };
const NIV = { amarillo: 1, naranja: 2, rojo: 3 };
const S = { pel: "todo", dia: 0, dep: null, lugar: null, aviso: null, resp: null, espera: null, q: "", vista: null };
let M, L, D = null, ultimaFirma;

function h(t, at = {}, ...hijos) {
  const e = document.createElement(t);
  for (const [k, v] of Object.entries(at)) {
    if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) e.setAttribute(k, v === true ? "" : v);
  }
  for (const c of hijos.flat()) if (c != null && c !== false) e.append(c);
  return e;
}
function g(t, at = {}) { const e = document.createElementNS(NS, t); for (const k in at) e.setAttribute(k, at[k]); return e; }
function ico(p) { const s = g("svg", { class: "ic", viewBox: "0 0 24 24", "aria-hidden": "true" }); s.append(g("path", { d: IC[p] || IC.otro })); return s; }
const MIN = new Set(["DE", "DEL", "LA", "LAS", "LOS", "Y", "EL"]);
const tit = s => s.split(" ").filter(Boolean).map((w, i) => i && MIN.has(w.toUpperCase()) ? w.toLowerCase() : w[0].toUpperCase() + w.slice(1).toLowerCase()).join(" ")
  .replace(/^Ancash$/, "Áncash").replace(/^Apurimac$/, "Apurímac").replace(/^Huanuco$/, "Huánuco").replace(/^Junin$/, "Junín").replace(/^San Martin$/, "San Martín");
const frase = s => { s = s.replace(/\s*\((EXTENSI|ACTUALI).*\)/i, "").toLowerCase(); return s ? s[0].toUpperCase() + s.slice(1) : ""; };
const sinT = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();
const F = s => new Date(s.length > 10 ? s.replace(" ", "T") : s + "T00:00:00");
const fecha = (s, o = { weekday: "short", day: "numeric", month: "short" }) => F(s).toLocaleDateString("es-PE", o);
const enlace = (u, t) => /^https?:\/\//.test(u) ? h("a", { href: u, target: "_blank", rel: "noopener" }, t) : t;
const km = (a, b, c, d) => { const r = Math.PI / 180, x = Math.sin((c - a) * r / 2) ** 2 + Math.cos(a * r) * Math.cos(c * r) * Math.sin((d - b) * r / 2) ** 2; return 12742 * Math.asin(Math.sqrt(x)); };
const lista = a => a.length < 2 ? a.join("") : a.slice(0, -1).join(", ") + " y " + a[a.length - 1];
const plural = (n, a, b) => `${n} ${n === 1 ? a : b}`;

/* ---- datos derivados ---- */
const dia = i => { const d = F(D.ahora); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() + i); return d; };
const hace = s => (F(D.ahora) - F(s)) / 864e5;
const avisos = () => D.eventos.filter(e => e.fuente === "SENAMHI" && e.inicio && e.fin);
const enDia = (e, i) => F(e.inicio) < dia(i + 1) && F(e.fin) >= (i === 0 ? F(D.ahora) : dia(i));
const avDia = (i = S.dia) => avisos().filter(e => enDia(e, i));
const avFil = () => avDia().filter(e => S.aviso ? e.id === S.aviso : S.pel === "todo" || e.peligro === S.pel);
const sismos = (dias = 30) => D.eventos.filter(e => e.fuente === "USGS" && hace(e.inicio) <= dias).sort((a, b) => F(b.inicio) - F(a.inicio));
const enfen = () => D.eventos.filter(e => e.fuente === "ENFEN").sort((a, b) => F(b.publicado) - F(a.publicado))[0];
const etiq = i => i === 0 ? "Hoy" : i === 1 ? "Mañana" : dia(i).toLocaleDateString("es-PE", { weekday: "long" }).replace(/^./, c => c.toUpperCase());
const nDias = () => Math.min(7, Math.max(1, ...avisos().map(a => Math.floor((F(a.fin) - dia(0)) / 864e5) + 1)));
const cuando = s => F(s.inicio).toLocaleString("es-PE", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false });

/* ---- zonas oficiales ---- */
const iso = i => { const d = dia(i); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const conZona = a => !!D.zonas[a.id];
const zdia = (a, i) => D.zonas[a.id]?.[iso(i)];
const NN = ["Sin aviso", "", "Amarillo", "Naranja", "Rojo"], NUM = { amarillo: 2, naranja: 3, rojo: 4 };
const idxDep = {};
// nivel (0,2,3,4) de un aviso en un día para un distrito (índice) o el máximo de un departamento
function nivelEn(a, i, dep, k) {
  const z = zdia(a, i);
  if (!z) return conZona(a) ? 0 : (enDia(a, i) && a.deps.includes(dep) ? NUM[a.nivel] : 0);
  if (F(z.fin) < F(D.ahora)) return 0;
  return k != null ? +z.d[k] : Math.max(0, ...idxDep[dep].map(j => +z.d[j]));
}
const maxNivel = (a, dep, k) => Math.max(0, ...Array.from({ length: nDias() }, (_, i) => nivelEn(a, i, dep, k)));

/* ---- mapa ---- */
let map, listo = false, marcas = [], nombres = [], sobre = null, zonaPedida = "";
const PERU = [[-81.4, -18.4], [-68.6, 0]];
const ancho = () => innerWidth > 900;
const pad = () => ancho() ? { left: 40, right: 490, top: 140, bottom: 130 } : { left: 20, right: 20, top: 165, bottom: innerHeight * .41 + 150 };
function armarMapa() {
  L.forEach((l, i) => (idxDep[l[0]] ||= []).push(i));
  map = new maplibregl.Map({
    container: "mapa", bounds: PERU, fitBoundsOptions: { padding: pad() }, minZoom: 2, maxZoom: 13, maxPitch: 65, attributionControl: false,
    style: { version: 8, sources: {
      sat: { type: "raster", tileSize: 256, maxzoom: 13, tiles: ["https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg"], attribution: '<a href="https://s2maps.eu" target="_blank" rel="noopener">Sentinel-2 cloudless</a> por EOX (Copernicus 2016, CC BY 4.0). Relieve: Terrain Tiles. Límites: IGN/OCHA' },
      dem: { type: "raster-dem", tileSize: 256, maxzoom: 11, encoding: "terrarium", tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"] }
    }, layers: [{ id: "fondo", type: "background", paint: { "background-color": "#0a1a22" } }, { id: "sat", type: "raster", source: "sat", paint: { "raster-brightness-max": .86, "raster-saturation": -.12 } }] }
  });
  map.addControl(new maplibregl.AttributionControl({ compact: false }), "bottom-left");
  map.on("load", () => {
    const vacio = { type: "FeatureCollection", features: [] };
    for (const [k, d] of [["mascara", M.mascara], ["zona", vacio], ["deps", M.deps], ["provs", M.provs], ["sis", vacio], ["nino", vacio]]) map.addSource(k, { type: "geojson", data: d, ...(k === "deps" ? { promoteId: "id" } : {}) });
    const capa = (id, source, type, paint, extra = {}) => map.addLayer({ id, source, type, paint, ...extra });
    const cn = ["match", ["get", "n"], 4, "#ff4747", 3, "#ff8a3c", "#ffd02e"];
    capa("mascara", "mascara", "fill", { "fill-color": "#061014", "fill-opacity": .62 });
    capa("zona", "zona", "fill", { "fill-color": cn, "fill-opacity": .5, "fill-antialias": false });
    capa("zonal", "zona", "line", { "line-color": cn, "line-width": 1, "line-opacity": .85 });
    capa("nino", "nino", "fill", { "fill-color": "#8fe3cf", "fill-opacity": .4 });
    capa("depf", "deps", "fill", { "fill-color": "#fff", "fill-opacity": ["case", ["boolean", ["feature-state", "sobre"], false], .14, 0] });
    capa("provs", "provs", "line", { "line-color": "#fff", "line-opacity": .4, "line-width": .7 }, { filter: ["==", ["get", "dep"], ""] });
    capa("depl", "deps", "line", { "line-color": "#fff", "line-opacity": .55, "line-width": .9 });
    capa("sel", "deps", "line", { "line-color": "#fff", "line-width": 2.6 }, { filter: ["==", ["get", "id"], ""] });
    capa("sis", "sis", "circle", { "circle-radius": ["interpolate", ["exponential", 1.6], ["get", "mag"], 3.5, ...(ancho() ? [4, 5, 9, 6, 16, 7, 26] : [3, 5, 5, 6, 9, 7, 14])], "circle-color": "#b68cff", "circle-opacity": ["case", ["get", "nuevo"], .9, .45], "circle-stroke-color": "#fff", "circle-stroke-width": 1.4 });
    map.on("mousemove", e => {
      const s = map.queryRenderedFeatures(e.point, { layers: ["sis"] })[0], f = map.queryRenderedFeatures(e.point, { layers: ["depf"] })[0], id = f?.properties.id ?? null;
      if (id !== sobre) { if (sobre) map.setFeatureState({ source: "deps", id: sobre }, { sobre: false }); if (id) map.setFeatureState({ source: "deps", id }, { sobre: true }); sobre = id; }
      map.getCanvas().style.cursor = s || id ? "pointer" : "";
      if (s) tip(e.originalEvent, "Magnitud " + (+s.properties.mag).toFixed(1), s.properties.txt); else if (id) tipDep(e.originalEvent, id); else quitaTip();
    });
    map.on("mouseout", quitaTip);
    map.on("click", e => {
      const s = map.queryRenderedFeatures(e.point, { layers: ["sis"] })[0]; if (s) return open(s.properties.url, "_blank", "noopener");
      const f = map.queryRenderedFeatures(e.point, { layers: ["depf"] })[0]; if (f && f.properties.id !== S.dep) elegir(f.properties.id);
    });
    for (const f of M.deps.features) { const el = h("div", { class: "nom" }, tit(f.properties.id)); nombres.push([f.properties, el, new maplibregl.Marker({ element: el }).setLngLat(f.properties.c).addTo(map)]); }
    map.on("zoom", verNombres); verNombres();
    map.addSource("dem2", { type: "raster-dem", tileSize: 256, maxzoom: 11, encoding: "terrarium", tiles: map.getStyle().sources.dem.tiles });
    map.addLayer({ id: "sombra", type: "hillshade", source: "dem2", paint: { "hillshade-exaggeration": .35, "hillshade-shadow-color": "#02090c" } }, "mascara");
    map.setTerrain({ source: "dem", exaggeration: 1.6 });
    listo = true; capas();
  });
  let w = innerWidth; addEventListener("resize", () => { if (Math.abs(innerWidth - w) > 40) { w = innerWidth; encuadre(); } });
}
const CHICOS = new Set(["CALLAO", "TUMBES", "LAMBAYEQUE", "MOQUEGUA", "TACNA", "HUANCAVELICA", "APURIMAC", "PASCO", "HUANUCO", "ICA", "SAN MARTIN", "CAJAMARCA"]);
function verNombres() { const z = map.getZoom(); for (const [p, el] of nombres) el.style.visibility = (S.dep ? p.id === S.dep && !S.lugar : z > 5.6 || (z > 4.3 && !CHICOS.has(p.id))) ? "" : "hidden"; }
function encuadre() {
  if (!map) return;
  const b = S.dep ? M.deps.features.find(f => f.properties.id === S.dep).properties.b : null, r3 = $("#rel").getAttribute("aria-pressed") === "true";
  map.fitBounds(b ? [[b[0], b[1]], [b[2], b[3]]] : PERU, { padding: pad(), pitch: S.dep && r3 ? 45 : 0, bearing: 0, duration: matchMedia("(prefers-reduced-motion:reduce)").matches ? 0 : 1600 });
}
async function capas() {
  if (!D || !listo) return;
  verNombres();
  map.setFilter("sel", ["==", ["get", "id"], S.dep || ""]); map.setFilter("provs", ["==", ["get", "dep"], S.dep || ""]);
  const fc = fs => ({ type: "FeatureCollection", features: fs }), todos = S.pel === "sismo", e = enfen();
  map.getSource("nino").setData(fc(S.pel === "El Niño Costero" && e ? M.deps.features.filter(f => e.deps.includes(f.properties.id)) : []));
  const ss = todos ? sismos(30) : S.pel === "todo" && S.dia === 0 && !S.aviso ? sismos(7).filter(s => s.mag >= 5.5) : [];
  map.getSource("sis").setData(fc(ss.sort((a, b) => b.mag - a.mag).map(s => ({ type: "Feature", properties: { mag: s.mag, nuevo: hace(s.inicio) < 2, url: s.url, txt: `${cuando(s)}. ${s.ref}. ${s.texto}` }, geometry: { type: "Point", coordinates: [s.lon, s.lat] } }))));
  marcas.forEach(m => m.remove()); marcas = [];
  if (ss.length) marcas.push(new maplibregl.Marker({ element: h("div", { class: "pulso", title: "Ver en USGS", onclick: () => open(ss[0].url, "_blank", "noopener") }) }).setLngLat([ss[0].lon, ss[0].lat]).addTo(map));
  if (S.lugar) marcas.push(new maplibregl.Marker({ color: "#f1f6f4" }).setLngLat([S.lugar[4], S.lugar[3]]).addTo(map));
  const clave = todos || S.pel === "El Niño Costero" ? "" : `${S.aviso || S.pel}_${iso(S.dia)}`;
  zonaPedida = clave;
  let datos = fc([]);
  if (clave) try { const r = await fetch(`zonas/${encodeURIComponent(clave)}.json?v=${encodeURIComponent(D.act)}`); if (r.ok) datos = await r.json(); } catch { /* sin zona publicada */ }
  if (zonaPedida === clave) map.getSource("zona").setData(datos);
}
function tip(e, a, b) {
  const t = $("#tip"); t.replaceChildren(h("b", {}, a), b); t.hidden = false;
  t.style.left = Math.min(e.clientX + 16, innerWidth - t.offsetWidth - 10) + "px"; t.style.top = Math.max(8, e.clientY - t.offsetHeight - 12) + "px";
}
function quitaTip() { $("#tip").hidden = true; }
function tipDep(e, id) {
  if (!D) return;
  if (S.pel === "sismo") return tip(e, tit(id), "Clic para ver el detalle");
  if (S.pel === "El Niño Costero") return tip(e, tit(id), enfen()?.deps.includes(id) ? "En la zona costera que cita el ENFEN" : "Fuera de la zona costera que cita el ENFEN");
  const a = avFil().map(x => [x, nivelEn(x, S.dia, id)]).filter(x => x[1]);
  tip(e, tit(id), a.length ? "Nivel más alto: " + a.map(([x, n]) => `${NOM[x.peligro].toLowerCase()} ${NN[n].toLowerCase()}`).join(", ") : "Sin zonas de aviso este día");
}

/* ---- controles ---- */
function controles() {
  const n = {};
  avDia().forEach(a => n[a.peligro] = (n[a.peligro] || 0) + 1);
  const pel = ["todo", ...["calor", "lluvias e inundaciones", "viento", "frío y heladas", "oleaje anómalo", "otro"].filter(p => avisos().some(a => a.peligro === p)), "sismo", "El Niño Costero"];
  const cuenta = p => p === "sismo" ? sismos().length : p === "todo" ? avDia().length : n[p] || 0;
  $("#filtros").replaceChildren(...pel.map(p => h("button", { "aria-pressed": String(S.pel === p && !S.aviso), onclick: () => { S.pel = p; S.aviso = null; S.vista = null; pinta(); } },
    ico(p), NOM[p], p === "El Niño Costero" ? null : h("i", {}, cuenta(p)))));
  const sin = S.pel === "sismo" || S.pel === "El Niño Costero";
  $("#dias").hidden = sin;
  $("#dias").replaceChildren(...Array.from({ length: nDias() }, (_, i) => h("button", { "aria-pressed": String(S.dia === i), onclick: () => { S.dia = i; S.aviso = null; pinta(); } },
    h("b", {}, etiq(i)), h("span", {}, plural(avDia(i).length, "aviso", "avisos")))));
  const it = (c, t) => h("span", {}, h("s", { style: "background:" + c }), t);
  $("#leyenda").replaceChildren(...(S.pel === "sismo" ? [it("var(--sismo)", "Sismo: a mayor círculo, mayor magnitud")] : S.pel === "El Niño Costero" ? [it("var(--acento)", "Departamentos costeros que cita el ENFEN")]
    : [it("var(--n2)", "Amarillo"), it("var(--n3)", "Naranja"), it("var(--n4)", "Rojo"), S.pel === "todo" && S.dia === 0 && !S.aviso ? it("var(--sismo)", "Sismo 5.5 o más, 7 días") : null].filter(Boolean)));
  $("#volver").hidden = !S.dep;
}
function elegir(dep, lugar = null) {
  Object.assign(S, { dep, lugar, resp: null, aviso: null, q: "", vista: null });
  pinta(); encuadre(); $("#panel").scrollTop = 0; quitaTip();
}

/* ---- panel ---- */
const ext = (u, t) => /^https?:\/\//.test(u) ? h("a", { href: u, target: "_blank", rel: "noopener", class: "ext" }, t) : t;
const numAv = a => a.id.split("-")[1];
function tarjeta(a, n, nota) {
  const ver = () => { S.aviso = S.aviso === a.id ? null : a.id; if (S.aviso && !zdia(a, S.dia)) { const i = Array.from({ length: nDias() }, (_, k) => k).find(k => zdia(a, k)); if (i != null) S.dia = i; } pinta(); };
  return h("div", { class: "aviso" + (S.aviso === a.id ? " on" : "") },
    h("button", { class: "cab", "aria-pressed": String(S.aviso === a.id), onclick: ver }, ico(a.peligro), h("span", {}, h("b", {}, frase(a.titulo)), h("span", { class: "mut" }, `${fecha(a.inicio)} al ${fecha(a.fin)}`, nota ? h("br") : null, nota || null)), h("span", { class: "niv n" + n }, NN[n])),
    h("div", { class: "acc" }, ext(a.url, `Senamhi, aviso ${numAv(a)}`)),
    h("details", {}, h("summary", {}, "Leer texto oficial"), h("p", {}, a.texto)));
}
const notaSismo = (s, ref = s.ref) => h("div", {}, h("button", { class: "destaca", onclick: () => { S.pel = "sismo"; S.aviso = null; if (!S.dep) S.vista = null; pinta(); } },
  h("strong", {}, s.mag.toFixed(1)), h("span", {}, h("b", {}, "Sismo reciente"), h("br"), h("span", { class: "mut" }, `${cuando(s)}, ${ref}`))), h("p", { class: "mut", style: "margin:7px 0 0" }, ext(s.url, "Ver en USGS")));
function tablaSismos(ss, conKm) {
  if (!ss.length) return h("p", { class: "mut" }, "USGS no registra sismos de magnitud 3.5 o más en este ámbito en los últimos 30 días.");
  return h("table", {}, h("tr", {}, h("th", {}, "Mag."), h("th", {}, "Cuándo"), h("th", {}, conKm ? "Distancia" : "Dónde"), h("th", {}, "Fuente")),
    ss.slice(0, 12).map(s => h("tr", {}, h("td", {}, h("b", {}, s.mag.toFixed(1))), h("td", {}, cuando(s)), h("td", {}, conKm ? `${Math.round(s.km)} km` : s.ref), h("td", {}, ext(s.url, "USGS")))));
}
const actualiza = () => h("button", { class: "bot", disabled: S.espera === "actualizar", onclick: () => { S.espera = "actualizar"; envia({ accion: "actualizar" }); panel(); } }, S.espera === "actualizar" ? "Actualizando, tarda cerca de 2 min" : "Actualizar datos");
const pie = () => h("div", { class: "pie" }, h("p", {}, "Reúne lo que publican fuentes oficiales. No predice ni reemplaza sus alertas."), h("button", { class: "volver2", onclick: () => { S.vista = "fuentes"; pinta(); $("#panel").scrollTop = 0; } }, "De dónde salen los datos"));
function panel() {
  const x = S.vista === "fuentes" ? pFuentes() : S.dep ? pDep() : S.pel === "sismo" ? pSismos() : S.pel === "El Niño Costero" ? pNino() : pPais();
  $("#panel").replaceChildren(...x.flat(2).filter(Boolean), ...(S.vista ? [] : [pie()]));
}
function pFuentes() {
  const f = (k, nom, que, como, url) => {
    const e = D.estado[k] || {};
    return [h("h3", {}, nom), h("p", { class: "mut" }, que, h("br"), como, h("br"), e.ok ? `Última descarga correcta: ${F(e.ok).toLocaleString("es-PE", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit", hour12: false })}. ${e.n} registros.` : "", e.error ? h("span", { class: "err" }, ` Falló el intento del ${e.error}; se muestra el último dato.`) : null), h("p", {}, ext(url, "Abrir la fuente"))];
  };
  return [h("button", { class: "volver2", onclick: () => { S.vista = null; pinta(); } }, "Volver"), h("h1", {}, "De dónde salen los datos"),
    h("p", { class: "mut" }, "Cada dato se descarga de una web pública y lleva el enlace a su original. No usamos datos inventados ni un modelo que los genere."),
    f("SENAMHI", "Avisos meteorológicos: Senamhi", "Título, nivel, vigencia y texto de cada aviso.", "Se lee la página pública de avisos.", "https://www.senamhi.gob.pe/?p=aviso-meteorologico"),
    f("ZONAS", "Zonas del mapa: Senamhi (IDESEP)", "Polígonos oficiales de cada aviso, por día y nivel. Los bordes se simplifican para dibujarlos.", "Servicio geográfico público WFS.", "https://idesep.senamhi.gob.pe/portalidesep/"),
    f("INDECI", "Notas y medidas: INDECI", "Las 20 notas de prensa más recientes y sus recomendaciones.", "Se leen las páginas de gob.pe, con 2 s entre peticiones.", "https://www.gob.pe/institucion/indeci/noticias"),
    f("USGS", "Sismos: Servicio Geológico de EE. UU.", "Magnitud 3.5 o más, últimos 45 días. Puede diferir del IGP, que no permite el acceso automático.", "API pública.", "https://earthquake.usgs.gov/earthquakes/map/"),
    h("h3", {}, "El Niño Costero: ENFEN"), h("p", { class: "mut" }, "Comunicado oficial N.° 20. Se descargó una vez: no se actualiza solo, porque su web bloquea las lecturas repetidas y no lo eludimos."), h("p", {}, ext(enfen()?.url || "https://enfen.imarpe.gob.pe/", "Abrir la fuente")),
    h("h2", {}, "Qué hace la app con ellos"), h("p", { class: "mut" }, "Clasifica el peligro con palabras clave, ubica tu distrito dentro de cada zona oficial con un punto de referencia (en distritos grandes el nivel puede variar) y extrae recomendaciones textuales. El buscador ordena esos textos con un modelo de similitud, sin reescribirlos."),
    h("p", { class: "mut" }, "Imagen satelital: Sentinel-2 de 2016; es solo fondo, no muestra la situación actual. Código asistido por IA."), actualiza()];
}
function pPais() {
  const a = avDia().filter(e => S.pel === "todo" || e.peligro === S.pel).sort((p, q) => NIV[q.nivel] - NIV[p.nivel]), r = a.filter(e => e.nivel === "rojo").length;
  const cu = S.dia > 1 ? "el " + etiq(S.dia).toLowerCase() : etiq(S.dia).toLowerCase(), q = S.pel === "todo" ? "" : ` de ${NOM[S.pel].toLowerCase()}`;
  const gr = sismos(7).filter(s => s.mag >= 5.5).sort((p, q) => q.mag - p.mag)[0];
  return [h("h1", {}, a.length ? `${plural(a.length, "aviso", "avisos")}${q} ${cu}${r ? `, ${r} de nivel rojo` : ""}` : `Sin avisos${q} publicados para ${cu}`),
    h("p", { class: "mut" }, "Busca tu distrito para ver qué nivel le toca y qué hacer."),
    S.dia === 0 && S.pel === "todo" && gr ? notaSismo(gr) : null,
    a.length ? h("h2", {}, "Toca un aviso para ver su zona") : null, a.map(e => tarjeta(e, NUM[e.nivel]))];
}
function pSismos() {
  const s = sismos(), m = [...s].sort((a, b) => b.mag - a.mag)[0];
  return [h("h1", {}, plural(s.length, "sismo", "sismos") + " en 30 días"), h("p", { class: "mut" }, "Magnitud 3.5 o más, en el Perú y zonas cercanas. El mayor fue:"), m ? notaSismo(m) : null, h("h2", {}, "Más recientes"), tablaSismos(s)];
}
function pNino() {
  const e = enfen(), l = D.enfen || [];
  if (!e) return [h("h1", {}, "Sin comunicado del ENFEN cargado")];
  return [h("h1", {}, "El Niño Costero"),
    h("div", { class: "nino" }, h("span", { class: "mut" }, "Magnitud que señala el ENFEN"), h("h1", {}, e.nivel ? frase(e.nivel) : "No indicada"), h("span", { class: "mut" }, `${e.titulo}, ${fecha(e.publicado, { day: "numeric", month: "long", year: "numeric" })}`)),
    h("p", { style: "margin-top:12px" }, ext(e.url, "Ver en ENFEN")),
    h("h2", {}, "Qué dice el comunicado"), l.slice(0, 2).map(t => h("p", {}, t)),
    l.length > 2 ? h("details", { class: "ancho" }, h("summary", {}, "Leer el comunicado completo"), l.slice(2).map(t => h("p", {}, t))) : null];
}
function pDep() {
  const id = S.dep, lg = S.lugar, k = lg ? L.indexOf(lg) : null, quiere = S.espera === "pregunta", e = enfen();
  const todos = avisos().filter(a => F(a.fin) >= F(D.ahora)), con = todos.map(a => ({ a, hoy: nivelEn(a, 0, id, k), max: maxNivel(a, id, k) })).filter(x => x.max);
  const hoy = con.filter(x => x.hoy).sort((x, y) => y.hoy - x.hoy), prox = con.filter(x => !x.hoy).sort((x, y) => F(x.a.inicio) - F(y.a.inicio)), n = Math.max(0, ...hoy.map(x => x.hoy));
  const rs = L.filter(l => l[0] === id), prom = j => rs.reduce((s, l) => s + l[j], 0) / rs.length, la = lg ? lg[3] : prom(3), lo = lg ? lg[4] : prom(4);
  const ss = sismos().map(s => ({ ...s, km: km(la, lo, s.lat, s.lon) })).filter(s => s.km <= 200), gr = ss.filter(s => s.mag >= 5.5 && hace(s.inicio) <= 7).sort((a, b) => b.mag - a.mag)[0];
  const notas = D.eventos.filter(x => x.fuente === "INDECI" && x.deps.includes(id) && x.publicado && hace(x.publicado) <= 7 && x.peligro !== "otro").sort((a, b) => F(b.publicado) - F(a.publicado));
  const recs = [], vis = new Set(), fu = [...con.map(x => x.a), ...notas];
  for (const p of new Set(con.map(x => x.a.peligro))) { let c = 0; for (const f of fu) if (f.peligro === p) for (const t of f.recs) if (c < 2 && !vis.has(t.slice(0, 60))) { vis.add(t.slice(0, 60)); c++; recs.push([p, t, f]); } }
  const campo = h("input", { placeholder: "¿Cómo me protejo del calor?", "aria-label": "Tu pregunta", value: S.q });
  const cambia = x => { const m = Array.from({ length: nDias() }, (_, i) => [i, nivelEn(x.a, i, id, k)]).filter(y => y[1] > x.hoy).sort((p, q) => q[1] - p[1])[0]; return m && x.hoy ? `Sube a ${NN[m[1]].toLowerCase()}: ${etiq(m[0]).toLowerCase()}` : null; };
  const aprox = x => conZona(x.a) ? cambia(x) : "Zona aproximada: Senamhi no publicó el polígono";
  return [h("button", { class: "volver2", onclick: () => $("#volver").click() }, "Todo el Perú"), h("h1", {}, lg ? tit(lg[2]) : tit(id)), lg ? h("p", { class: "mut" }, `${tit(lg[1])}, ${tit(id)}`) : null,
    h("div", { class: "local n" + n }, h("b", {}, n ? `Nivel ${NN[n].toLowerCase()} hoy` : "Sin avisos meteorológicos hoy"), n ? `${lg ? "En tu distrito" : "Lo más alto en el departamento"}: ${lista([...new Set(hoy.filter(x => x.hoy === n).map(x => NOM[x.a.peligro].toLowerCase()))])}.` : (lg ? "Tu distrito no está en las zonas publicadas para hoy." : "Ninguna zona publicada para hoy toca este departamento."), lg || !n ? null : " Busca tu distrito para saber su nivel."),
    gr ? notaSismo(gr, `a ${Math.round(gr.km)} km`) : null,
    hoy.length ? [h("h2", {}, "Vigentes hoy"), ...hoy.map(x => tarjeta(x.a, x.hoy, aprox(x)))] : null,
    prox.length ? [h("h2", {}, "Próximos días"), ...prox.map(x => tarjeta(x.a, x.max, aprox(x)))] : null,
    h("h2", {}, "Qué hacer"), recs.length ? h("ul", { class: "rec" }, recs.map(([p, t, f]) => h("li", {}, h("b", {}, NOM[p]), h("br"), t, h("small", {}, ext(f.url, f.fuente === "INDECI" ? "INDECI, nota original" : `Senamhi, aviso ${numAv(f)}`))))) : h("p", { class: "mut" }, "Las fuentes consultadas no publican medidas para avisos en esta zona."),
    h("h2", {}, "Pregunta a las fuentes oficiales"),
    h("form", { class: "preg", onsubmit: ev => { ev.preventDefault(); const q = campo.value.trim(); if (!q) return; S.q = q; S.espera = "pregunta"; S.resp = null; envia({ accion: "pregunta", q, dep: id }); panel(); } }, campo, h("button", { disabled: quiere }, quiere ? "Buscando" : "Buscar")),
    S.resp ? (S.resp.items.length ? h("ul", { class: "rec" }, S.resp.items.map(r => h("li", {}, r.texto, h("small", {}, ext(r.url, r.fuente + ", original"))))) : h("p", { class: "mut" }, S.resp.motivo)) : null,
    notas.length ? [h("h2", {}, "Notas de INDECI, últimos 7 días"), h("ul", { class: "rec" }, notas.slice(0, 5).map(x => h("li", {}, ext(x.url, x.titulo), h("small", {}, fecha(x.publicado)))))] : null,
    h("h2", {}, `Sismos a menos de 200 km${lg ? "" : " del centro"}`), tablaSismos(ss, true),
    e && e.deps.includes(id) ? [h("h2", {}, "El Niño Costero"), h("div", { class: "nino" }, h("b", {}, `Magnitud ${e.nivel || "no indicada"}`), h("br"), h("span", { class: "mut" }, `${e.titulo}. `, ext(e.url, "Ver en ENFEN")))] : null];
}
function pinta() { if (D) { controles(); capas(); panel(); } }

/* ---- buscador ---- */
let idx = -1;
function sugerir() {
  const t = sinT($("#q").value.trim()), ul = $("#sug");
  idx = -1;
  if (t.length < 2) { ul.hidden = true; return; }
  const ds = M.deps.features.map(f => f.properties).filter(d => d.id.startsWith(t)).map(d => [tit(d.id), "Departamento", () => elegir(d.id)]);
  const ls = L.filter(l => sinT(l[2]).includes(t)).sort((a, b) => sinT(b[2]).startsWith(t) - sinT(a[2]).startsWith(t)).map(l => [tit(l[2]), `${tit(l[1])}, ${tit(l[0])}`, () => elegir(l[0], l)]);
  const r = [...ds, ...ls].slice(0, 8);
  ul.replaceChildren(...(r.length ? r.map(([a, b, f]) => h("li", {}, h("button", { onclick: () => { ul.hidden = true; $("#q").value = a; f(); } }, a, h("small", {}, b)))) : [h("li", { class: "mut", style: "padding:8px 12px" }, "No encontramos ese lugar")]));
  ul.hidden = false;
}
$("#q").addEventListener("input", sugerir);
$("#q").addEventListener("keydown", e => {
  const b = [...$("#sug").querySelectorAll("button")];
  if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); idx = Math.max(0, Math.min(b.length - 1, idx + (e.key === "ArrowDown" ? 1 : -1))); b.forEach((x, i) => x.classList.toggle("on", i === idx)); }
  else if (e.key === "Enter") { if (!$("#sug").hidden) b[Math.max(0, idx)]?.click(); }
  else if (e.key === "Escape") $("#sug").hidden = true;
});
document.addEventListener("click", e => { if (!e.target.closest(".busca")) $("#sug").hidden = true; });
$("#act").onclick = () => { S.vista = "fuentes"; pinta(); };
$("#rel").onclick = e => { const on = e.target.getAttribute("aria-pressed") !== "true"; e.target.setAttribute("aria-pressed", String(on)); if (listo) { map.setTerrain(on ? { source: "dem", exaggeration: 1.6 } : null); encuadre(); } };
$("#volver").onclick = () => { $("#q").value = ""; elegir(null); };

/* ---- Streamlit ---- */
const manda = (type, o) => parent.postMessage({ isStreamlitMessage: true, type, ...o }, "*");
const envia = v => manda("streamlit:setComponentValue", { value: { ...v, n: Date.now() }, dataType: "json" });
function recibe(a) {
  const f = JSON.stringify([a.datos.act, a.resp]);
  if (f === ultimaFirma) return;
  ultimaFirma = f;
  D = a.datos;
  $("#act").textContent = "Datos del " + F(D.act).toLocaleString("es-PE", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit", hour12: false });
  if (a.resp) { S.espera = null; if (a.resp.accion === "pregunta" && a.resp.dep === S.dep) S.resp = a.resp; }
  pinta();
}
let pend = null;
addEventListener("message", e => { if (e.source === parent && e.data.type === "streamlit:render") { if (M) recibe(e.data.args); else pend = e.data.args; } });
manda("streamlit:componentReady", { apiVersion: 1 });
manda("streamlit:setFrameHeight", { height: 800 });
Promise.all(["mapa.json", "lugares.json"].map(u => fetch(u).then(r => r.json()))).then(([m, l]) => { M = m; L = l; armarMapa(); if (pend) recibe(pend); });
