// Registro de uso (docs/app/definicion.md, sección 5): solo opciones de listas cerradas y números, nunca el texto
// consultado. La sesión es un id al azar en sessionStorage, que muere con la pestaña.
import { esCelular } from "../ganchos";

export type Pantalla = "verificar" | "preguntar" | "panorama" | "metodologia";
type Seccion = "hallazgos" | "linea" | "magnitudes" | "reaccion" | "temas" | "citas" | "youtube";

export type Evento =
  | { evento: "vista"; pantalla: Pantalla; anterior?: Pantalla; segundos?: number }
  | {
      evento: "verificar";
      tipo_resultado: "datos" | "cercania" | "insuficiente" | "fuera_de_tema";
      resultado?: "coincide" | "revisar" | "no_coincide" | "cercano" | "intermedio" | "lejano";
      macroregion: string;
      palabras: number;
    }
  | { evento: "ver_por_que" }
  | { evento: "interes"; interes: string }
  | { evento: "clic_que_hacer"; tipo: "oficial" | "nota"; posicion: number }
  | { evento: "compartir" }
  | { evento: "preguntar"; herramienta: string; fuera_alcance: boolean }
  | { evento: "filtro_panorama"; filtro: "fechas" | "macroregion" }
  | { evento: "tabla_descargada"; seccion: Seccion };

const RUTA = "/api/eventos";
const POR_LOTE = 50;
const CADA_MS = 5000;

function nuevaSesion(): string {
  const letras = "abcdefghijklmnopqrstuvwxyz0123456789";
  const azar = new Uint8Array(16);
  crypto.getRandomValues(azar);
  return Array.from(azar, (b) => letras[b % letras.length]).join("");
}

function sesion(): string {
  try {
    const s = window.sessionStorage.getItem("radar.sesion");
    if (s && /^[a-z0-9]{16}$/.test(s)) return s;
    const n = nuevaSesion();
    window.sessionStorage.setItem("radar.sesion", n);
    return n;
  } catch {
    return (memoria ??= nuevaSesion());
  }
}
let memoria: string | undefined;

let cola: (Evento & { pantalla?: Pantalla })[] = [];
let temporizador: ReturnType<typeof setTimeout> | null = null;
let pantallaActual: Pantalla | null = null;
let desde = 0;
let instalado = false;

function lote(eventos: typeof cola) {
  return JSON.stringify({ sesion: sesion(), dispositivo: esCelular() ? "celular" : "escritorio", eventos });
}

export function enviar(alSalir = false) {
  if (temporizador) clearTimeout(temporizador);
  temporizador = null;
  while (cola.length) {
    const parte = cola.splice(0, POR_LOTE);
    const cuerpo = lote(parte);
    if (alSalir && typeof navigator.sendBeacon === "function") {
      navigator.sendBeacon(RUTA, new Blob([cuerpo], { type: "application/json" }));
    } else {
      fetch(RUTA, { method: "POST", body: cuerpo, headers: { "Content-Type": "application/json" }, keepalive: true,
        credentials: "omit" }).catch(() => {
        /* el registro nunca interrumpe a quien usa la app */
      });
    }
  }
}

function instalar() {
  if (instalado || typeof window === "undefined") return;
  instalado = true;
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") enviar(true);
  });
  window.addEventListener("pagehide", () => enviar(true));
}

export function registrar(e: Evento) {
  instalar();
  const conPantalla = e.evento === "vista" ? e : { ...e, pantalla: pantallaActual ?? undefined };
  cola.push(conPantalla);
  if (cola.length >= POR_LOTE) enviar();
  else if (!temporizador) temporizador = setTimeout(() => enviar(), CADA_MS);
}

/** Cambio de pantalla: registra la nueva con el tiempo que se pasó en la anterior. */
export function vista(pantalla: Pantalla) {
  if (pantalla === pantallaActual) return;
  const ahora = Date.now();
  const anterior = pantallaActual ?? undefined;
  const segundos = anterior ? Math.min(86_400, Math.round((ahora - desde) / 1000)) : undefined;
  pantallaActual = pantalla;
  desde = ahora;
  registrar({ evento: "vista", pantalla, anterior, segundos });
}

/** Solo para pruebas. */
export function _cola() {
  return cola;
}

export function _reiniciar() {
  cola = [];
  pantallaActual = null;
  if (temporizador) clearTimeout(temporizador);
  temporizador = null;
}
