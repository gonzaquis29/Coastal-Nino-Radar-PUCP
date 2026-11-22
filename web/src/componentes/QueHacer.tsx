import { enlaceSeguro } from "../api/cliente";
import type { Interes, QueHacer as Q } from "../api/tipos";
import { registrar } from "../registro/registro";
import { fechaCorta, T } from "../textos";
import { Cita } from "./Cita";

interface Props {
  q: Q;
  cambiarInteres: (i: Interes) => void;
  cargando: boolean;
}

/** D5: hasta 3 elementos — las recomendaciones oficiales para el interés elegido y una nota que coincide. */
export function QueHacer({ q, cambiarInteres, cargando }: Props) {
  const nota = q.nota;
  const url = enlaceSeguro(nota?.url);
  return (
    <section className="bloque que-hacer" aria-labelledby="titulo-que-hacer" aria-busy={cargando}>
      <h2 id="titulo-que-hacer">{T.verificar.que_hacer}</h2>
      <div className="que-hacer__intereses">
        <p id="titulo-intereses" className="campo__etiqueta">
          {T.verificar.que_te_interesa}
        </p>
        <div className="chips" role="group" aria-labelledby="titulo-intereses">
          {q.intereses.map((i) => (
            <button
              key={i.id}
              type="button"
              className="chip"
              aria-pressed={i.id === q.interes}
              onClick={() => {
                if (i.id === q.interes) return;
                registrar({ evento: "interes", interes: i.id });
                cambiarInteres(i.id);
              }}
            >
              {i.texto}
            </button>
          ))}
        </div>
      </div>
      <div className={cargando ? "que-hacer__lista atenuado" : "que-hacer__lista"}>
        {q.oficiales.length === 0 && <p className="mensaje">{T.verificar.sin_que_hacer}</p>}
        {q.oficiales.map((p, i) => (
          <Cita
            key={p.parrafo}
            texto={p.texto}
            comunicado={p.comunicado}
            etiqueta={T.verificar.recomendacion}
            alAbrir={() => registrar({ evento: "clic_que_hacer", tipo: "oficial", posicion: i })}
          />
        ))}
        {nota && (
          <div className="nota">
            <span className="cita__etiqueta">{T.verificar.nota_reciente}</span>
            {url ? (
              <a
                className="nota__titular"
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => registrar({ evento: "clic_que_hacer", tipo: "nota", posicion: q.oficiales.length })}
              >
                {nota.titular}
                <span aria-hidden="true"> ↗</span>
              </a>
            ) : (
              <p className="nota__titular">{nota.titular}</p>
            )}
            <p className="nota__meta">
              {nota.medio_texto} · {fechaCorta(nota.fecha)}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
