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

/**
 * La cercanía en un solo tono (U6): sin verde, amarillo ni rojo, porque sin datos no hay veredicto. El número no se
 * muestra: solo el tramo.
 */
export function Medidor({ valor, mediaDesde, altaDesde, banda }: Props) {
  const p = posicion(valor, mediaDesde, altaDesde);
  const pct = Math.round(p * 100);
  return (
    <div className="medidor">
      <div
        className="medidor__barra"
        role="meter"
        aria-label={T.verificar.cercania_medidor}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-valuetext={ETIQUETA[banda]}
      >
        <div className="medidor__relleno" style={{ width: `${pct}%` }} />
        <div className="medidor__marca" style={{ left: `${pct}%` }} />
        <span className="medidor__corte" style={{ left: "33.333%" }} />
        <span className="medidor__corte" style={{ left: "66.666%" }} />
      </div>
      <div className="medidor__tramos" aria-hidden="true">
        {(["lejano", "intermedio", "cercano"] as Banda[]).map((b) => (
          <span key={b} className={b === banda ? "activo" : undefined}>
            {ETIQUETA[b]}
          </span>
        ))}
      </div>
    </div>
  );
}
