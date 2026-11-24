// El lienzo del mapa (MapLibre): fondo satelital, zonas oficiales, sismos y límites. No conoce a React.
import maplibregl from "maplibre-gl/dist/maplibre-gl-csp";
import rutaWorker from "maplibre-gl/dist/maplibre-gl-csp-worker?url";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Sismo } from "../api/tipos";

export interface Base {
  deps: GeoJSON.FeatureCollection;
  provs: GeoJSON.FeatureCollection;
  mascara: GeoJSON.Feature;
}

export interface Vista {
  zona: GeoJSON.FeatureCollection;
  sismos: Sismo[];
  recientes: Set<string>;
  departamento: string | null;
  punto: [number, number] | null;
}

interface Opciones {
  base: Base;
  nombre: (id: string) => string;
  alTocar: (id: string) => void;
  alPasar: (pista: { x: number; y: number; dep?: string; sismo?: string } | null) => void;
}

type Propiedades = { id: string; c: [number, number]; b: [number, number, number, number] };

export const COLOR_NIVEL: Record<number, string> = { 2: "#f2c418", 3: "#f0882a", 4: "#e0392f" };
const COLOR_SISMO = "#b68cff";
const PERU: [[number, number], [number, number]] = [[-81.4, -18.4], [-68.6, 0]];
const VACIO: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };
const RELIEVE = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";
const SATELITE = "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg";
const ATRIBUCION =
  '<a href="https://s2maps.eu" target="_blank" rel="noopener">Sentinel-2 cloudless</a> de EOX (Copernicus 2016, CC BY 4.0) · Terrain Tiles · Límites: IGN/OCHA, geoBoundaries (CC BY 3.0 IGO)';
const CHICOS = new Set(["CALLAO", "TUMBES", "LAMBAYEQUE", "MOQUEGUA", "TACNA", "HUANCAVELICA", "APURIMAC", "PASCO", "HUANUCO", "ICA", "SAN MARTIN", "CAJAMARCA"]);
const colorNivel = ["match", ["get", "n"], 4, COLOR_NIVEL[4], 3, COLOR_NIVEL[3], COLOR_NIVEL[2]] as unknown as string;

maplibregl.setWorkerUrl(rutaWorker);

