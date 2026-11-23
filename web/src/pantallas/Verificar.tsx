import { useCallback, useEffect, useId, useRef, useState } from "react";
import { api } from "../api/cliente";
import type { Interes, Macroregion, Resultado as R } from "../api/tipos";
import { AvisoError } from "../componentes/Aviso";
import { Cita } from "../componentes/Cita";
import { AvisosZona, PanelZona } from "../componentes/PanelZona";
import { QueHacer } from "../componentes/QueHacer";
import { magnitudDelMensaje, Resultado } from "../componentes/Resultado";
import { useConsulta, useZona } from "../ganchos";
import { registrar } from "../registro/registro";
import { hoy, llenar, T } from "../textos";

const LARGO_MAXIMO = 20_000;
const LARGO_ENLACE = 1500; // lo que viaja en el fragmento # del enlace compartido
const ZONAS = Object.entries(T.macroregiones) as [Macroregion, string][];

/** El texto compartido viaja en el fragmento #t=…, que el navegador no envía al servidor (D6). */
function textoDelEnlace(): string {
  const m = window.location.hash.match(/^#t=(.*)$/s);
  if (!m) return "";
  try {
    return decodeURIComponent(m[1]).slice(0, LARGO_MAXIMO);
  } catch {
    return "";
  }
}

export default function Verificar() {
  const [zona, setZona] = useZona();
  const [texto, setTexto] = useState(textoDelEnlace);
  const [fecha, setFecha] = useState(hoy);
  const [otraFecha, setOtraFecha] = useState(false);
  const [vacio, setVacio] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const titulo = useRef<HTMLHeadingElement>(null);
  const cuadro = useRef<HTMLTextAreaElement>(null);
  const zonaRef = useRef<HTMLDivElement>(null);
  const idAyuda = useId();
  const idFecha = useId();

  const estado = useConsulta((s, z: Macroregion, f: string) => api.estado(z, f, s));
  const resultado = useConsulta(
    (s, t: string, z: Macroregion, f: string, i?: Interes) => api.verificar({ texto: t, macroregion: z, fecha: f, interes: i }, s),
  );
  const interesConsulta = useConsulta(
    (s, t: string, z: Macroregion, f: string, i: Interes) => api.verificar({ texto: t, macroregion: z, fecha: f, interes: i }, s),
  );
  const pedido = useRef<{ texto: string; zona: Macroregion; fecha: string } | null>(null);

  const { ejecutar: pedirEstado } = estado;
  useEffect(() => {
    if (zona) pedirEstado(zona, fecha || hoy());
  }, [zona, fecha, pedirEstado]);

  const verificar = useCallback(
    async (e?: React.FormEvent) => {
      e?.preventDefault();
      const t = texto.trim();
      if (!t) {
        setVacio(true);
        cuadro.current?.focus();
        return;
      }
      if (!zona) {
        zonaRef.current?.querySelector("button")?.focus();
        return;
      }
      setVacio(false);
      setCopiado(false);
      const f = fecha || hoy();
      pedido.current = { texto: t, zona, fecha: f };
      const r = await resultado.ejecutar(t, zona, f);
      if (!r) return;
      registrar({
        evento: "verificar",
        tipo_resultado: r.tipo,
        resultado: r.nivel ?? undefined,
        macroregion: zona,
        palabras: r.palabras,
      });
      requestAnimationFrame(() => titulo.current?.focus());
    },
    [texto, zona, fecha, resultado],
  );

  const cambiarInteres = useCallback(
    async (i: Interes) => {
      const p = pedido.current;
      const actual = resultado.datos;
      if (!p || !actual) return;
      const r = await interesConsulta.ejecutar(p.texto, p.zona, p.fecha, i);
      if (r) resultado.setDatos({ ...actual, que_hacer: r.que_hacer } as R);
    },
    [interesConsulta, resultado],
  );

  const compartir = useCallback(async () => {
    const r = resultado.datos;
    const p = pedido.current;
    if (!r || !p) return;
    registrar({ evento: "compartir" });
    const c = r.estado.comunicado;
    const mensaje = c
      ? llenar(T.verificar.compartir_texto, { titulo: r.titulo, numero: c.numero, fecha: c.fecha_texto })
      : llenar(T.verificar.compartir_sin_comunicado, { titulo: r.titulo });
    const url = `${window.location.origin}/#t=${encodeURIComponent(p.texto.slice(0, LARGO_ENLACE))}`;
    if (typeof navigator.share === "function") {
      try {
        await navigator.share({ title: T.comun.marca, text: mensaje, url });
        return;
      } catch (e) {
        if ((e as DOMException)?.name === "AbortError") return;
      }
    }
    try {
      await navigator.clipboard.writeText(`${mensaje} ${url}`);
      setCopiado(true);
    } catch {
      /* sin portapapeles: no hay nada más que hacer */
    }
  }, [resultado.datos]);

  const r = resultado.datos;
  return (
    <div className="hoy">
      <div className="hoy__zona">
      {zona ? (
        <PanelZona estado={estado.datos} zona={zona} cambiarZona={setZona} magnitudMensaje={magnitudDelMensaje(r)} />
      ) : (
        <div className="elegir-zona" ref={zonaRef} role="group" aria-labelledby="titulo-zona">
          <h1 id="titulo-zona" className="zona__estado">{T.verificar.elige_zona}</h1>
          <p>{T.verificar.elige_zona_ayuda}</p>
          <div className="chips">
            {ZONAS.map(([id, nombre]) => (
              <button key={id} type="button" className="chip" aria-pressed={false} onClick={() => setZona(id)}>
                {nombre}
              </button>
            ))}
          </div>
        </div>
      )}
      {estado.error && <AvisoError tipo={estado.error} reintentar={() => zona && pedirEstado(zona, fecha || hoy())} />}
      </div>

      <div className="hoy__mensaje">
      <form className="cuadro" onSubmit={verificar} noValidate aria-labelledby="titulo-mensaje">
        <h2 id="titulo-mensaje" className="cuadro__titulo">
          {T.verificar.mensaje_titulo}
        </h2>
        <p className="cuadro__bajada">{T.verificar.mensaje_ayuda}</p>
        <label htmlFor="texto" className="solo-lectores">
          {T.verificar.cuadro}
        </label>
        <textarea
          id="texto"
          ref={cuadro}
          value={texto}
          maxLength={LARGO_MAXIMO}
          rows={3}
          placeholder={T.verificar.cuadro}
          aria-describedby={idAyuda}
          aria-invalid={vacio || undefined}
          onChange={(e) => {
            setTexto(e.target.value);
            if (vacio) setVacio(false);
          }}
        />
        <p id={idAyuda} className={vacio ? "cuadro__ayuda cuadro__ayuda--error" : "cuadro__ayuda"}>
          {vacio ? T.verificar.vacio : T.verificar.cuadro_ayuda}
        </p>
        <div className="cuadro__acciones">
          <button type="submit" className="boton boton--grande" disabled={resultado.cargando}>
            {resultado.cargando ? T.verificar.verificando : T.verificar.boton}
          </button>
          {otraFecha ? (
            <div className="cuadro__fecha">
              <label htmlFor={idFecha} className="campo__etiqueta">
                {T.verificar.fecha}
              </label>
              <input
                id={idFecha}
                type="date"
                value={fecha}
                min="2024-01-01"
                max={hoy()}
                onChange={(e) => setFecha(e.target.value)}
              />
              <button
                type="button"
                className="enlace-boton"
                onClick={() => {
                  setFecha(hoy());
                  setOtraFecha(false);
                }}
              >
                {T.verificar.fecha_hoy}
              </button>
            </div>
          ) : (
            <button type="button" className="enlace-boton" onClick={() => setOtraFecha(true)}>
              {T.verificar.otra_fecha}
            </button>
          )}
        </div>
      </form>

      {resultado.error && <AvisoError tipo={resultado.error} reintentar={() => verificar()} />}

      {r && (
        <div className={resultado.cargando ? "respuesta atenuado" : "respuesta"}>
          <Resultado r={r} ref={titulo} />

          {r.oficial_cercano && (
            <section className="bloque" aria-labelledby="titulo-oficial">
              <h2 id="titulo-oficial">{T.verificar.oficial_titulo}</h2>
              <p className="bloque__ayuda">{T.verificar.oficial_ayuda}</p>
              <Cita texto={r.oficial_cercano.texto} comunicado={r.oficial_cercano.comunicado} />
            </section>
          )}

          <QueHacer q={r.que_hacer} cambiarInteres={cambiarInteres} cargando={interesConsulta.cargando} />

          <div className="compartir">
            <button type="button" className="boton boton--grande compartir__boton" onClick={compartir}>
              <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path
                  d="M12 3v12M7 8l5-5 5 5M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              {T.verificar.compartir}
            </button>
            <button
              type="button"
              className="boton boton--sutil"
              onClick={() => {
                resultado.reiniciar();
                setTexto("");
                pedido.current = null;
                if (window.location.hash) window.history.replaceState({}, "", window.location.pathname);
                cuadro.current?.focus();
              }}
            >
              {T.verificar.nueva}
            </button>
            {copiado && (
              <p className="compartir__copiado" role="status">
                {T.verificar.copiado}
              </p>
            )}
          </div>
        </div>
      )}
      </div>
      {zona && (
        <div className="hoy__avisos">
          <AvisosZona estado={estado.datos} />
        </div>
      )}
    </div>
  );
}
