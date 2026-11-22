import { AxisBottom } from "@visx/axis";
import { Group } from "@visx/group";
import { scaleBand, scaleTime } from "@visx/scale";
import { useMemo } from "react";
import type { Magnitudes as M } from "../api/tipos";
import { fechaCorta, T } from "../textos";
import { Emergente, Grafico, Leyenda, puntero, useEmergente } from "./base";
import { dia, etiquetaEje, MARGEN, mesEje, sumarDias } from "./comun";

const ALTO = 250;
const IZQUIERDA = 104;
const COINCIDE = "respaldada";

/** Desplazamiento vertical fijo por punto (no al azar), para que los datos del mismo día no se tapen. */
function desplazamiento(i: number): number {
  const h = Math.sin(i * 12.9898) * 43758.5453;
  return h - Math.floor(h) - 0.5;
}

/**
 * B: la magnitud oficial como escalón y un punto por cada dato de magnitud de las notas. La información emergente
 * nunca muestra el medio (P12): la API ni siquiera lo envía.
 */
export function GraficoMagnitudes({ datos, cargando }: { datos: M; cargando?: boolean }) {
  const { punta, mostrar, ocultar } = useEmergente();
  const nombre = useMemo(() => Object.fromEntries(datos.grupos.map((g) => [g.id, g.texto])), [datos.grupos]);
  const tabla = {
    columnas: [
      { id: "fecha", texto: T.panorama.fecha },
      { id: "magnitud", texto: T.panorama.magnitud },
      { id: "grupo", texto: T.panorama.grupo },
    ],
    filas: datos.puntos.map((p) => ({ ...p, grupo: nombre[p.grupo] ?? p.grupo })),
  };
  const vacio = datos.puntos.length === 0 ? T.panorama.sin_datos : null;

  return (
    <Grafico
      seccion="magnitudes"
      letra="B"
      titulo={T.panorama.b_titulo}
      comoLeer={T.panorama.b_leer}
      tabla={tabla}
      vacio={vacio}
      cargando={cargando}
      ancho="medio"
      leyenda={
        <Leyenda
          items={[
            { texto: T.panorama.b_coincide, color: "var(--coinciden)", forma: "punto" },
            { texto: T.panorama.b_otros, color: "var(--difieren)", forma: "punto" },
            { texto: T.panorama.a_oficial, color: "var(--tinta)", forma: "linea" },
          ]}
        />
      }
    >
      {(ancho, lienzo) => {
        const fechas = datos.puntos.map((p) => p.fecha).sort();
        const inicio = dia(datos.escalon[0]?.desde > fechas[0] ? datos.escalon[0].desde : fechas[0]);
        const fin = sumarDias(dia(fechas[fechas.length - 1]), 3);
        const anchoInterno = ancho - IZQUIERDA - MARGEN.derecha;
        const x = scaleTime({ domain: [inicio, fin], range: [0, anchoInterno] });
        const y = scaleBand({ domain: [...datos.magnitudes].reverse(), range: [0, ALTO], padding: 0.2 });
        const centro = (m: string) => (y(m) ?? 0) + y.bandwidth() / 2;
        const puntos = datos.puntos.map((p, i) => ({
          ...p,
          px: x(dia(p.fecha)),
          py: centro(p.magnitud) + desplazamiento(i) * y.bandwidth() * 0.8,
        }));
        // escalón: un tramo horizontal por comunicado y un salto vertical entre ellos
        let camino = "";
        datos.escalon.forEach((s, k) => {
          const a = Math.max(0, x(dia(s.desde)));
          const b = Math.min(anchoInterno, x(s.hasta ? dia(s.hasta) : fin));
          if (b <= 0 || a >= anchoInterno || !s.magnitud) return;
          const yy = centro(s.magnitud);
          camino += `${k === 0 || !camino ? "M" : "L"}${a},${yy}H${b}`;
        });
        const cercano = (mx: number, my: number) => {
          let mejor: (typeof puntos)[number] | null = null;
          let d = 20 * 20;
          for (const p of puntos) {
            const dd = (p.px - mx) ** 2 + (p.py - my) ** 2;
            if (dd < d) {
              d = dd;
              mejor = p;
            }
          }
          return mejor;
        };
        return (
          <>
            <svg
              width={ancho}
              height={ALTO + MARGEN.arriba + MARGEN.abajo}
              role="img"
              aria-label={T.panorama.b_titulo}
              onPointerLeave={ocultar}
              onPointerMove={(e) => {
                const p = puntero(e, lienzo.current);
                const c = cercano(p.x - IZQUIERDA, p.y - MARGEN.arriba);
                if (!c) return ocultar();
                mostrar(c.px + IZQUIERDA, c.py + MARGEN.arriba, (
                  <>
                    <strong>{fechaCorta(c.fecha)}</strong>
                    <span>
                      {T.panorama.magnitud}: {c.magnitud}
                    </span>
                    <span>{nombre[c.grupo]}</span>
                  </>
                ));
              }}
            >
              <Group left={IZQUIERDA} top={MARGEN.arriba}>
                {datos.magnitudes.map((m) => (
                  <g key={m}>
                    <line x1={0} x2={anchoInterno} y1={centro(m)} y2={centro(m)} className="rejilla" />
                    <text x={-10} y={centro(m)} dy={4} textAnchor="end" className="eje__texto">
                      {m}
                    </text>
                  </g>
                ))}
                {puntos.map((p, i) => (
                  <circle
                    key={i}
                    cx={p.px}
                    cy={p.py}
                    r={4}
                    className="punto"
                    style={{ fill: p.grupo === COINCIDE ? "var(--coinciden)" : "var(--difieren)" }}
                  />
                ))}
                <path d={camino} className="escalon" />
                <AxisBottom
                  top={ALTO}
                  scale={x}
                  numTicks={ancho < 520 ? 4 : 6}
                  tickFormat={(d) => mesEje(d as Date)}
                  axisClassName="eje"
                  tickClassName="eje"
                  tickLabelProps={etiquetaEje}
                />
              </Group>
            </svg>
            <Emergente punta={punta} ancho={ancho} />
          </>
        );
      }}
    </Grafico>
  );
}
