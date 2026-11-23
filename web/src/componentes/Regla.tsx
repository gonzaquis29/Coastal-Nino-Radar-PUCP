import { T } from "../textos";
import { Palabra } from "./Glosario";

/** Posición en la escala (0 débil … 3 extraordinaria) del grado más alto que nombra un texto; null si no nombra ninguno. */
export function nivelDeMagnitud(texto: string | null | undefined): number | null {
  const t = (texto ?? "").toLowerCase();
  if (/extraordinari/.test(t)) return 3;
  if (/fuerte/.test(t)) return 2;
  if (/moderad/.test(t)) return 1;
  if (/d[eé]bil/.test(t)) return 0;
  return null;
}

interface Props {
  /** La magnitud que prevé el ENFEN, tal como viene del comunicado ("extraordinaria", "débil a moderada"…). */
  enfen: string | null | undefined;
  /** La magnitud que dice el mensaje, si trae una. */
  mensaje?: string | null;
  titulo?: string;
  /** El título abre la explicación de «magnitud» en el glosario. */
  conGlosario?: boolean;
}

/**
 * La regla de magnitud, como la de un mareógrafo (sección 11): cuatro niveles de abajo hacia arriba, con la marca del
 * ENFEN y, si el mensaje trae una magnitud, la suya. Los colores son la escala ordinal ya validada (P9).
 */
export function Regla({ enfen, mensaje, titulo = T.verificar.magnitud_titulo, conGlosario = false }: Props) {
  const nEnfen = nivelDeMagnitud(enfen);
  const nMensaje = nivelDeMagnitud(mensaje);
  if (nEnfen === null && nMensaje === null) return null;
  const niveles = T.magnitudes.map((nombre, i) => ({ nombre, i })).reverse();
  const resumen = [
    nEnfen !== null ? `${T.verificar.marca_enfen}: ${T.magnitudes[nEnfen]}` : null,
    nMensaje !== null ? `${T.verificar.marca_texto}: ${T.magnitudes[nMensaje]}` : null,
  ].filter(Boolean).join(". ");
  return (
    <figure className="regla" data-regla>
      <figcaption className="eyebrow">
        {conGlosario ? <Palabra termino="magnitud">{titulo}</Palabra> : titulo}
      </figcaption>
      <div className="regla__cuerpo" role="img" aria-label={`${titulo}. ${resumen}.`}>
        <div className="regla__barra" aria-hidden="true">
          {niveles.map(({ i }) => (
            <i key={i} className={`regla__tramo regla__tramo--${i}`} />
          ))}
        </div>
        <ol className="regla__niveles" aria-hidden="true">
          {niveles.map(({ nombre, i }) => (
            <li key={i} className={i === nEnfen || i === nMensaje ? "activo" : undefined}>
              <span>{nombre}</span>
              {i === nEnfen && <span className="marca-regla marca-regla--enfen">{T.verificar.marca_enfen}</span>}
              {i === nMensaje && <span className="marca-regla marca-regla--mensaje">{T.verificar.marca_texto}</span>}
            </li>
          ))}
        </ol>
      </div>
    </figure>
  );
}

/** La escalera de estados del ENFEN (no activo, vigilancia, alerta) con el de hoy marcado. */
export function Escalera({ estado }: { estado: string | null | undefined }) {
  const t = (estado ?? "").toLowerCase();
  const hoy = /alerta/.test(t) ? 2 : /vigilancia/.test(t) ? 1 : /no activo/.test(t) ? 0 : null;
  const nombres = [T.estados.no_activo, T.estados.vigilancia, T.estados.alerta];
  return (
    <ol className="escalera" aria-label={T.verificar.estado_titulo}>
      {nombres.map((n, i) => (
        <li key={n} className={i === hoy ? "actual" : undefined} aria-current={i === hoy ? "step" : undefined}>
          {n}
        </li>
      ))}
    </ol>
  );
}
