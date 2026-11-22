import { useCallback, useEffect, useId, useRef, useState } from "react";
import { api, ErrorApi, type Filtros, type TipoError } from "../api/cliente";
import type { Hallazgo, Macroregion, Panorama as P, Seccion } from "../api/tipos";
import { AvisoError } from "../componentes/Aviso";
import { GraficoCitas } from "../graficos/Citas";
import { GraficoLinea } from "../graficos/Linea";
import { GraficoMagnitudes } from "../graficos/Magnitudes";
import { GraficoReaccion } from "../graficos/Reaccion";
import { GraficoTemas } from "../graficos/Temas";
import { GraficoYoutube } from "../graficos/Youtube";
import { registrar } from "../registro/registro";
import { hoy, T } from "../textos";
import "../estilos/panorama.css";

const CON_FILTRO: Seccion[] = ["linea", "magnitudes", "temas", "youtube"];
const SIN_FILTRO: Seccion[] = ["hallazgos", "reaccion", "citas"];
const ZONAS = Object.entries(T.macroregiones) as [Macroregion, string][];
const INICIO = "2026-01-01";

type Datos = Partial<P>;

export default function Panorama() {
  const [datos, setDatos] = useState<Datos>({});
  const [cargando, setCargando] = useState<Set<Seccion>>(new Set([...CON_FILTRO, ...SIN_FILTRO]));
  const [error, setError] = useState<TipoError | null>(null);
  const [filtros, setFiltros] = useState<Filtros>({});
  // un pedido por grupo: cambiar un filtro cancela solo las secciones filtradas, nunca las fijas
  const control = useRef<Record<"fijas" | "filtradas", AbortController | null>>({ fijas: null, filtradas: null });

  const pedir = useCallback(async (grupo: "fijas" | "filtradas", f: Filtros) => {
    const secciones = grupo === "fijas" ? SIN_FILTRO : CON_FILTRO;
    control.current[grupo]?.abort();
    const c = new AbortController();
    control.current[grupo] = c;
    setCargando((s) => new Set([...s, ...secciones]));
    setError(null);
    await Promise.all(
      secciones.map(async (s) => {
        try {
          const r = await api.panorama(s, CON_FILTRO.includes(s) ? f : {}, c.signal);
          if (!c.signal.aborted) setDatos((d) => ({ ...d, [s]: r }));
        } catch (e) {
          if (!c.signal.aborted) setError(e instanceof ErrorApi ? e.tipo : "error");
        } finally {
          if (!c.signal.aborted)
            setCargando((x) => {
              const n = new Set(x);
              n.delete(s);
              return n;
            });
        }
      }),
    );
  }, []);

  useEffect(() => {
    pedir("fijas", {});
    pedir("filtradas", {});
    const c = control.current;
    return () => {
      c.fijas?.abort();
      c.filtradas?.abort();
    };
  }, [pedir]);

  const aplicar = (f: Filtros, cual: "fechas" | "macroregion" | null) => {
    setFiltros(f);
    if (cual) registrar({ evento: "filtro_panorama", filtro: cual });
    pedir("filtradas", f);
  };

  const hay = (s: Seccion) => cargando.has(s);
  return (
    <div className="panorama">
      <header className="panorama__cabeza envoltura-ancha">
        <h1>{T.panorama.titulo}</h1>
        <p>{T.panorama.intro}</p>
      </header>

      <section className="hallazgos envoltura-ancha" aria-labelledby="titulo-hallazgos">
        <h2 id="titulo-hallazgos" className="solo-lectores">
          {T.panorama.hallazgos}
        </h2>
        {datos.hallazgos ? datos.hallazgos.map((h) => <Tarjeta key={h.id} h={h} />) : <p className="cargando">{T.comun.cargando}</p>}
      </section>

      <BarraFiltros filtros={filtros} aplicar={aplicar} />

      <div className="envoltura-ancha">
        {error && <AvisoError tipo={error} reintentar={() => {
              pedir("fijas", {});
              pedir("filtradas", filtros);
            }} />}
      </div>

      <div className="graficos envoltura-ancha">
        {datos.linea ? <GraficoLinea datos={datos.linea} cargando={hay("linea")} /> : <Hueco />}
        {datos.magnitudes ? <GraficoMagnitudes datos={datos.magnitudes} cargando={hay("magnitudes")} /> : <Hueco medio />}
        {datos.reaccion ? <GraficoReaccion datos={datos.reaccion} /> : <Hueco medio />}
        {datos.temas ? <GraficoTemas datos={datos.temas} cargando={hay("temas")} /> : <Hueco medio />}
        {datos.citas ? <GraficoCitas datos={datos.citas} /> : <Hueco medio />}
        {datos.youtube ? <GraficoYoutube datos={datos.youtube} cargando={hay("youtube")} /> : <Hueco />}
      </div>
    </div>
  );
}

