import { useId, useState } from "react";
import { enlaceSeguro } from "../api/cliente";
import type { Estado, Macroregion } from "../api/tipos";
import { fechaCorta, llenar, T } from "../textos";

interface Props {
  estado: Estado | null;
  zona: Macroregion;
  cambiarZona: (z: Macroregion) => void;
}

const ZONAS = Object.entries(T.macroregiones) as [Macroregion, string][];

/** Lo vigente en una línea (D2): zona, estado, magnitud y comunicado; los avisos del Senamhi se abren al tocar. */
export function LineaEstado({ estado, zona, cambiarZona }: Props) {
  const [abierto, setAbierto] = useState(false);
  const [eligiendo, setEligiendo] = useState(false);
  const idAvisos = useId();
  const idZona = useId();
  const c = estado?.comunicado;
  const vigentes = estado?.avisos.filter((a) => a.vigente) ?? [];
  const textoAvisos = vigentes.length === 0 ? T.verificar.sin_avisos
    : vigentes.length === 1 ? T.verificar.aviso_uno : llenar(T.verificar.avisos, { n: vigentes.length });

  return (
    <section className="estado" aria-label={T.verificar.zona}>
      <div className="estado__fila">
        <button
          type="button"
          className="estado__zona"
          aria-expanded={eligiendo}
          aria-controls={idZona}
          onClick={() => setEligiendo((v) => !v)}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12Z" fill="none" stroke="currentColor" strokeWidth="2" />
            <circle cx="12" cy="10" r="2.6" fill="currentColor" />
          </svg>
          <span>{T.macroregiones[zona]}</span>
          <span className="solo-lectores">. {T.verificar.cambiar_zona}</span>
        </button>
        <p className="estado__texto">
          {c ? (
            <>
              <strong>{c.estado}</strong>
              {c.magnitud && <> · {llenar(T.verificar.magnitud_prevista, { magnitud: c.magnitud })}</>}
              <span className="estado__comunicado">
                {" "}
                · {llenar(T.comun.comunicado, { numero: c.numero, fecha: c.fecha_texto })}
              </span>
            </>
          ) : estado ? (
            T.verificar.sin_comunicado
          ) : (
            <span className="estado__esqueleto" aria-hidden="true" />
          )}
        </p>
        {estado && (
          <button
            type="button"
            className="estado__avisos"
            aria-expanded={abierto}
            aria-controls={idAvisos}
            onClick={() => setAbierto((v) => !v)}
            disabled={vigentes.length === 0}
          >
            {textoAvisos}
          </button>
        )}
      </div>
      {eligiendo && (
        <div id={idZona} className="estado__panel aparece" role="group" aria-label={T.verificar.elige_zona}>
          <div className="chips">
            {ZONAS.map(([id, texto]) => (
              <button
                key={id}
                type="button"
                className="chip"
                aria-pressed={id === zona}
                onClick={() => {
                  cambiarZona(id);
                  setEligiendo(false);
                }}
              >
                {texto}
              </button>
            ))}
          </div>
        </div>
      )}
      {abierto && vigentes.length > 0 && (
        <div id={idAvisos} className="estado__panel aparece">
          <h2 className="estado__titulo">{T.verificar.avisos_titulo}</h2>
          <ul className="avisos">
            {vigentes.map((a) => {
              const url = enlaceSeguro(a.url);
              return (
                <li key={a.numero}>
                  <span className={`avisos__nivel avisos__nivel--${a.nivel}`}>{a.nivel}</span>
                  <span className="avisos__texto">
                    {url ? (
                      <a href={url} target="_blank" rel="noopener noreferrer">
                        {a.titulo}
                      </a>
                    ) : (
                      a.titulo
                    )}
                    <small>{llenar(T.verificar.aviso_hasta, { fin: fechaCorta(a.fin.slice(0, 10)) })}</small>
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
