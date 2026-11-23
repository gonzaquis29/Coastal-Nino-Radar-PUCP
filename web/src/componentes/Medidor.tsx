import type { Banda } from "../api/tipos";
import { T } from "../textos";

interface Props {
  valor: number;
  mediaDesde: number;
  altaDesde: number;
  banda: Banda;
}

/** Posición del valor en tres tramos iguales (baja, media, alta), para que el corte se lea y no el número. */
export function posicion(valor: number, mediaDesde: number, altaDesde: number): number {
  const paso = Math.max(altaDesde - mediaDesde, 1e-6);
  const piso = mediaDesde - paso * 2;
  const techo = altaDesde + paso * 2;
  const tramo = (v: number, a: number, b: number, desde: number) => desde + (Math.min(Math.max(v, a), b) - a) / (b - a) / 3;
  if (valor < mediaDesde) return tramo(valor, piso, mediaDesde, 0);
  if (valor < altaDesde) return tramo(valor, mediaDesde, altaDesde, 1 / 3);
  return tramo(valor, altaDesde, techo, 2 / 3);
}

const ETIQUETA: Record<Banda, string> = { lejano: T.verificar.baja, intermedio: T.verificar.media, cercano: T.verificar.alta };
const ORDEN: Banda[] = ["lejano", "intermedio", "cercano"];

/**
 * Qué tanto habla del mismo tema (sección 11): tres ondas en un solo tono, encendidas hasta su tramo. Sin verde,
 * amarillo ni rojo (U6), sin número y chica, para que no se lea como «coincide».
 */
export function Medidor({ valor, mediaDesde, altaDesde, banda }: Props) {
  const pct = Math.round(posicion(valor, mediaDesde, altaDesde) * 100);
  const encendidas = ORDEN.indexOf(banda) + 1;
  return (
    <span
      className="ondas"
      role="meter"
      aria-label={T.verificar.cercania_medidor}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      aria-valuetext={ETIQUETA[banda]}
    >
      {ORDEN.map((b, i) => (
        <i key={b} className={i < encendidas ? "on" : undefined} />
      ))}
    </span>
  );
}