const quieto = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function crearLienzo(nodo: HTMLElement, o: Opciones) {
  const deps = o.base.deps.features.map((f) => f.properties as Propiedades);
  const ancho = () => nodo.clientWidth > 900;
  const margen = () => {
    const alto = nodo.clientHeight;
    return ancho()
      ? { left: 30, right: 480, top: 120, bottom: 110 }
      : { left: 16, right: 16, top: 120, bottom: Math.min(alto * 0.36 + 135, alto - 190) };
  };
  let relieve = true;
  let listo = false;
  let actual: Vista | null = null;
  let sobre: string | null = null;
  let marcas: maplibregl.Marker[] = [];

  const mapa = new maplibregl.Map({
    container: nodo,
    bounds: PERU,
    fitBoundsOptions: { padding: margen() },
    minZoom: 2,
    maxZoom: 13,
    maxPitch: 65,
    attributionControl: false,
    style: {
      version: 8,
      sources: {
        satelite: { type: "raster", tileSize: 256, maxzoom: 13, tiles: [SATELITE], attribution: ATRIBUCION },
        relieve: { type: "raster-dem", tileSize: 256, maxzoom: 11, encoding: "terrarium", tiles: [RELIEVE] },
        sombra: { type: "raster-dem", tileSize: 256, maxzoom: 11, encoding: "terrarium", tiles: [RELIEVE] },
        mascara: { type: "geojson", data: o.base.mascara },
        zona: { type: "geojson", data: VACIO },
        deps: { type: "geojson", data: o.base.deps, promoteId: "id" },
        provs: { type: "geojson", data: o.base.provs },
        sismos: { type: "geojson", data: VACIO },
      },
      layers: [
        { id: "fondo", type: "background", paint: { "background-color": "#0a1a22" } },
        { id: "satelite", type: "raster", source: "satelite", paint: { "raster-brightness-max": 0.86, "raster-saturation": -0.12 } },
        { id: "sombra", type: "hillshade", source: "sombra", paint: { "hillshade-exaggeration": 0.35, "hillshade-shadow-color": "#02090c" } },
        { id: "mascara", type: "fill", source: "mascara", paint: { "fill-color": "#061017", "fill-opacity": 0.62 } },
        { id: "zona", type: "fill", source: "zona", paint: { "fill-color": colorNivel, "fill-opacity": 0.52, "fill-antialias": false } },
        { id: "zona-borde", type: "line", source: "zona", paint: { "line-color": colorNivel, "line-width": 1, "line-opacity": 0.85 } },
        { id: "deps", type: "fill", source: "deps", paint: { "fill-color": "#fff", "fill-opacity": ["case", ["boolean", ["feature-state", "sobre"], false], 0.14, 0] } },
        { id: "provs", type: "line", source: "provs", filter: ["==", ["get", "dep"], ""], paint: { "line-color": "#fff", "line-opacity": 0.4, "line-width": 0.7 } },
        { id: "deps-borde", type: "line", source: "deps", paint: { "line-color": "#fff", "line-opacity": 0.55, "line-width": 0.9 } },
        { id: "elegido", type: "line", source: "deps", filter: ["==", ["get", "id"], ""], paint: { "line-color": "#fff", "line-width": 2.6 } },
        {
          id: "sismos", type: "circle", source: "sismos",
          paint: {
            "circle-radius": ["interpolate", ["exponential", 1.6], ["get", "magnitud"], 3.5, 3.5, 5, 7, 6, 13, 7, ancho() ? 24 : 15],
            "circle-color": COLOR_SISMO,
            "circle-opacity": ["case", ["get", "nuevo"], 0.9, 0.45],
            "circle-stroke-color": "#fff",
            "circle-stroke-width": 1.4,
          },
        },
      ],
    },
  });
  mapa.addControl(new maplibregl.AttributionControl({ compact: !ancho() }), "bottom-left");

  const nombres = deps.map((p) => {
    const el = document.createElement("div");
    el.className = "mapa__nombre";
    el.textContent = o.nombre(p.id);
    new maplibregl.Marker({ element: el }).setLngLat(p.c).addTo(mapa);
    return { id: p.id, el };
  });

  function verNombres() {
    const z = mapa.getZoom();
    for (const { id, el } of nombres) {
      const ver = actual?.departamento ? id === actual.departamento && !actual.punto : z > 5.6 || (z > 3.6 && !CHICOS.has(id));
      el.style.visibility = ver ? "" : "hidden";
    }
  }

  function pintar() {
    if (!listo || !actual) return;
    const v = actual;
    const fuente = (id: string) => mapa.getSource(id) as maplibregl.GeoJSONSource;
    fuente("zona").setData(v.zona);
    const orden = [...v.sismos].sort((a, b) => b.magnitud - a.magnitud);
    fuente("sismos").setData({
      type: "FeatureCollection",
      features: orden.map((s) => ({
        type: "Feature",
        properties: { id: s.id, magnitud: s.magnitud, nuevo: v.recientes.has(s.id) },
        geometry: { type: "Point", coordinates: [s.lon, s.lat] },
      })),
    });
    mapa.setFilter("elegido", ["==", ["get", "id"], v.departamento ?? ""]);
    mapa.setFilter("provs", ["==", ["get", "dep"], v.departamento ?? ""]);
    marcas.forEach((m) => m.remove());
    marcas = [];
    if (v.punto) marcas.push(new maplibregl.Marker({ color: "#e9f1f4" }).setLngLat(v.punto).addTo(mapa));
    verNombres();
  }

  function encuadrar(departamento: string | null) {
    const b = deps.find((p) => p.id === departamento)?.b;
    mapa.fitBounds(b ? [[b[0], b[1]], [b[2], b[3]]] : PERU, {
      padding: margen(), pitch: b && relieve ? 45 : 0, bearing: 0, duration: quieto() ? 0 : 1400,
    });
  }

  mapa.on("zoom", verNombres);
  // "style.load" y no "load": sin internet, "load" espera para siempre al satélite y no se pintarían las zonas
  mapa.on("style.load", () => {
    if (relieve) mapa.setTerrain({ source: "relieve", exaggeration: 1.6 });
    listo = true;
    pintar();
  });
  const enPunto = (p: maplibregl.Point, capa: string) => mapa.queryRenderedFeatures(p, { layers: [capa] })[0]?.properties;
  mapa.on("mousemove", (e) => {
    if (!listo) return;
    const s = enPunto(e.point, "sismos");
    const id = (enPunto(e.point, "deps")?.id as string | undefined) ?? null;
    if (id !== sobre) {
      if (sobre) mapa.setFeatureState({ source: "deps", id: sobre }, { sobre: false });
      if (id) mapa.setFeatureState({ source: "deps", id }, { sobre: true });
      sobre = id;
    }
    mapa.getCanvas().style.cursor = s || id ? "pointer" : "";
    o.alPasar(s || id ? { x: e.point.x, y: e.point.y, sismo: s?.id as string, dep: id ?? undefined } : null);
  });
  mapa.on("mouseout", () => o.alPasar(null));
  mapa.on("click", (e) => {
    const id = listo ? (enPunto(e.point, "deps")?.id as string | undefined) : undefined;
    if (id) o.alTocar(id);
  });

  let anchoPrevio = nodo.clientWidth;
  const alRedimensionar = () => {
    if (Math.abs(nodo.clientWidth - anchoPrevio) < 40) return;
    anchoPrevio = nodo.clientWidth;
    encuadrar(actual?.departamento ?? null);
  };
  window.addEventListener("resize", alRedimensionar);

  return {
    mostrar(v: Vista) {
      const cambia = !actual || v.departamento !== actual.departamento;
      const inicial = !actual && !v.departamento;
      actual = v;
      pintar();
      if (cambia && !inicial) encuadrar(v.departamento);
    },
    ponerRelieve(si: boolean) {
      relieve = si;
      if (listo) mapa.setTerrain(si ? { source: "relieve", exaggeration: 1.6 } : null);
      encuadrar(actual?.departamento ?? null);
    },
    cerrar() {
      window.removeEventListener("resize", alRedimensionar);
      mapa.remove();
    },
  };
}

export type Lienzo = ReturnType<typeof crearLienzo>;