function Hueco({ medio }: { medio?: boolean }) {
  return <div className={`grafico grafico--${medio ? "medio" : "completo"} grafico--hueco`} aria-hidden="true" />;
}

/** Una cifra grande con su frase y una mini serie decorativa (el número está en la frase). */
function Tarjeta({ h }: { h: Hallazgo }) {
  const w = 120;
  const alto = 36;
  const ys = h.serie.map((s) => s.y);
  const min = Math.min(...ys);
  const max = Math.max(...ys);
  const puntos = h.serie
    .map((s, i) => `${(i / Math.max(1, h.serie.length - 1)) * w},${alto - 3 - ((s.y - min) / (max - min || 1)) * (alto - 6)}`)
    .join(" ");
  return (
    <article className={`hallazgo hallazgo--${h.id}`}>
      <p className="hallazgo__valor">{h.valor}</p>
      <p className="hallazgo__texto">{h.texto}</p>
      <div className="hallazgo__pie">
        {h.serie.length > 1 && (
          <svg width={w} height={alto} viewBox={`0 0 ${w} ${alto}`} aria-hidden="true" className="hallazgo__serie">
            <polyline points={puntos} />
          </svg>
        )}
        {h.descriptivo && (
          <span className="insignia" data-descriptivo="" title={T.panorama.descriptivo_ayuda}>
            {T.panorama.descriptivo}
          </span>
        )}
      </div>
    </article>
  );
}

function BarraFiltros({ filtros, aplicar }: { filtros: Filtros; aplicar: (f: Filtros, cual: "fechas" | "macroregion" | null) => void }) {
  const id = useId();
  const [desde, setDesde] = useState(filtros.desde ?? "");
  const [hasta, setHasta] = useState(filtros.hasta ?? "");
  const espera = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fechas = (d: string, h: string) => {
    setDesde(d);
    setHasta(h);
    if (espera.current) clearTimeout(espera.current);
    espera.current = setTimeout(() => {
      if (d && h && d > h) return; // rango al revés: se espera a que lo corrija
      aplicar({ ...filtros, desde: d || undefined, hasta: h || undefined }, "fechas");
    }, 350);
  };
  const activos = !!(filtros.desde || filtros.hasta || filtros.macroregion);
  return (
    <form className="filtros" role="search" aria-label={T.panorama.filtros} onSubmit={(e) => e.preventDefault()}>
      <div className="filtros__fila envoltura-ancha">
        <div className="campo">
          <label htmlFor={`${id}-desde`} className="campo__etiqueta">
            {T.panorama.desde}
          </label>
          <input id={`${id}-desde`} type="date" min={INICIO} max={hasta || hoy()} value={desde} onChange={(e) => fechas(e.target.value, hasta)} />
        </div>
        <div className="campo">
          <label htmlFor={`${id}-hasta`} className="campo__etiqueta">
            {T.panorama.hasta}
          </label>
          <input id={`${id}-hasta`} type="date" min={desde || INICIO} max={hoy()} value={hasta} onChange={(e) => fechas(desde, e.target.value)} />
        </div>
        <div className="campo">
          <label htmlFor={`${id}-region`} className="campo__etiqueta">
            {T.panorama.region}
          </label>
          <select
            id={`${id}-region`}
            value={filtros.macroregion ?? ""}
            onChange={(e) => aplicar({ ...filtros, macroregion: (e.target.value || undefined) as Macroregion | undefined }, "macroregion")}
          >
            <option value="">{T.panorama.todas}</option>
            {ZONAS.map(([z, t]) => (
              <option key={z} value={z}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          className="boton boton--sutil filtros__limpiar"
          disabled={!activos}
          onClick={() => {
            setDesde("");
            setHasta("");
            aplicar({}, null);
          }}
        >
          {T.panorama.limpiar}
        </button>
      </div>
    </form>
  );
}
