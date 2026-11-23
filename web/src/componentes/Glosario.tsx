import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { llenar, T } from "../textos";

// Sección 11: las palabras que no todos conocen. Cada una abre la misma ventana, en su explicación.
export type Termino = "enfen" | "senamhi" | "nino" | "magnitud" | "estados";
const ORDEN: Termino[] = ["enfen", "estados", "magnitud", "nino", "senamhi"];
const G = T.glosario as Record<string, string>;

const Contexto = createContext<(t: Termino) => void>(() => {});

export function useGlosario() {
  return useContext(Contexto);
}

/** Una palabra subrayada que abre su explicación. */
export function Palabra({ termino, children }: { termino: Termino; children: React.ReactNode }) {
  const abrir = useGlosario();
  const nombre = typeof children === "string" ? children : termino;
  return (
    <button
      type="button"
      className="palabra"
      data-termino={termino}
      aria-haspopup="dialog"
      aria-label={llenar(T.glosario.abrir, { termino: nombre })}
      onClick={() => abrir(termino)}
    >
      {children}
    </button>
  );
}

export function GlosarioProvider({ children }: { children: React.ReactNode }) {
  const [abierto, setAbierto] = useState<Termino | null>(null);
  const ventana = useRef<HTMLDialogElement>(null);
  const abrir = useCallback((t: Termino) => setAbierto(t), []);

  useEffect(() => {
    const d = ventana.current;
    if (!d) return;
    if (abierto) {
      if (!d.open) {
        if (typeof d.showModal === "function") d.showModal();
        else d.setAttribute("open", "");
      }
      const titulo = d.querySelector<HTMLElement>(`[data-termino=${abierto}] h3`);
      titulo?.scrollIntoView({ block: "nearest" });
      titulo?.focus();
    } else if (d.open) {
      if (typeof d.close === "function") d.close();
      else d.removeAttribute("open");
    }
  }, [abierto]);

  return (
    <Contexto.Provider value={abrir}>
      {children}
      <dialog
        ref={ventana}
        className="glosario"
        aria-labelledby="titulo-glosario"
        onClose={() => setAbierto(null)}
        onClick={(e) => {
          if (e.target === e.currentTarget) setAbierto(null); // tocar fuera cierra
        }}
      >
        <div className="glosario__hoja">
          <div className="glosario__cabeza">
            <h2 id="titulo-glosario">{T.glosario.titulo}</h2>
            <button type="button" className="boton boton--sutil" onClick={() => setAbierto(null)}>
              {T.comun.cerrar}
            </button>
          </div>
          {ORDEN.map((t) => (
            <section key={t} data-termino={t} className={t === abierto ? "glosario__entrada activa" : "glosario__entrada"}>
              <h3 tabIndex={-1}>{G[`${t}_titulo`]}</h3>
              <p>{G[t]}</p>
              {t === "enfen" && <p className="glosario__nota">{T.glosario.enfen_miembros}</p>}
            </section>
          ))}
        </div>
      </dialog>
    </Contexto.Provider>
  );
}
