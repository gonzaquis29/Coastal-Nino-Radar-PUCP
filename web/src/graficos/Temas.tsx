import { AxisBottom, AxisLeft } from "@visx/axis";
import { Group } from "@visx/group";
import { scaleLinear, scalePoint } from "@visx/scale";
import { useState } from "react";
import type { Temas as Te } from "../api/tipos";
import { fechaCorta, llenar, mesLargo, numero, T } from "../textos";
import { Emergente, Grafico, Leyenda, puntero, useEmergente } from "./base";
import { COLOR_TEMA, etiquetaEje, etiquetaEjeIzq, MARGEN } from "./comun";

const ALTO = 240;

/** D: área apilada por mes con las 4 categorías de interés y "otros" (D8), con cruz y emergente por mes. */
export function GraficoTemas({ datos, cargando }: { datos: Te; cargando?: boolean }) {
  const { punta, mostrar, ocultar } = useEmergente();
  const [mes, setMes] = useState<number | null>(null);
  const cats = datos.categorias;
  const tabla = {
    columnas: [
      { id: "mes", texto: T.panorama.mes },
      ...cats.map((c) => ({ id: c, texto: c, numero: true })),
    ],
    filas: datos.meses,
  };
  return (
    <Grafico
      seccion="temas"
      letra="D"
      titulo={T.panorama.d_titulo}
      comoLeer={T.panorama.d_leer}
      tabla={tabla}
      nota={llenar(T.panorama.d_hasta, { fecha: fechaCorta(datos.hasta) })}
      vacio={datos.meses.length ? null : T.panorama.sin_datos}
      cargando={cargando}
      ancho="medio"
      leyenda={<Leyenda items={cats.map((c, i) => ({ texto: c, color: COLOR_TEMA[i] }))} />}
    >
      {(ancho, lienzo) => {
        const anchoInterno = ancho - MARGEN.izquierda - MARGEN.derecha;
        const x = scalePoint({ domain: datos.meses.map((m) => m.mes), range: [0, anchoInterno] });
        // pilas: de abajo arriba en el orden fijo de las categorías
        const pilas = datos.meses.map((m) => {
          let base = 0;
          return cats.map((c) => {
            const v = Number(m[c]) || 0;
            const tramo = [base, base + v] as const;
            base += v;
            return tramo;
          });
        });
        const maximo = Math.max(1, ...pilas.map((p) => p[p.length - 1][1]));
        const y = scaleLinear({ domain: [0, maximo], range: [ALTO, 0], nice: true });
        const areas = cats.map((_, k) => {
          const arriba = datos.meses.map((m, i) => `${x(m.mes)},${y(pilas[i][k][1])}`);
          const abajo = datos.meses.map((m, i) => `${x(m.mes)},${y(pilas[i][k][0])}`).reverse();
          return `M${arriba.join("L")}L${abajo.join("L")}Z`;
        });
        const paso = datos.meses.length > 1 ? anchoInterno / (datos.meses.length - 1) : anchoInterno;
        return (
          <>
            <svg
              width={ancho}
              height={ALTO + MARGEN.arriba + MARGEN.abajo}
              role="img"
              aria-label={T.panorama.d_titulo}
              onPointerLeave={() => {
                ocultar();
                setMes(null);
              }}
              onPointerMove={(e) => {
                const p = puntero(e, lienzo.current);
                const i = Math.max(0, Math.min(datos.meses.length - 1, Math.round((p.x - MARGEN.izquierda) / paso)));
                const m = datos.meses[i];
                setMes(i);
                mostrar(MARGEN.izquierda + (x(m.mes) ?? 0), p.y, (
                  <>
                    <strong>{mesLargo(m.mes)}</strong>
                    {[...cats].reverse().map((c) => (
                      <span key={c} className="emergente__fila">
                        <i style={{ background: COLOR_TEMA[cats.indexOf(c)] }} />
                        {c}: {numero(Number(m[c]) || 0)}
                      </span>
                    ))}
                  </>
                ));
              }}
            >
              <Group left={MARGEN.izquierda} top={MARGEN.arriba}>
                {y.ticks(4).map((t) => (
                  <line key={t} x1={0} x2={anchoInterno} y1={y(t)} y2={y(t)} className="rejilla" />
                ))}
                {areas.map((d, k) => (
                  <path key={cats[k]} d={d} className="area" style={{ fill: COLOR_TEMA[k] }} />
                ))}
                {mes !== null && (
                  <line x1={x(datos.meses[mes].mes)} x2={x(datos.meses[mes].mes)} y1={0} y2={ALTO} className="cruz" />
                )}
                <AxisLeft scale={y} numTicks={4} hideAxisLine hideTicks tickLabelProps={etiquetaEjeIzq} tickFormat={(v) => numero(Number(v))} />
                <AxisBottom
                  top={ALTO}
                  scale={x}
                  tickFormat={(m) => fechaCorta(String(m)).split(" ")[0]}
                  numTicks={ancho < 520 ? 4 : 12}
                  axisClassName="eje"
                  tickClassName="eje"
                  tickLabelProps={etiquetaEje}
                  tickValues={ancho < 520 ? datos.meses.filter((_, i) => i % 2 === 0).map((m) => m.mes) : undefined}
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
