// Cálculos del mapa sobre los datos de la API: sin React ni MapLibre, para poder probarlos.
import type { AvisoMapa, DatosMapa, Macroregion, Sismo } from "../api/tipos";

export type Lugar = [dep: string, prov: string, dist: string, lat: number, lon: number];

export const NIVEL_AVISO = { amarillo: 2, naranja: 3, rojo: 4 } as const;
export const NOMBRE_NIVEL: Record<number, "amarillo" | "naranja" | "rojo"> = { 2: "amarillo", 3: "naranja", 4: "rojo" };
export const PELIGROS = ["lluvias", "calor", "viento", "frio", "oleaje", "otro"] as const;
const DIA_MS = 86_400_000;
const DIAS_MAXIMOS = 7;
export const SISMO_FUERTE = 5.5;
export const KM_CERCA = 200;

const MENORES = new Set(["DE", "DEL", "LA", "LAS", "LOS", "Y", "EL"]);
const CON_TILDE: Record<string, string> = { Ancash: "Áncash", Apurimac: "Apurímac", Huanuco: "Huánuco", Junin: "Junín", "San Martin": "San Martín" };

export function titulo(s: string): string {
  const t = s.split(" ").filter(Boolean)
    .map((w, i) => (i && MENORES.has(w.toUpperCase()) ? w.toLowerCase() : w[0].toUpperCase() + w.slice(1).toLowerCase())).join(" ");
  return CON_TILDE[t] ?? t;
}

export function frase(s: string): string {
  const t = s.replace(/\s*\((EXTENSI|ACTUALI).*\)/i, "").toLowerCase();
  return t ? t[0].toUpperCase() + t.slice(1) : "";
}

export const sinTildes = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();

/** '2026-11-24' más i días, en AAAA-MM-DD (aritmética en UTC: no depende de la zona del navegador). */
export function diaMas(iso: string, i: number): string {
  return new Date(Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) + i * DIA_MS).toISOString().slice(0, 10);
}

export const diasDesde = (d: DatosMapa, momento: string) => (Date.parse(d.ahora) - Date.parse(momento)) / DIA_MS;

export function cuantosDias(d: DatosMapa): number {
  const hoy = d.ahora.slice(0, 10);
  let n = 1;
  for (const a of d.avisos) while (n < DIAS_MAXIMOS && a.fin.slice(0, 10) >= diaMas(hoy, n)) n++;
  return n;
}

/** El aviso toca ese día y todavía no venció. */
export function enDia(d: DatosMapa, a: AvisoMapa, i: number): boolean {
  const dia = diaMas(d.ahora, i);
  return a.inicio.slice(0, 10) <= dia && a.fin.slice(0, 10) >= dia && a.fin >= d.ahora;
}

export function avisosDelDia(d: DatosMapa, i: number, peligro: string): AvisoMapa[] {
  return d.avisos.filter((a) => enDia(d, a, i) && (peligro === "todo" || a.peligro === peligro))
    .sort((a, b) => NIVEL_AVISO[b.nivel] - NIVEL_AVISO[a.nivel]);
}

export const tieneZona = (d: DatosMapa, a: AvisoMapa) => !!d.zonas[String(a.numero)];

/** Nivel del aviso ese día en un distrito (un índice) o el más alto de un departamento (todos sus índices). */
export function nivelEn(d: DatosMapa, a: AvisoMapa, i: number, indices: number[]): number {
  const z = d.zonas[String(a.numero)]?.[diaMas(d.ahora, i)];
  if (!z || z.fin < d.ahora) return 0;
  return indices.reduce((m, k) => Math.max(m, Number(z.distritos[k] ?? 0)), 0);
}

export function km(a: number, b: number, c: number, e: number): number {
  const r = Math.PI / 180;
  const x = Math.sin(((c - a) * r) / 2) ** 2 + Math.cos(a * r) * Math.cos(c * r) * Math.sin(((e - b) * r) / 2) ** 2;
  return 12_742 * Math.asin(Math.sqrt(x));
}

export function sismosCerca(d: DatosMapa, lat: number, lon: number): (Sismo & { km: number })[] {
  return d.sismos.map((s) => ({ ...s, km: km(lat, lon, s.lat, s.lon) })).filter((s) => s.km <= KM_CERCA);
}

export function sismoFuerte<S extends Sismo>(d: DatosMapa, sismos: S[]): S | undefined {
  return sismos.filter((s) => s.magnitud >= SISMO_FUERTE && diasDesde(d, s.momento) <= 7).sort((a, b) => b.magnitud - a.magnitud)[0];
}

export function buscarLugares(texto: string, lugares: Lugar[], tope = 8): { dep: string; indice: number | null }[] {
  const t = sinTildes(texto.trim());
  if (t.length < 2) return [];
  const deps = [...new Set(lugares.map((l) => l[0]))].filter((x) => x.startsWith(t)).map((dep) => ({ dep, indice: null }));
  const dist = lugares.map((l, indice) => ({ dep: l[0], indice, n: sinTildes(l[2]) })).filter((x) => x.n.includes(t))
    .sort((a, b) => Number(b.n.startsWith(t)) - Number(a.n.startsWith(t)) || a.n.length - b.n.length);
  return [...deps, ...dist.map(({ dep, indice }) => ({ dep, indice }))].slice(0, tope);
}

export function macroregionDe(d: DatosMapa, dep: string): Macroregion | null {
  const m = d.macroregiones[dep];
  return m === "costa_norte" || m === "costa_centro" || m === "lima" ? m : null;
}

/** Consejos literales del INDECI (últimos 7 días) para los peligros y el departamento, hasta 2 por peligro. */
export function consejos(d: DatosMapa, dep: string, peligros: string[]) {
  const vistos = new Set<string>();
  return peligros.flatMap((p) => {
    const de = d.notas.filter((n) => n.peligro === p && n.departamentos.includes(dep) && diasDesde(d, n.fecha) <= 7)
      .flatMap((n) => n.recomendaciones.map((texto) => ({ peligro: p, texto, url: n.url })));
    return de.filter((c) => !vistos.has(c.texto.slice(0, 60)) && vistos.add(c.texto.slice(0, 60))).slice(0, 2);
  });
}
