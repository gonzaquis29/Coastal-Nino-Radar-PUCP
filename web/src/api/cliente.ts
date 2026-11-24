// Cliente de la API: misma dirección que la interfaz, sin cookies, con tope de tiempo y cancelación.
import type { DatosMapa, Estado, Interes, Macroregion, Metodologia, Panorama, Respuesta, Resultado, Seccion } from "./tipos";

export type TipoError = "sin_conexion" | "arrancando" | "error";

export class ErrorApi extends Error {
  constructor(public tipo: TipoError) {
    super(tipo);
  }
}

const TOPE_MS = 30_000;

async function pedir<T>(ruta: string, opciones: RequestInit = {}, senal?: AbortSignal): Promise<T> {
  const control = new AbortController();
  const tope = setTimeout(() => control.abort(), TOPE_MS);
  senal?.addEventListener("abort", () => control.abort(), { once: true });
  let r: Response;
  try {
    r = await fetch(ruta, {
      ...opciones,
      credentials: "omit",
      headers: opciones.body ? { "Content-Type": "application/json" } : undefined,
      signal: control.signal,
    });
  } catch (e) {
    if (senal?.aborted) throw e;
    throw new ErrorApi("sin_conexion");
  } finally {
    clearTimeout(tope);
  }
  if (r.status === 503) throw new ErrorApi("arrancando");
  if (!r.ok) throw new ErrorApi("error");
  return (await r.json()) as T;
}

export interface Filtros {
  desde?: string;
  hasta?: string;
  macroregion?: Macroregion;
}

function consulta(filtros: Record<string, string | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(filtros)) if (v) p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const api = {
  estado: (macroregion: Macroregion, fecha: string, senal?: AbortSignal) =>
    pedir<Estado>(`/api/estado${consulta({ macroregion, fecha })}`, {}, senal),
  verificar: (
    cuerpo: { texto: string; macroregion: Macroregion; fecha: string; interes?: Interes },
    senal?: AbortSignal,
  ) => pedir<Resultado>("/api/verificar", { method: "POST", body: JSON.stringify(cuerpo) }, senal),
  preguntar: (
    cuerpo: { consulta: string; macroregion: Macroregion; fecha: string; interes?: Interes },
    senal?: AbortSignal,
  ) => pedir<Respuesta>("/api/preguntar", { method: "POST", body: JSON.stringify(cuerpo) }, senal),
  panorama: <S extends Seccion>(seccion: S, filtros: Filtros = {}, senal?: AbortSignal) =>
    pedir<Panorama[S]>(`/api/panorama/${seccion}${consulta({ ...filtros })}`, {}, senal),
  mapa: (senal?: AbortSignal) => pedir<DatosMapa | { disponible: false }>("/api/mapa", {}, senal),
  zona: (clave: string, senal?: AbortSignal) =>
    pedir<GeoJSON.FeatureCollection>(`/api/mapa/zonas/${encodeURIComponent(clave)}`, {}, senal),
  metodologia: (senal?: AbortSignal) => pedir<Metodologia>("/api/metodologia", {}, senal),
};

/** Solo se enlaza a direcciones https (los enlaces vienen de datos, no del código). */
export function enlaceSeguro(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}
