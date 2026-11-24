import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, enlaceSeguro, type TipoError } from "../api/cliente";
import type { AvisoMapa, DatosMapa, Estado, FuenteMapa, Sismo } from "../api/tipos";
import { irA } from "../App";
import { AvisoError } from "../componentes/Aviso";
import "../estilos/mapa.css";
import { guardado } from "../ganchos";
import {
  avisosDelDia, buscarLugares, consejos, cuantosDias, diaMas, diasDesde, frase, type Lugar, macroregionDe, NIVEL_AVISO,
  nivelEn, NOMBRE_NIVEL, PELIGROS, SISMO_FUERTE, sismoFuerte, sismosCerca, tieneZona, titulo,
} from "../mapa/datos";
import { type Base, COLOR_NIVEL, crearLienzo, type Lienzo } from "../mapa/lienzo";
import { fechaCorta, llenar, T } from "../textos";

const M = T.mapa;
const SIN_ZONA: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };
const ICONOS: Record<string, string> = {
  todo: "M4 6h16M4 12h16M4 18h16",
  calor: "M12 8a4 4 0 100 8 4 4 0 000-8M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.500 1.500M17.500 17.500L19 19M5 19l1.500-1.500M17.500 6.500L19 5",
  lluvias: "M7 14a4 4 0 01.5-8 5 5 0 019.5 1.500A3.300 3.300 0 0117 14M8 17l-1 4M13 17l-1 4M18 17l-1 4",
  viento: "M3 9h11a3 3 0 10-3-3M3 14h15a3 3 0 11-3 3M3 19h7",
  frio: "M12 2v20M3.500 7l17 10M20.500 7l-17 10",
  oleaje: "M2 10c3-4 5-4 8 0s5 4 8 0l4-2M2 17c3-4 5-4 8 0s5 4 8 0l4-2",
  sismo: "M2 12h4l2-6 4 13 3-10 2 3h5",
  otro: "M12 8v.1M12 11v6",
};
const FUENTES: [FuenteMapa, string, string][] = [
  ["avisos", M.fuente_avisos, "https://www.senamhi.gob.pe/?p=aviso-meteorologico"],
  ["zonas", M.fuente_zonas, "https://idesep.senamhi.gob.pe/portalidesep/"],
  ["notas", M.fuente_notas, "https://www.gob.pe/institucion/indeci/noticias"],
  ["sismos", M.fuente_sismos, "https://earthquake.usgs.gov/earthquakes/map/"],
];

const nombrePeligro = (p: string) => (M as Record<string, string>)[p] ?? p;
const nombreNivel = (n: number) => T.verificar[`nivel_${NOMBRE_NIVEL[n]}` as "nivel_rojo"];
const hora = (iso: string) => `${fechaCorta(iso.slice(0, 10))}, ${iso.slice(11, 16)}`;
const cuentaAvisos = (n: number) => (n === 1 ? M.un_aviso : llenar(M.n_avisos, { n }));

function Icono({ p }: { p: string }) {
  return (
    <svg className="mapa__icono" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={ICONOS[p] ?? ICONOS.otro} />
    </svg>
  );
}

function Fuera({ url, children }: { url: string; children: ReactNode }) {
  const seguro = enlaceSeguro(url);
  return seguro ? (
    <a href={seguro} target="_blank" rel="noopener noreferrer">
      {children}
      <span aria-hidden="true"> ↗</span>
    </a>
  ) : (
    <>{children}</>
  );
}

function diaTexto(d: DatosMapa, i: number): string {
  if (i === 0) return M.hoy;
  if (i === 1) return M.manana;
  const t = new Intl.DateTimeFormat("es", { weekday: "long", timeZone: "UTC" }).format(new Date(`${diaMas(d.ahora, i)}T00:00:00Z`));
  return t[0].toUpperCase() + t.slice(1);
}

