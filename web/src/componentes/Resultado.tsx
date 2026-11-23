import { forwardRef, useId, useState } from "react";
import type { Afirmacion, Dato, Resultado as R, ResultadoDatos } from "../api/tipos";
import { registrar } from "../registro/registro";
import { fechaCorta, llenar, T } from "../textos";
import { Cita } from "./Cita";
import { Medidor } from "./Medidor";

const FRASES_VISIBLES = 3;

/** El resultado según D1: un veredicto solo si hay datos; si no, la cercanía en un solo tono. */
export const Resultado = forwardRef<HTMLHeadingElement, { r: R }>(function Resultado({ r }, ref) {
  if (r.tipo === "datos") return <ConDatos r={r} ref={ref} />;
  if (r.tipo === "cercania") {
    return (
      <section className="resultado resultado--cercania aparece" aria-live="polite" data-tipo="cercania">
        <h2 ref={ref} tabIndex={-1} className="resultado__titulo">
          {r.titulo}
        </h2>
        <p className="resultado__resumen">{r.resumen}</p>
        <Medidor
          valor={r.medidor.valor}
          mediaDesde={r.medidor.media_desde}
          altaDesde={r.medidor.alta_desde}
          banda={r.nivel}
        />
        <p className="resultado__aviso">
          <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <circle cx="12" cy="12" r="9.5" fill="none" stroke="currentColor" strokeWidth="2" />
            <path d="M12 10.5v6M12 7.2v.1" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
          </svg>
          <span>{r.aviso}</span>
        </p>
      </section>
    );
  }
  // Sin datos, sin medidor y sin color (U6): "insuficiente" y "fuera_de_tema" (sección 9) solo explican qué pasó
  return (
    <section className="resultado resultado--insuficiente aparece" aria-live="polite" data-tipo={r.tipo}>
      <h2 ref={ref} tabIndex={-1} className="resultado__titulo resultado__titulo--chico">
        {r.titulo}
      </h2>
      {r.resumen && <p className="resultado__resumen">{r.resumen}</p>}
    </section>
  );
});

const ConDatos = forwardRef<HTMLHeadingElement, { r: ResultadoDatos }>(function ConDatos({ r }, ref) {
  const [abierto, setAbierto] = useState(false);
  const [todas, setTodas] = useState(false);
  const id = useId();
  const visibles = todas ? r.afirmaciones : r.afirmaciones.slice(0, FRASES_VISIBLES);
  const ocultas = r.afirmaciones.length - visibles.length;
  return (
    <section className={`resultado resultado--datos resultado--${r.nivel} aparece`} aria-live="polite" data-tipo="datos">
      <div className="resultado__cabeza">
        <span className={`icono-estado icono-estado--${r.nivel}`} aria-hidden="true">
          {r.icono}
        </span>
        <div>
          <h2 ref={ref} tabIndex={-1} className="resultado__titulo">
            {r.titulo}
          </h2>
          <p className="resultado__resumen">{r.resumen}</p>
        </div>
      </div>
      {r.aviso && <p className="resultado__aviso resultado__aviso--fuerte">{r.aviso}</p>}
      <button
        type="button"
        className="boton boton--sutil resultado__abrir"
        aria-expanded={abierto}
        aria-controls={id}
        onClick={() => {
          if (!abierto) registrar({ evento: "ver_por_que" });
          setAbierto((v) => !v);
        }}
      >
        {abierto ? T.verificar.ocultar : T.verificar.ver_por_que}
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" className={abierto ? "girado" : undefined}>
          <path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
        </svg>
      </button>
      <div id={id} hidden={!abierto} className="detalle">
        {visibles.map((a, i) => (
          <Frase key={i} a={a} />
        ))}
        {ocultas > 0 && (
          <button type="button" className="enlace-boton" onClick={() => setTodas(true)}>
            {llenar(T.verificar.ver_mas, { n: ocultas })}
          </button>
        )}
        {r.linea_tiempo.length > 0 && (
          <div className="linea-tiempo">
            <h3>{T.verificar.linea_titulo}</h3>
            <ol>
              {r.linea_tiempo.map((c) => (
                <li key={c.id} className={[c.vigente && "vigente", c.respaldo && "respaldo"].filter(Boolean).join(" ")}>
                  <span className="linea-tiempo__punto" aria-hidden="true" />
                  <strong>N.° {c.numero}</strong>
                  <span>{fechaCorta(c.fecha)}</span>
                  <span className="linea-tiempo__magnitud">{c.magnitud}</span>
                  {c.vigente && <em>{T.verificar.vigente}</em>}
                  {c.respaldo && <em>{T.verificar.de_aqui}</em>}
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </section>
  );
});

function Resaltada({ frase, marcas }: { frase: string; marcas: [number, number][] }) {
  const orden = [...marcas].sort((a, b) => a[0] - b[0]);
  const partes: React.ReactNode[] = [];
  let i = 0;
  orden.forEach(([a, b], k) => {
    if (a < i) return; // marcas que se cruzan: se queda la primera
    partes.push(frase.slice(i, a), <mark key={k}>{frase.slice(a, b)}</mark>);
    i = b;
  });
  partes.push(frase.slice(i));
  return <>{partes}</>;
}

function Frase({ a }: { a: Afirmacion }) {
  const marcas = a.datos.map((d) => d.resaltado).filter((m): m is [number, number] => !!m);
  return (
    <article className="frase">
      <p className="frase__texto">
        «<Resaltada frase={a.frase} marcas={marcas} />»
      </p>
      <ul className="frase__datos">
        {a.datos.map((d, i) => (
          <DatoComparado key={i} d={d} />
        ))}
      </ul>
    </article>
  );
}

function DatoComparado({ d }: { d: Dato }) {
  const nivel = d.nivel ?? "neutro";
  return (
    <li className={`dato dato--${nivel}`}>
      <p className="dato__veredicto">
        <span className={`icono-estado icono-estado--chico icono-estado--${nivel}`} aria-hidden="true">
          {d.icono}
        </span>
        <strong>{d.veredicto}</strong>
      </p>
      <div className="dato__comparacion">
        <div>
          <h4>{T.verificar.lo_que_dice_texto}</h4>
          <p>
            {d.dato_texto}: {d.valor}
          </p>
        </div>
        <div>
          <h4>{T.verificar.lo_que_dice_enfen}</h4>
          <p>{d.oficial.dice}</p>
        </div>
      </div>
      {d.oficial.cita && <Cita texto={d.oficial.cita.cita} comunicado={d.oficial.comunicado} />}
      {d.oficial.anterior && (
        <p className="dato__anterior">
          {llenar(T.verificar.dato_anterior, { numero: d.oficial.anterior.numero, fecha: d.oficial.anterior.fecha_texto })}
        </p>
      )}
    </li>
  );
}
