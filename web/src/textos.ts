// Textos de la interfaz: copia generada de radar.app.textos (python -m radar.app.textos). No se escriben aquí.
import generado from "./generado/textos.json";

export const T = generado;

/** Rellena las llaves {x} de una plantilla con valores de la API. */
export function llenar(plantilla: string, valores: Record<string, string | number>): string {
  return plantilla.replace(/\{(\w+)\}/g, (_, k: string) => (k in valores ? String(valores[k]) : `{${k}}`));
}

// Coma decimal y espacio antes de %, como en los documentos del proyecto (0,168; 12,3 %)
const NUMERO = new Intl.NumberFormat("es", { useGrouping: true });
const DECIMAL = new Intl.NumberFormat("es", { maximumFractionDigits: 3 });
const TRES = new Intl.NumberFormat("es", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
const PORCENTAJE = new Intl.NumberFormat("es", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 });

export const numero = (n: number) => NUMERO.format(n);
export const decimal = (n: number) => DECIMAL.format(n);
export const porcentaje = (n: number) => PORCENTAJE.format(n).replace(/\s?%/, " %");
export const tresDecimales = (n: number) => TRES.format(n).replace("-", "−");

const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const MESES_LARGOS = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre",
  "diciembre",
];

/** '2026-03-09' -> '9 mar 2026'; '2026-03' -> 'mar 2026'. */
export function fechaCorta(iso: string): string {
  const [a, m, d] = iso.split("-");
  const mes = MESES[Number(m) - 1];
  return d ? `${Number(d)} ${mes} ${a}` : `${mes} ${a}`;
}

export function mesLargo(iso: string): string {
  const [a, m] = iso.split("-");
  return `${MESES_LARGOS[Number(m) - 1]} de ${a}`;
}

/** Fecha de hoy en la zona horaria del navegador, en AAAA-MM-DD. */
export function hoy(): string {
  const d = new Date();
  const dos = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())}`;
}