function Tarjeta({ a, nivel, nota, activo, alTocar }: { a: AvisoMapa; nivel: number; nota?: string | null; activo: boolean; alTocar: () => void }) {
  return (
    <li className={activo ? "mapa__aviso mapa__aviso--activo" : "mapa__aviso"}>
      <button type="button" className="mapa__cabeza" aria-pressed={activo} onClick={alTocar}>
        <Icono p={a.peligro} />
        <span className="mapa__titulo">
          <b>{frase(a.titulo)}</b>
          <small>{`${fechaCorta(a.inicio.slice(0, 10))} – ${fechaCorta(a.fin.slice(0, 10))}`}</small>
          {nota && <small>{nota}</small>}
        </span>
        <span className={`mapa__nivel mapa__nivel--${nivel}`}>{nombreNivel(nivel)}</span>
      </button>
      <div className="mapa__acciones">
        <Fuera url={a.url}>{llenar(M.ver_senamhi, { numero: a.numero })}</Fuera>
      </div>
      <details>
        <summary>{M.leer}</summary>
        <p>{a.texto}</p>
      </details>
    </li>
  );
}

function SismoDestacado({ s, donde }: { s: Sismo; donde: string }) {
  return (
    <div className="mapa__sismo">
      <strong>{s.magnitud.toFixed(1)}</strong>
      <span>
        <b>{M.sismo_reciente}</b>
        <small>{`${hora(s.momento)}, ${donde}`}</small>
        <small>
          <Fuera url={s.url}>{M.ver_usgs}</Fuera>
        </small>
      </span>
    </div>
  );
}

