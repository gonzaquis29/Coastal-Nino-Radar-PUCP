import { AxisBottom, AxisLeft } from "@visx/axis";
import { Group } from "@visx/group";
import { scaleLinear, scaleLog } from "@visx/scale";
import { useMemo } from "react";
import type { Youtube as Y } from "../api/tipos";
import { decimal, fechaCorta, llenar, mesLargo, numero, porcentaje, T, tresDecimales } from "../textos";
import { Emergente, Grafico, Leyenda, puntero, useEmergente } from "./base";
import { COLOR_SERIE, etiquetaEje, etiquetaEjeIzq } from "./comun";

const ALTO = 300;
const FRANJA_CERO = 22;
const HUECO = 12; // aire entre la escala logarítmica y la franja del 0 // los videos sin interacción no caben en la escala logarítmica: van en su propia franja
const M = { arriba: 10, derecha: 12, abajo: 34, izquierda: 52 };
const PISO = 0.001;

function desplazamiento(i: number): number {
  const h = Math.sin(i * 78.233) * 12345.6789;
  return h - Math.floor(h) - 0.5;
}

/** F: dispersión de la interacción frente a la cercanía, por tipo de canal y sin nombres, más los 2 indicadores. */
export function GraficoYoutube({ datos, cargando }: { datos: Y; cargando?: boolean }) {
  const { punta, mostrar, ocultar } = useEmergente();
  const color = useMemo(() => Object.fromEntries(datos.tipos.map((t, i) => [t.id, COLOR_SERIE[i]])), [datos.tipos]);
  const nombre = Object.fromEntries(datos.tipos.map((t) => [t.id, t.texto]));
  const tabla = {
    columnas: [
      { id: "tipo", texto: T.panorama.tipo },
      { id: "mes", texto: T.panorama.mes },
      { id: "cercania", texto: T.panorama.cercania, numero: true, formato: (v: unknown) => decimal(Number(v)) },
      { id: "tasa", texto: T.panorama.tasa, numero: true, formato: (v: unknown) => porcentaje(Number(v)) },
    ],
    filas: datos.puntos.map((p) => ({ ...p, tipo: nombre[p.tipo] ?? p.tipo })),
  };
  const r = datos.indicador_respuesta;
  const lateral = datos.disponible && (
    <div className="indicadores">
      <div className="indicador" data-indicador="tasa">
        <h3>{T.panorama.f_tasa}</h3>
        <p className="bloque__ayuda">{T.panorama.f_tasa_ayuda}</p>
        <ul>
          {datos.indicador_tasa.map((i) => (
            <li key={i.tipo} data-tipo={i.tipo}>
              <span className="leyenda__marca leyenda__marca--punto" style={{ background: color[i.tipo] }} />
              <span className="indicador__nombre">{i.texto}</span>
              <span className="indicador__valor">{porcentaje(i.mediana)}</span>
              <span className="indicador__n">{llenar(T.panorama.f_n, { n: numero(i.n) })}</span>
            </li>
          ))}
        </ul>
      </div>
      {r && (
        <div className="indicador" data-indicador="respuesta">
          <h3>{T.panorama.f_respuesta}</h3>
          <p className="indicador__respuesta">{r.texto}</p>
          <p className="bloque__ayuda">
            {llenar(T.panorama.f_ic, { rho: tresDecimales(r.rho), inf: tresDecimales(r.ic_inf), sup: tresDecimales(r.ic_sup), n: numero(r.n) })}
          </p>
          <p className="bloque__ayuda">{datos.nota}</p>
        </div>
      )}
    </div>
  );

  return (
    <Grafico
      seccion="youtube"
      letra="F"
      titulo={T.panorama.f_titulo}
      comoLeer={T.panorama.f_leer}
      tabla={tabla}
      nota={datos.disponible && datos.corte ? `${T.panorama.sin_region} ${llenar(T.panorama.f_corte, { fecha: fechaCorta(datos.corte) })}` : T.panorama.sin_region}
      vacio={!datos.disponible ? T.panorama.sin_youtube : datos.puntos.length ? null : T.panorama.sin_datos}
      cargando={cargando}
      lateral={lateral}
      leyenda={datos.disponible ? <Leyenda items={datos.tipos.map((t) => ({ texto: t.texto, color: color[t.id], forma: "punto" }))} /> : null}
    >
      {(ancho, lienzo) => {
        const anchoInterno = ancho - M.izquierda - M.derecha;
        const cercanias = datos.puntos.map((p) => p.cercania);
        const x = scaleLinear({ domain: [Math.min(...cercanias) - 0.02, Math.max(...cercanias) + 0.02], range: [0, anchoInterno] });
        const techo = Math.max(0.01, ...datos.puntos.map((p) => p.tasa)) * 1.2;
        const y = scaleLog({ domain: [PISO, techo], range: [ALTO - FRANJA_CERO - HUECO, 0], clamp: true });
        const puntos = datos.puntos.map((p, i) => ({
          ...p,
          px: x(p.cercania),
          py: p.tasa > 0 ? y(Math.max(p.tasa, PISO)) : ALTO - FRANJA_CERO / 2 + desplazamiento(i) * (FRANJA_CERO - 8),
        }));
        const ticks = [0.001, 0.01, 0.1].filter((t) => t <= techo);
        return (
          <>
            <svg
              width={ancho}
              height={ALTO + M.arriba + M.abajo}
              role="img"
              aria-label={T.panorama.f_titulo}
              onPointerLeave={ocultar}
              onPointerMove={(e) => {
                const p = puntero(e, lienzo.current);
                const mx = p.x - M.izquierda;
                const my = p.y - M.arriba;
                let mejor: (typeof puntos)[number] | null = null;
                let d = 18 * 18;
                for (const q of puntos) {
                  const dd = (q.px - mx) ** 2 + (q.py - my) ** 2;
                  if (dd < d) {
                    d = dd;
                    mejor = q;
                  }
                }
                if (!mejor) return ocultar();
                mostrar(mejor.px + M.izquierda, mejor.py + M.arriba, (
                  <>
                    <strong>{nombre[mejor.tipo]}</strong>
                    <span>{mesLargo(mejor.mes)}</span>
                    <span>
                      {T.panorama.cercania}: {decimal(mejor.cercania)}
                    </span>
                    <span>
                      {T.panorama.tasa}: {porcentaje(mejor.tasa)}
                    </span>
                  </>
                ));
              }}
            >
              <Group left={M.izquierda} top={M.arriba}>
                {ticks.map((t) => (
                  <line key={t} x1={0} x2={anchoInterno} y1={y(t)} y2={y(t)} className="rejilla" />
                ))}
                <rect x={0} y={ALTO - FRANJA_CERO} width={anchoInterno} height={FRANJA_CERO} className="franja-cero" />
                <text x={-8} y={ALTO - FRANJA_CERO / 2} dy={4} textAnchor="end" className="eje__texto">
                  0
                </text>
                {puntos.map((p, i) => (
                  <circle key={i} cx={p.px} cy={p.py} r={3.2} className="punto punto--denso" style={{ fill: color[p.tipo] }} />
                ))}
                <AxisLeft
                  scale={y}
                  tickValues={ticks}
                  hideAxisLine
                  hideTicks
                  tickLabelProps={etiquetaEjeIzq}
                  tickFormat={(v) => porcentaje(Number(v)).replace(",0 %", " %")}
                />
                <AxisBottom
                  top={ALTO}
                  scale={x}
                  numTicks={ancho < 520 ? 4 : 7}
                  tickFormat={(v) => decimal(Number(v))}
                  axisClassName="eje"
                  tickClassName="eje"
                  tickLabelProps={etiquetaEje}
                />
              </Group>
            </svg>
            <div className="grafico__ejes">
              <span>↑ {T.panorama.f_eje_y}</span>
              <span>{T.panorama.f_eje_x} →</span>
            </div>
            <Emergente punta={punta} ancho={ancho} />
          </>
        );
      }}
    </Grafico>
  );
}
