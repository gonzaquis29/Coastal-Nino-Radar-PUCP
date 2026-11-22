// Escalas, colores y formatos compartidos por los gráficos.
import { fechaCorta, porcentaje } from "../textos";

export const MAGNITUDES = ["débil", "moderada", "fuerte", "extraordinaria"] as const;
export const COLOR_MAGNITUD: Record<string, string> = {
  débil: "var(--mag-debil)",
  moderada: "var(--mag-moderada)",
  fuerte: "var(--mag-fuerte)",
  extraordinaria: "var(--mag-extraordinaria)",
};

export const COLOR_GRUPO_A: Record<string, string> = {
  coinciden: "var(--coinciden)",
  difieren: "var(--difieren)",
  sin_datos: "var(--sin-datos)",
};

export const COLOR_TEMA = ["var(--tema-1)", "var(--tema-2)", "var(--tema-3)", "var(--tema-4)", "var(--tema-otros)"];
export const COLOR_SERIE = ["var(--serie-1)", "var(--serie-2)", "var(--serie-3)"];

export const dia = (iso: string) => new Date(`${iso}T12:00:00`);
export const sumarDias = (d: Date, n: number) => new Date(d.getTime() + n * 86_400_000);

/** Etiquetas de los ejes en las tintas del texto, nunca en el color de una serie. */
export const etiquetaEje = () => ({ className: "eje__texto", fontSize: 12 });
export const etiquetaEjeIzq = () => ({ className: "eje__texto", fontSize: 12, textAnchor: "end" as const, dx: -4, dy: 4 });

export function cambio(veces: number): string {
  const p = veces - 1;
  return `${p >= 0 ? "+" : "−"}${porcentaje(Math.abs(p))}`;
}

export function mesEje(d: Date): string {
  return fechaCorta(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`).split(" ")[0];
}

export const MARGEN = { arriba: 10, derecha: 12, abajo: 30, izquierda: 44 };
