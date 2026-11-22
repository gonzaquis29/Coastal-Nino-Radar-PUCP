import { AxisBottom, AxisLeft } from "@visx/axis";
import { Group } from "@visx/group";
import { scaleLinear, scaleTime } from "@visx/scale";
import type { Linea as L } from "../api/tipos";
import { fechaCorta, numero, T } from "../textos";
import { Emergente, Grafico, Leyenda, puntero, useEmergente } from "./base";
import { COLOR_GRUPO_A, COLOR_MAGNITUD, dia, etiquetaEje, etiquetaEjeIzq, MAGNITUDES, MARGEN, mesEje, sumarDias } from "./comun";

const ALTO_BANDA = 40;
const SEPARACION = 34;
const ALTO_BARRAS = 210;

/** A: dos bandas sobre la misma fecha, cada una con su eje (no es un eje doble): lo oficial arriba, las notas abajo. */
export function GraficoLinea({ datos, cargando }: { datos: L; cargando?: boolean }) {
  const { punta, mostrar, ocultar } = useEmergente();
  const nombre = Object.fromEntries(datos.grupos.map((g) => [g.id, g.texto]));
  const filas = datos.semanas.map((s) => ({ ...s, total: s.coinciden + s.difieren + s.sin_datos }));
  const tabla = {
    columnas: [
      { id: "semana", texto: T.panorama.semana },
      ...datos.grupos.map((g) => ({ id: g.id, texto: g.texto, numero: true })),
      { id: "total", texto: T.panorama.notas, numero: true },
    ],
    filas,
  };
  const vacio = datos.semanas.length === 0 ? T.panorama.sin_datos : null;

  return (
    <Grafico
      seccion="linea"
      letra="A"
      titulo={T.panorama.a_titulo}
      comoLeer={T.panorama.a_leer}
      tabla={tabla}
      vacio={vacio}
      cargando={cargando}
      leyenda={
        <div className="leyendas">
          <Leyenda items={MAGNITUDES.map((m) => ({ texto: m, color: COLOR_MAGNITUD[m] }))} />
          <Leyenda items={datos.grupos.map((g) => ({ texto: g.texto, color: COLOR_GRUPO_A[g.id] }))} />
        </div>
      }
    >
      {(ancho, lienzo) => {
        if (!datos.semanas.length) return null;
        const inicio = dia(datos.semanas[0].semana);
        const fin = sumarDias(dia(datos.semanas[datos.semanas.length - 1].semana), 7);
        const anchoInterno = ancho - MARGEN.izquierda - MARGEN.derecha;
        const x = scaleTime({ domain: [inicio, fin], range: [0, anchoInterno] });
        const maximo = Math.max(1, ...filas.map((f) => f.total));
        const y = scaleLinear({ domain: [0, maximo], range: [ALTO_BARRAS, 0], nice: true });
        const alto = MARGEN.arriba + ALTO_BANDA + SEPARACION + ALTO_BARRAS + MARGEN.abajo;
        const paso = Math.max(2, x(sumarDias(inicio, 7)) - x(inicio));
        const anchoBarra = Math.max(1, paso - 2); // 2 px de separación entre barras
        const ticks = ancho < 520 ? 4 : 8;
        return (
          <>
            <svg width={ancho} height={alto} role="img" aria-label={T.panorama.a_titulo} onPointerLeave={ocultar}>
              <Group left={MARGEN.izquierda} top={MARGEN.arriba}>
                <text className="eje__titulo" x={0} y={-2}>
                  {T.panorama.a_oficial}
                </text>
                {datos.comunicados.map((c) => {
                  const a = Math.max(0, x(dia(c.desde)));
                  const b = Math.min(anchoInterno, x(c.hasta ? dia(c.hasta) : fin));
                  if (b <= a) return null;
                  return (
                    <g key={c.id}>
                      <rect
                        x={a}
                        y={6}
                        width={Math.max(1, b - a - 2)}
                        height={ALTO_BANDA - 6}
                        rx={4}
                        style={{ fill: COLOR_MAGNITUD[c.magnitud] ?? "var(--sin-datos)" }}
                        onPointerMove={(e) => {
                          const p = puntero(e, lienzo.current);
                          mostrar(p.x, p.y, (
                            <>
                              <strong>Comunicado N.° {c.numero}</strong>
                              <span>{c.estado}</span>
                              <span>
                                {T.panorama.magnitud}: {c.magnitud}
                              </span>
                              <span>
                                {fechaCorta(c.desde)}
                                {c.hasta ? ` – ${fechaCorta(c.hasta)}` : ""}
                              </span>
                            </>
                          ));
                        }}
                      />
                      <line x1={a} x2={a} y1={2} y2={ALTO_BANDA} className="marca-comunicado" />
                    </g>
                  );
                })}
                <Group top={ALTO_BANDA + SEPARACION}>
                  <text className="eje__titulo" x={0} y={-10}>
                    {T.panorama.a_notas}
                  </text>
                  {y.ticks(4).map((t) => (
                    <line key={t} x1={0} x2={anchoInterno} y1={y(t)} y2={y(t)} className="rejilla" />
                  ))}
                  {filas.map((f) => {
                    const x0 = x(dia(f.semana)) + 1;
                    let base = ALTO_BARRAS;
                    const piezas = (["coinciden", "difieren", "sin_datos"] as const).map((g) => {
                      const h = ALTO_BARRAS - y(f[g]);
                      const pieza = h > 0 && (
                        <rect key={g} x={x0} y={base - h} width={anchoBarra} height={Math.max(0, h - 1)} style={{ fill: COLOR_GRUPO_A[g] }} />
                      );
                      base -= h;
                      return pieza;
                    });
                    return (
                      <g key={f.semana}>
                        {piezas}
                        <rect
                          x={x0 - 1}
                          y={0}
                          width={paso}
                          height={ALTO_BARRAS}
                          className="zona-toque"
                          onPointerMove={(e) => {
                            const p = puntero(e, lienzo.current);
                            mostrar(p.x, p.y, (
                              <>
                                <strong>
                                  {T.panorama.semana} {fechaCorta(f.semana)}
                                </strong>
                                {(["coinciden", "difieren", "sin_datos"] as const).map((g) => (
                                  <span key={g} className="emergente__fila">
                                    <i style={{ background: COLOR_GRUPO_A[g] }} />
                                    {nombre[g]}: {numero(f[g])}
                                  </span>
                                ))}
                              </>
                            ));
                          }}
                        />
                      </g>
                    );
                  })}
                  <AxisLeft scale={y} numTicks={4} hideAxisLine hideTicks tickLabelProps={etiquetaEjeIzq} tickFormat={(v) => numero(Number(v))} />
                  <AxisBottom
                    top={ALTO_BARRAS}
                    scale={x}
                    numTicks={ticks}
                    tickFormat={(d) => mesEje(d as Date)}
                    axisClassName="eje"
                    tickClassName="eje"
                    tickLabelProps={etiquetaEje}
                  />
                </Group>
              </Group>
            </svg>
            <Emergente punta={punta} ancho={ancho} />
          </>
        );
      }}
    </Grafico>
  );
}
