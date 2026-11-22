import type { Tema } from "../ganchos";
import { T } from "../textos";

const SIGUIENTE: Record<Tema, Tema> = { sistema: "claro", claro: "oscuro", oscuro: "sistema" };
const NOMBRE: Record<Tema, string> = {
  sistema: T.comun.tema_sistema,
  claro: T.comun.tema_claro,
  oscuro: T.comun.tema_oscuro,
};

/** Un botón que recorre sistema → claro → oscuro; el nombre accesible dice el tema actual. */
export function SelectorTema({ tema, cambiar }: { tema: Tema; cambiar: (t: Tema) => void }) {
  return (
    <button
      type="button"
      className="boton boton--sutil tema"
      onClick={() => cambiar(SIGUIENTE[tema])}
      aria-label={`${T.comun.tema}: ${NOMBRE[tema]}`}
      title={`${T.comun.tema}: ${NOMBRE[tema]}`}
    >
      <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        {tema === "oscuro" ? (
          <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z" fill="currentColor" />
        ) : tema === "claro" ? (
          <g fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <circle cx="12" cy="12" r="4.2" fill="currentColor" />
            <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" />
          </g>
        ) : (
          <g fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="8.5" />
            <path d="M12 3.5a8.5 8.5 0 0 1 0 17Z" fill="currentColor" />
          </g>
        )}
      </svg>
    </button>
  );
}
