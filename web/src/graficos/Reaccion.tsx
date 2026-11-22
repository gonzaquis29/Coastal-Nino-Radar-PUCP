import { AxisBottom } from "@visx/axis";
import { Group } from "@visx/group";
import { scaleBand, scaleLog } from "@visx/scale";
import type { Reaccion as R } from "../api/tipos";
import { fechaCorta, T } from "../textos";
import { Emergente, Grafico, puntero, useEmergente } from "./base";
import { cambio, etiquetaEje, MARGEN } from "./comun";

const FILA = 22;
const IZQUIERDA = 64;

/** C: pesas por comunicado, del antes al después, en orden de fecha (no por tamaño). Descriptivo (D9). */
export function GraficoReaccion({ datos }: { datos: R }) {
  const { punta, mostrar, ocultar } = useEmergente();
  const filas = datos.comunicados;
  const tabla = {
    columnas: [
      { id: "numero", texto: T.panorama.comunicado },
      { id: "fecha", texto: T.panorama.fecha },
      { id: "veces", texto: T.panorama.veces, numero: true, formato: (v: unknown) => cambio(Number(v)) },
    ],
    filas,
  };
  return (
    <Grafico
      seccion="reaccion"
      letra="C"
      titulo={T.panorama.c_titulo}
      comoLeer={T.panorama.c_leer}
      tabla={tabla}
      descriptivo
      nota={T.panorama.sin_region}
      ancho="medio"
      vacio={filas.length ? null : T.panorama.sin_datos}
    >
      {(ancho, lienzo) => {
        const alto = filas.length * FILA;
        const valores = filas.map((f) => f.veces);
        const piso = Math.min(0.5, ...valores) * 0.8;
        const techo = Math.max(2, ...valores) * 1.25;
        const anchoInterno = ancho - IZQUIERDA - MARGEN.derecha;
        const x = scaleLog({ domain: [piso, techo], range: [0, anchoInterno] });
        const y = scaleBand({ domain: filas.map((_, i) => String(i)), range: [0, alto], padding: 0.3 });
        const ticks = [0.5, 1, 2, 5, 10, 20].filter((t) => t >= piso && t <= techo);
        return (
          <>
            <svg width={ancho} height={alto + MARGEN.arriba + MARGEN.abajo + 18} role="img" aria-label={T.panorama.c_titulo} onPointerLeave={ocultar}>
              <Group left={IZQUIERDA} top={MARGEN.arriba}>
                {ticks.map((t) => (
                  <line key={t} x1={x(t)} x2={x(t)} y1={0} y2={alto} className={t === 1 ? "referencia" : "rejilla"} />
                ))}
                <text x={x(1)} y={alto + 44} textAnchor="middle" className="eje__texto eje__texto--chico">
                  {T.panorama.c_igual}
                </text>
                {filas.map((f, i) => {
                  const cy = (y(String(i)) ?? 0) + y.bandwidth() / 2;
                  return (
                    <g
                      key={f.fecha}
                      onPointerMove={(e) => {
                        const p = puntero(e, lienzo.current);
                        mostrar(p.x, p.y, (
                          <>
                            <strong>
                              {f.numero ? `Comunicado N.° ${f.numero}` : T.panorama.comunicado} · {fechaCorta(f.fecha)}
                            </strong>
                            <span>{cambio(f.veces)}</span>
                          </>
                        ));
                      }}
                    >
                      <rect x={-IZQUIERDA} y={cy - FILA / 2} width={ancho} height={FILA} className="zona-toque" />
                      <text x={-10} y={cy} dy={4} textAnchor="end" className="eje__texto">
                        N.° {f.numero ?? "?"}
                      </text>
                      <line x1={x(1)} x2={x(f.veces)} y1={cy} y2={cy} className="pesa" />
                      <circle cx={x(1)} cy={cy} r={3} className="pesa__antes" />
                      <circle cx={x(f.veces)} cy={cy} r={5.5} className="pesa__despues" />
                    </g>
                  );
                })}
                <AxisBottom
                  top={alto}
                  scale={x}
                  tickValues={ticks}
                  tickFormat={(v) => `×${String(v).replace(".", ",")}`}
                  axisClassName="eje"
                  tickClassName="eje"
                  tickLabelProps={etiquetaEje}
                />
              </Group>
            </svg>
            <p className="grafico__eje-titulo">{T.panorama.c_eje}</p>
            <Emergente punta={punta} ancho={ancho} />
          </>
        );
      }}
    </Grafico>
  );
}
