// Piezas comunes de los gráficos del Panorama: cada uno tiene información emergente, vista de tabla con descarga en
// CSV y una línea de "Cómo leer" (P10). "Descriptivo" solo donde el componente no pasó su criterio (D9).
import { useCallback, useId, useRef, useState } from "react";
import { useAncho } from "../ganchos";
import { registrar } from "../registro/registro";
import { T } from "../textos";

export type SeccionGrafico = "linea" | "magnitudes" | "reaccion" | "temas" | "citas" | "youtube";

export interface Columna {
  id: string;
  texto: string;
  numero?: boolean;
  formato?: (v: unknown) => string;
}

export interface Tabla {
  columnas: Columna[];
  filas: Record<string, unknown>[];
}

/** CSV con BOM para que las hojas de cálculo lean bien las tildes. Las celdas van siempre entre comillas. */
export function aCsv(t: Tabla): string {
  const celda = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const lineas = [t.columnas.map((c) => celda(c.texto)).join(",")];
  for (const f of t.filas) lineas.push(t.columnas.map((c) => celda(f[c.id])).join(","));
  return `﻿${lineas.join("\r\n")}\r\n`;
}

function descargar(nombre: string, contenido: string) {
  const url = URL.createObjectURL(new Blob([contenido], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export interface Punta {
  x: number;
  y: number;
  contenido: React.ReactNode;
}

/** La información emergente: aparece junto al cursor y no se sale del gráfico. */
export function useEmergente() {
  const [punta, setPunta] = useState<Punta | null>(null);
  const mostrar = useCallback((x: number, y: number, contenido: React.ReactNode) => setPunta({ x, y, contenido }), []);
  const ocultar = useCallback(() => setPunta(null), []);
  return { punta, mostrar, ocultar };
}

export function Emergente({ punta, ancho }: { punta: Punta | null; ancho: number }) {
  if (!punta) return null;
  const izquierda = punta.x > ancho * 0.6;
  return (
    <div
      className="emergente"
      role="status"
      style={{
        left: izquierda ? undefined : punta.x + 14,
        right: izquierda ? ancho - punta.x + 14 : undefined,
        top: Math.max(0, punta.y - 12),
      }}
    >
      {punta.contenido}
    </div>
  );
}

export function Leyenda({ items }: { items: { texto: string; color: string; forma?: "linea" | "punto" }[] }) {
  return (
    <ul className="leyenda">
      {items.map((i) => (
        <li key={i.texto}>
          <span className={`leyenda__marca leyenda__marca--${i.forma ?? "bloque"}`} style={{ background: i.color }} />
          {i.texto}
        </li>
      ))}
    </ul>
  );
}

/** Posición del puntero dentro del lienzo (para el emergente). */
export function puntero(e: React.PointerEvent | React.MouseEvent, lienzo: HTMLElement | null) {
  const r = lienzo?.getBoundingClientRect();
  return r ? { x: e.clientX - r.left, y: e.clientY - r.top } : { x: 0, y: 0 };
}

interface Props {
  seccion: SeccionGrafico;
  letra: string;
  titulo: string;
  comoLeer: string;
  tabla: Tabla;
  descriptivo?: boolean;
  nota?: string | null;
  vacio?: string | null;
  cargando?: boolean;
  ancho?: "completo" | "medio";
  lateral?: React.ReactNode;
  leyenda?: React.ReactNode;
  children: (ancho: number, lienzo: React.RefObject<HTMLDivElement | null>) => React.ReactNode;
}

export function Grafico(p: Props) {
  const [verTabla, setVerTabla] = useState(false);
  const [info, setInfo] = useState(false);
  const [ref, ancho] = useAncho<HTMLDivElement>();
  const lienzo = useRef<HTMLDivElement>(null);
  const idTitulo = useId();
  const idInfo = useId();
  return (
    <section
      className={`grafico grafico--${p.ancho ?? "completo"}${p.cargando ? " atenuado" : ""}`}
      aria-labelledby={idTitulo}
      data-seccion={p.seccion}
    >
      <header className="grafico__cabeza">
        <span className="grafico__letra" aria-hidden="true">
          {p.letra}
        </span>
        <div className="grafico__titulos">
          <h2 id={idTitulo}>{p.titulo}</h2>
          {p.descriptivo && (
            <span className="grafico__descriptivo">
              <span className="insignia" data-descriptivo="">
                {T.panorama.descriptivo}
              </span>
              <button
                type="button"
                className="info"
                aria-expanded={info}
                aria-controls={idInfo}
                aria-label={`${T.panorama.descriptivo}: ${T.panorama.como_leer}`}
                onClick={() => setInfo((v) => !v)}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                  <circle cx="12" cy="12" r="9.5" fill="none" stroke="currentColor" strokeWidth="2" />
                  <path d="M12 10.5v6M12 7.2v.1" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
                </svg>
              </button>
            </span>
          )}
        </div>
      </header>
      {p.descriptivo && info && (
        <p id={idInfo} className="grafico__info">
          {T.panorama.descriptivo_ayuda}
        </p>
      )}
      <p className="grafico__leer" data-como-leer="">
        <strong>{T.panorama.como_leer}:</strong> {p.comoLeer}
      </p>
      {p.nota && <p className="grafico__nota">{p.nota}</p>}
      {p.leyenda}
      <div className={p.lateral ? "grafico__cuerpo grafico__cuerpo--lateral" : "grafico__cuerpo"}>
        <div ref={ref} className="grafico__area">
          {p.vacio ? (
            <p className="mensaje">{p.vacio}</p>
          ) : verTabla ? (
            <TablaDatos tabla={p.tabla} titulo={p.titulo} />
          ) : (
            <div ref={lienzo} className="grafico__lienzo" data-emergente="">
              {p.children(ancho, lienzo)}
            </div>
          )}
        </div>
        {p.lateral && <aside className="grafico__lateral">{p.lateral}</aside>}
      </div>
      {!p.vacio && (
        <footer className="grafico__pie">
          <button type="button" className="boton boton--sutil" aria-pressed={verTabla} onClick={() => setVerTabla((v) => !v)}>
            {verTabla ? T.panorama.ver_grafico : T.panorama.ver_tabla}
          </button>
          <button
            type="button"
            className="boton boton--sutil"
            data-descargar=""
            onClick={() => {
              registrar({ evento: "tabla_descargada", seccion: p.seccion });
              descargar(`radar-nino-costero-${p.seccion}.csv`, aCsv(p.tabla));
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M12 4v11m-5-5 5 5 5-5M5 20h14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {T.panorama.descargar}
          </button>
        </footer>
      )}
    </section>
  );
}

export function TablaDatos({ tabla, titulo }: { tabla: Tabla; titulo: string }) {
  return (
    <div className="tabla" tabIndex={0} role="region" aria-label={titulo}>
      <table>
        <caption className="solo-lectores">{titulo}</caption>
        <thead>
          <tr>
            {tabla.columnas.map((c) => (
              <th key={c.id} scope="col" className={c.numero ? "num" : undefined}>
                {c.texto}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tabla.filas.map((f, i) => (
            <tr key={i}>
              {tabla.columnas.map((c) => (
                <td key={c.id} className={c.numero ? "num" : undefined} data-columna={c.id}>
                  {c.formato ? c.formato(f[c.id]) : String(f[c.id] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
