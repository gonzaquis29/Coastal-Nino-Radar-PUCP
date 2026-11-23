import { useCallback, useEffect, useId, useRef, useState } from "react";
import { api } from "../api/cliente";
import type { Interes, Macroregion, Respuesta } from "../api/tipos";
import { AvisoError } from "../componentes/Aviso";
import { Cita } from "../componentes/Cita";
import { useConsulta, useZona } from "../ganchos";
import { registrar } from "../registro/registro";
import { hoy, T } from "../textos";

const EJEMPLOS = [T.preguntar.ejemplo_1, T.preguntar.ejemplo_2, T.preguntar.ejemplo_3];
const ZONAS = Object.entries(T.macroregiones) as [Macroregion, string][];
const INTERESES = Object.entries(T.intereses) as [Interes, string][];
const LARGO_PREGUNTA = 500;

interface Intercambio {
  pregunta: string;
  respuesta: Respuesta;
}

/** D7: el agente en su propia pestaña, con sus citas literales y lo que entendió a la vista y editable. */
export default function Preguntar() {
  const [zonaGuardada] = useZona();
  const [consulta, setConsulta] = useState("");
  const [historia, setHistoria] = useState<Intercambio[]>([]);
  const pedido = useConsulta(
    (s, c: string, z: Macroregion, f: string, i?: Interes) =>
      api.preguntar({ consulta: c, macroregion: z, fecha: f, interes: i }, s),
  );
  const ultimo = useRef<HTMLDivElement>(null);
  const idEjemplos = useId();

  const preguntar = useCallback(
    async (c: string, ajustes?: { macroregion: Macroregion; fecha: string; interes: Interes }) => {
      const texto = c.trim().slice(0, LARGO_PREGUNTA);
      if (!texto) return;
      const r = await pedido.ejecutar(
        texto,
        ajustes?.macroregion ?? zonaGuardada ?? "lima",
        ajustes?.fecha ?? hoy(),
        ajustes?.interes,
      );
      if (!r) return;
      registrar({ evento: "preguntar", herramienta: r.herramienta, fuera_alcance: r.herramienta === "fuera" });
      setHistoria((h) => [...h, { pregunta: texto, respuesta: r }]);
      setConsulta("");
    },
    [pedido, zonaGuardada],
  );

  useEffect(() => {
    if (historia.length) {
      ultimo.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      ultimo.current?.focus({ preventScroll: true });
    }
  }, [historia.length]);

  return (
    <div className="envoltura preguntar">
      <h1 className="titulo-pantalla">{T.preguntar.titulo}</h1>

      {historia.length === 0 && (
        <div className="ejemplos">
          <p id={idEjemplos} className="campo__etiqueta">
            {T.preguntar.ejemplos}
          </p>
          <div className="chips chips--columna" role="group" aria-labelledby={idEjemplos}>
            {EJEMPLOS.map((e) => (
              <button key={e} type="button" className="chip" disabled={pedido.cargando} onClick={() => preguntar(e)}>
                {e}
              </button>
            ))}
          </div>
        </div>
      )}

      <ol className="conversacion">
        {historia.map((h, i) => (
          <li key={i}>
            <div className="burbuja burbuja--usuario">
              <span className="solo-lectores">{T.preguntar.tu_pregunta}: </span>
              {h.pregunta}
            </div>
            <div
              className="burbuja burbuja--respuesta aparece"
              ref={i === historia.length - 1 ? ultimo : undefined}
              tabIndex={-1}
              aria-live="polite"
            >
              <span className="solo-lectores">{T.preguntar.respuesta}: </span>
              <p className="burbuja__texto">{h.respuesta.texto}</p>
              {h.respuesta.citas.length > 0 && (
                <div className="burbuja__citas">
                  <h2 className="burbuja__subtitulo">{T.preguntar.citas}</h2>
                  {h.respuesta.citas.map((c) => (
                    <Cita key={c.parrafo} texto={c.cita} comunicado={c.comunicado} fuente={c.fuente} url={c.url} />
                  ))}
                </div>
              )}
              <Entendido
                r={h.respuesta}
                cargando={pedido.cargando}
                repetir={(ajustes) => preguntar(h.pregunta, ajustes)}
              />
            </div>
          </li>
        ))}
      </ol>

      {pedido.error && <AvisoError tipo={pedido.error} reintentar={() => preguntar(consulta)} />}

      <form
        className="cuadro cuadro--pregunta tarjeta"
        onSubmit={(e) => {
          e.preventDefault();
          preguntar(consulta);
        }}
      >
        <label htmlFor="pregunta" className="solo-lectores">
          {T.preguntar.cuadro}
        </label>
        <input
          id="pregunta"
          type="search"
          value={consulta}
          maxLength={LARGO_PREGUNTA}
          placeholder={T.preguntar.cuadro}
          enterKeyHint="send"
          onChange={(e) => setConsulta(e.target.value)}
        />
        <button type="submit" className="boton" disabled={pedido.cargando || !consulta.trim()}>
          {pedido.cargando ? T.preguntar.pensando : T.preguntar.boton}
        </button>
      </form>
    </div>
  );
}

function Entendido({
  r,
  cargando,
  repetir,
}: {
  r: Respuesta;
  cargando: boolean;
  repetir: (a: { macroregion: Macroregion; fecha: string; interes: Interes }) => void;
}) {
  const [zona, setZona] = useState<Macroregion>(r.entendido.macroregion);
  const [fecha, setFecha] = useState(r.entendido.fecha);
  const [interes, setInteres] = useState<Interes>(r.entendido.interes);
  const id = useId();
  const cambio = zona !== r.entendido.macroregion || fecha !== r.entendido.fecha || interes !== r.entendido.interes;
  return (
    <details className="entendido">
      <summary>{T.preguntar.entendido}: {r.entendido.macroregion_texto} · {r.entendido.fecha_texto}</summary>
      <p className="bloque__ayuda">{T.preguntar.entendido_ayuda}</p>
      <div className="entendido__campos">
        <div className="campo">
          <label htmlFor={`${id}-zona`} className="campo__etiqueta">
            {T.preguntar.zona}
          </label>
          <select id={`${id}-zona`} value={zona} onChange={(e) => setZona(e.target.value as Macroregion)}>
            {ZONAS.map(([z, t]) => (
              <option key={z} value={z}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label htmlFor={`${id}-fecha`} className="campo__etiqueta">
            {T.preguntar.fecha}
          </label>
          <input id={`${id}-fecha`} type="date" value={fecha} max={hoy()} onChange={(e) => setFecha(e.target.value)} />
        </div>
        <div className="campo">
          <label htmlFor={`${id}-tema`} className="campo__etiqueta">
            {T.preguntar.tema}
          </label>
          <select id={`${id}-tema`} value={interes} onChange={(e) => setInteres(e.target.value as Interes)}>
            {INTERESES.map(([i, t]) => (
              <option key={i} value={i}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>
      <button
        type="button"
        className="boton boton--sutil"
        disabled={!cambio || cargando || !fecha}
        onClick={() => repetir({ macroregion: zona, fecha, interes })}
      >
        {T.preguntar.repetir}
      </button>
    </details>
  );
}