function TablaSismos({ sismos }: { sismos: (Sismo & { km?: number })[] }) {
  if (!sismos.length) return <p className="mapa__tenue">{M.sin_sismos}</p>;
  return (
    <table className="mapa__tabla">
      <thead>
        <tr>
          <th scope="col">{M.magnitud}</th>
          <th scope="col">{M.cuando}</th>
          <th scope="col">{M.donde}</th>
        </tr>
      </thead>
      <tbody>
        {sismos.slice(0, 12).map((s) => (
          <tr key={s.id}>
            <td><Fuera url={s.url}>{s.magnitud.toFixed(1)}</Fuera></td>
            <td>{hora(s.momento)}</td>
            <td>{s.km === undefined ? s.lugar : llenar(M.a_km, { km: Math.round(s.km) })}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

interface Cargado {
  datos: DatosMapa;
  base: Base;
  lugares: Lugar[];
}

async function archivo<X>(ruta: string): Promise<X> {
  const r = await fetch(ruta, { credentials: "omit" });
  if (!r.ok) throw new Error(ruta);
  return (await r.json()) as X;
}

export default function Mapa() {
  const [cargado, setCargado] = useState<Cargado | null>(null);
  const [sinDatos, setSinDatos] = useState(false);
  const [error, setError] = useState<TipoError | null>(null);
  const cargar = useCallback(() => {
    setError(null);
    Promise.all([api.mapa(), archivo<Base>("/mapa/base.json"), archivo<Lugar[]>("/mapa/lugares.json")])
      .then(([datos, base, lugares]) => (datos.disponible ? setCargado({ datos, base, lugares }) : setSinDatos(true)))
      .catch((e) => setError((e as { tipo?: TipoError }).tipo ?? "error"));
  }, []);
  useEffect(cargar, [cargar]);
  if (error) return <div className="envoltura"><AvisoError tipo={error} reintentar={cargar} /></div>;
  if (sinDatos) return <p className="envoltura mapa__vacio">{M.sin_datos}</p>;
  if (!cargado) return <p className="cargando envoltura">{T.comun.cargando}</p>;
  return <Tablero {...cargado} />;
}

function Tablero({ datos: d, base, lugares }: Cargado) {
  const [peligro, setPeligro] = useState("todo");
  const [dia, setDia] = useState(0);
  const [aviso, setAviso] = useState<number | null>(null);
  const [dep, setDep] = useState<string | null>(null);
  const [indice, setIndice] = useState<number | null>(null);
  const [fuentes, setFuentes] = useState(false);
  const [relieve, setRelieve] = useState(true);
  const [busca, setBusca] = useState("");
  const [abierta, setAbierta] = useState(false);
  const [marcado, setMarcado] = useState(0);
  const [zona, setZona] = useState(SIN_ZONA);
  const [pista, setPista] = useState<{ x: number; y: number; titulo: string; texto: string } | null>(null);
  const [estado, setEstado] = useState<Estado | null>(null);
  const nodo = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLElement>(null);
  const lienzo = useRef<Lienzo | null>(null);

  const indicesDe = useMemo(() => {
    const m: Record<string, number[]> = {};
    lugares.forEach((l, i) => (m[l[0]] ??= []).push(i));
    return m;
  }, [lugares]);
  const dias = cuantosDias(d);
  const lugar = indice === null ? null : lugares[indice];
  const macro = dep ? macroregionDe(d, dep) : null;

  const elegir = useCallback((id: string | null, i: number | null = null) => {
    setDep(id);
    setIndice(i);
    setAviso(null);
    setFuentes(false);
    setPista(null);
    panel.current?.scrollTo(0, 0);
  }, []);

  // lo que el lienzo dice al pasar el cursor depende del filtro: se lee de una referencia, sin rehacer el mapa
  const textoDe = useRef<(id: string) => string>(() => "");
  textoDe.current = (id) => {
    if (peligro === "sismo") return "";
    const niveles = avisosDelDia(d, dia, peligro).filter((a) => aviso === null || a.numero === aviso)
      .map((a) => [a, nivelEn(d, a, dia, indicesDe[id] ?? [])] as const).filter(([, n]) => n);
    return niveles.map(([a, n]) => `${nombrePeligro(a.peligro)}: ${nombreNivel(n).toLowerCase()}`).join(", ") || M.sin_avisos_dia;
  };

  useEffect(() => {
    if (!nodo.current) return;
    const l = crearLienzo(nodo.current, {
      base,
      nombre: titulo,
      alTocar: (id) => elegir(id),
      alPasar: (p) => {
        const s = p?.sismo ? d.sismos.find((x) => x.id === p.sismo) : undefined;
        if (p && s) setPista({ x: p.x, y: p.y, titulo: `${M.magnitud} ${s.magnitud.toFixed(1)}`, texto: `${hora(s.momento)}, ${s.lugar}` });
        else if (p?.dep) setPista({ x: p.x, y: p.y, titulo: titulo(p.dep), texto: textoDe.current(p.dep) });
        else setPista(null);
      },
    });
    lienzo.current = l;
    return () => {
      l.cerrar();
      lienzo.current = null;
    };
  }, [base, d, elegir]);

  useEffect(() => {
    if (peligro === "sismo") {
      setZona(SIN_ZONA);
      return;
    }
    const control = new AbortController();
    const clave = `${aviso === null ? peligro : `aviso-${aviso}`}_${diaMas(d.ahora, dia)}`;
    api.zona(clave, control.signal).then(setZona).catch(() => !control.signal.aborted && setZona(SIN_ZONA));
    return () => control.abort();
  }, [peligro, dia, aviso, d]);

  useEffect(() => {
    const sismos = peligro === "sismo" ? d.sismos
      : peligro === "todo" && dia === 0 && aviso === null ? d.sismos.filter((s) => s.magnitud >= SISMO_FUERTE && diasDesde(d, s.momento) <= 7) : [];
    lienzo.current?.mostrar({
      zona, sismos, departamento: dep, punto: lugar ? [lugar[4], lugar[3]] : null,
      recientes: new Set(sismos.filter((s) => diasDesde(d, s.momento) < 2).map((s) => s.id)),
    });
  }, [zona, peligro, dia, aviso, dep, lugar, d]);

  useEffect(() => {
    setEstado(null);
    if (!macro) return;
    const control = new AbortController();
    api.estado(macro, d.ahora.slice(0, 10), control.signal).then(setEstado).catch(() => undefined);
    return () => control.abort();
  }, [macro, d]);

  const opciones = buscarLugares(busca, lugares);
  const abrirOpcion = (o: { dep: string; indice: number | null }) => {
    setBusca(titulo(o.indice === null ? o.dep : lugares[o.indice][2]));
    setAbierta(false);
    elegir(o.dep, o.indice);
  };
  const tocarAviso = (a: AvisoMapa) => {
    if (aviso === a.numero) return setAviso(null);
    const deEse = d.zonas[String(a.numero)] ?? {};
    if (!deEse[diaMas(d.ahora, dia)]) {
      const i = Array.from({ length: dias }, (_, k) => k).find((k) => deEse[diaMas(d.ahora, k)]);
      if (i !== undefined) setDia(i);
    }
    if (peligro === "sismo") setPeligro("todo");
    setAviso(a.numero);
  };
  const irConZona = (ruta: string) => {
    if (macro) guardado.escribir("radar.zona", macro);
    irA(ruta);
  };

  const filtros = ["todo", ...PELIGROS.filter((p) => d.avisos.some((a) => a.peligro === p)), "sismo"];
  const tarjeta = (a: AvisoMapa, nivel: number, nota?: string | null) => (
    <Tarjeta key={a.numero} a={a} nivel={nivel} nota={nota} activo={aviso === a.numero} alTocar={() => tocarAviso(a)} />
  );

  function panelPais() {
    const lista = avisosDelDia(d, dia, peligro);
    const rojos = lista.filter((a) => a.nivel === "rojo").length;
    const fuerte = dia === 0 && peligro === "todo" ? sismoFuerte(d, d.sismos) : undefined;
    const cuenta = cuentaAvisos(lista.length);
    return (
      <>
        <p className="eyebrow">{peligro === "todo" ? diaTexto(d, dia) : `${diaTexto(d, dia)} · ${nombrePeligro(peligro)}`}</p>
        <h1>{!lista.length ? M.sin_avisos_dia : rojos ? llenar(M.rojos, { avisos: cuenta, n: rojos }) : cuenta}</h1>
        <p className="mapa__tenue">{M.ayuda}</p>
        {fuerte && <SismoDestacado s={fuerte} donde={fuerte.lugar} />}
        {lista.length > 0 && <h2>{M.toca_aviso}</h2>}
        <ul className="mapa__lista">{lista.map((a) => tarjeta(a, NIVEL_AVISO[a.nivel]))}</ul>
      </>
    );
  }

  function panelSismos() {
    const mayor = [...d.sismos].sort((a, b) => b.magnitud - a.magnitud)[0];
    return (
      <>
        <h1>{llenar(M.sismos_titulo, { n: d.sismos.length })}</h1>
        <p className="mapa__tenue">{M.sismos_ayuda}</p>
        {mayor && <SismoDestacado s={mayor} donde={mayor.lugar} />}
        <TablaSismos sismos={d.sismos} />
      </>
    );
  }

  function panelLugar(id: string) {
    const indices = indice === null ? (indicesDe[id] ?? []) : [indice];
    const locales = d.avisos.filter((a) => a.fin >= d.ahora).map((a) => {
      const niveles = Array.from({ length: dias }, (_, i) => nivelEn(d, a, i, indices));
      const max = Math.max(...niveles);
      return { a, hoy: niveles[0], max, cuando: niveles.indexOf(max) };
    });
    const hoy = locales.filter((x) => x.hoy).sort((x, y) => y.hoy - x.hoy);
    const proximos = locales.filter((x) => !x.hoy && x.max).sort((x, y) => x.a.inicio.localeCompare(y.a.inicio));
    const sinPoligono = locales.filter((x) => !tieneZona(d, x.a));
    const n = hoy[0]?.hoy ?? 0;
    const peligros = [...new Set(hoy.filter((x) => x.hoy === n).map((x) => nombrePeligro(x.a.peligro).toLowerCase()))].join(", ");
    const todos = [...new Set([...hoy, ...proximos].map((x) => x.a.peligro))];
    const utiles = consejos(d, id, todos);
    const prom = (k: 3 | 4) => indices.reduce((s, i) => s + lugares[i][k], 0) / Math.max(1, indices.length);
    const cerca = sismosCerca(d, prom(3), prom(4));
    const fuerte = sismoFuerte(d, cerca);
    const notas = d.notas.filter((x) => x.departamentos.includes(id) && diasDesde(d, x.fecha) <= 7).slice(0, 5);
    const c = estado?.comunicado;
    return (
      <>
        <button type="button" className="mapa__volver" onClick={() => { setBusca(""); elegir(null); }}>{M.todo_peru}</button>
        <h1>{titulo(lugar ? lugar[2] : id)}</h1>
        {lugar && <p className="mapa__tenue">{`${titulo(lugar[1])}, ${titulo(id)}`}</p>}
        <div className={`mapa__local mapa__local--${n}`}>
          <b>{n ? llenar(M.nivel_hoy, { nivel: nombreNivel(n).toLowerCase() }) : M.sin_nivel}</b>
          <span>{n ? llenar(lugar ? M.en_distrito : M.en_departamento, { peligros }) : lugar ? M.fuera_distrito : M.fuera_departamento}</span>
        </div>
        {fuerte && <SismoDestacado s={fuerte} donde={llenar(M.a_km, { km: Math.round(fuerte.km) })} />}
        <section className="mapa__nino">
          <h2>{M.nino}</h2>
          {!macro ? <p className="mapa__tenue">{M.nino_fuera}</p> : c ? (
            <>
              <p>{llenar(M.nino_texto, { estado: c.estado, magnitud: c.magnitud || "–" })}</p>
              <p><Fuera url={c.url}>{llenar(M.comunicado, { numero: c.numero })}</Fuera></p>
            </>
          ) : null}
          <div className="mapa__botones">
            <button type="button" className="boton" onClick={() => irConZona("/")}>{M.comparar}</button>
            <button type="button" className="boton boton--sutil" onClick={() => irConZona("/preguntar")}>{M.preguntar}</button>
          </div>
        </section>
        {hoy.length > 0 && (
          <>
            <h2>{M.vigentes}</h2>
            <ul className="mapa__lista">
              {hoy.map((x) => tarjeta(x.a, x.hoy, x.max > x.hoy ? llenar(M.sube, { nivel: nombreNivel(x.max).toLowerCase(), dia: diaTexto(d, x.cuando).toLowerCase() }) : null))}
            </ul>
          </>
        )}
        {proximos.length > 0 && (
          <>
            <h2>{M.proximos}</h2>
            <ul className="mapa__lista">{proximos.map((x) => tarjeta(x.a, x.max))}</ul>
          </>
        )}
        {sinPoligono.length > 0 && (
          <ul className="mapa__lista">{sinPoligono.map((x) => tarjeta(x.a, NIVEL_AVISO[x.a.nivel], M.sin_poligono))}</ul>
        )}
        <h2>{M.que_hacer}</h2>
        {utiles.length === 0 ? <p className="mapa__tenue">{M.sin_que_hacer}</p> : (
          <ul className="mapa__consejos">
            {utiles.map((x) => (
              <li key={x.texto}>
                <b>{nombrePeligro(x.peligro)}</b>
                {x.texto}
                <small><Fuera url={x.url}>{M.indeci}</Fuera></small>
              </li>
            ))}
          </ul>
        )}
        {notas.length > 0 && (
          <>
            <h2>{M.notas}</h2>
            <ul className="mapa__consejos">
              {notas.map((x) => (
                <li key={x.url}>
                  <Fuera url={x.url}>{x.titulo}</Fuera>
                  <small>{fechaCorta(x.fecha)}</small>
                </li>
              ))}
            </ul>
          </>
        )}
        <h2>{M.sismos_cerca}</h2>
        <TablaSismos sismos={cerca} />
      </>
    );
  }

  function panelFuentes() {
    return (
      <>
        <button type="button" className="mapa__volver" onClick={() => setFuentes(false)}>{M.volver}</button>
        <h1>{M.fuentes}</h1>
        <p className="mapa__tenue">{M.fuentes_intro}</p>
        {FUENTES.map(([id, nombre, url]) => {
          const f = d.fuentes[id];
          return (
            <section key={id}>
              <h2><Fuera url={url}>{nombre}</Fuera></h2>
              {f?.ok && <p className="mapa__tenue">{llenar(M.ultima, { fecha: hora(f.ok), n: f.n })}</p>}
              {f?.error && <p>{llenar(M.fallo, { fecha: hora(f.error) })}</p>}
            </section>
          );
        })}
        <ul className="mapa__consejos">
          {[M.fuentes_nivel, M.fuentes_peligro, M.fuentes_fondo].map((t) => <li key={t}>{t}</li>)}
        </ul>
      </>
    );
  }

  return (
    <div className="mapa">
      <div ref={nodo} className="mapa__lienzo" role="region" aria-label={M.titulo} />
      <div className="mapa__arriba">
        <div className="mapa__buscador">
          <input
            type="search" value={busca} placeholder={M.buscar} aria-label={M.buscar} autoComplete="off"
            role="combobox" aria-expanded={abierta && busca.trim().length > 1} aria-controls="mapa-opciones" aria-autocomplete="list"
            aria-activedescendant={abierta && opciones[marcado] ? `mapa-opcion-${marcado}` : undefined}
            onChange={(e) => { setBusca(e.target.value); setAbierta(true); setMarcado(0); }}
            onBlur={() => setAbierta(false)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setAbierta(false);
              else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                e.preventDefault();
                setMarcado((m) => Math.max(0, Math.min(opciones.length - 1, m + (e.key === "ArrowDown" ? 1 : -1))));
              } else if (e.key === "Enter" && abierta && opciones[marcado]) abrirOpcion(opciones[marcado]);
            }}
          />
          {abierta && busca.trim().length > 1 && (
            <ul id="mapa-opciones" role="listbox" aria-label={M.buscar}>
              {opciones.length === 0 && <li className="mapa__sin-lugar">{M.sin_lugar}</li>}
              {opciones.map((o, i) => (
                <li
                  key={`${o.dep}-${o.indice}`} id={`mapa-opcion-${i}`} role="option" aria-selected={i === marcado}
                  onMouseDown={(e) => { e.preventDefault(); abrirOpcion(o); }}
                >
                  {titulo(o.indice === null ? o.dep : lugares[o.indice][2])}
                  <small>{o.indice === null ? M.departamento : `${titulo(lugares[o.indice][1])}, ${titulo(o.dep)}`}</small>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="mapa__filtros" role="group" aria-label={M.peligros}>
          {filtros.map((p) => (
            <button
              key={p} type="button" aria-pressed={peligro === p && aviso === null}
              onClick={() => { setPeligro(p); setAviso(null); setFuentes(false); if (p === "sismo") elegir(null); }}
            >
              <Icono p={p} />
              {nombrePeligro(p)}
              <i>{p === "sismo" ? d.sismos.length : avisosDelDia(d, dia, p).length}</i>
            </button>
          ))}
        </div>
      </div>
      <div className="mapa__abajo">
        <div className="mapa__leyenda">
          {peligro === "sismo" ? <span><s className="mapa__punto" />{M.leyenda_sismos}</span> : (
            <>
              {[2, 3, 4].map((n) => <span key={n}><s style={{ background: COLOR_NIVEL[n] }} />{nombreNivel(n)}</span>)}
              {peligro === "todo" && dia === 0 && aviso === null && <span><s className="mapa__punto" />{M.leyenda_sismo}</span>}
            </>
          )}
        </div>
        {peligro !== "sismo" && (
          <div className="mapa__dias" role="group" aria-label={M.dias}>
            {Array.from({ length: dias }, (_, i) => (
              <button key={i} type="button" aria-pressed={dia === i} onClick={() => { setDia(i); setAviso(null); }}>
                <b>{diaTexto(d, i)}</b>
                <span>{cuentaAvisos(avisosDelDia(d, i, peligro).length)}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      <button
        type="button" className="mapa__relieve" aria-pressed={relieve}
        onClick={() => { setRelieve(!relieve); lienzo.current?.ponerRelieve(!relieve); }}
      >
        {M.relieve}
      </button>
      <aside ref={panel} className="mapa__panel" tabIndex={0} aria-label={M.titulo}>
        {fuentes ? panelFuentes() : dep ? panelLugar(dep) : peligro === "sismo" ? panelSismos() : panelPais()}
        {!fuentes && (
          <footer className="mapa__pie">
            <p>{M.pie}</p>
            <p>{llenar(M.actualizado, { fecha: hora(d.actualizado) })}</p>
            <button type="button" className="mapa__volver" onClick={() => { setFuentes(true); panel.current?.scrollTo(0, 0); }}>{M.fuentes}</button>
          </footer>
        )}
      </aside>
      {pista && (
        <div className="mapa__pista" style={{ left: pista.x + 14, top: pista.y + 14 }}>
          <b>{pista.titulo}</b>
          {pista.texto}
        </div>
      )}
    </div>
  );
}
