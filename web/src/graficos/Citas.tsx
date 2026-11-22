import type { Citas as C } from "../api/tipos";
import { numero, porcentaje, T } from "../textos";
import { Emergente, Grafico, Leyenda, puntero, useEmergente } from "./base";
import { COLOR_SERIE } from "./comun";

const NOMBRE_ACTOR: Record<string, string> = { ENFEN: "ENFEN", SENAMHI: "Senamhi", INDECI: "INDECI" };

/**
 * E: un medidor por medio y por institución. Los medios van en orden alfabético (lo da la API) para que no se lea
 * como un ranking (P12).
 */
export function GraficoCitas({ datos }: { datos: C }) {
  const { punta, mostrar, ocultar } = useEmergente();
  const maximo = Math.max(0.05, ...datos.medios.flatMap((m) => datos.actores.map((a) => Number(m[a]))));
  const escala = Math.min(1, Math.ceil(maximo * 10) / 10);
  const tabla = {
    columnas: [
      { id: "medio_texto", texto: T.panorama.medio },
      { id: "notas", texto: T.panorama.notas, numero: true },
      ...datos.actores.map((a) => ({ id: a, texto: NOMBRE_ACTOR[a] ?? a, numero: true, formato: (v: unknown) => porcentaje(Number(v)) })),
    ],
    filas: datos.medios,
  };
  return (
    <Grafico
      seccion="citas"
      letra="E"
      titulo={T.panorama.e_titulo}
      comoLeer={T.panorama.e_leer}
      tabla={tabla}
      nota={T.panorama.sin_region}
      ancho="medio"
      vacio={datos.medios.length ? null : T.panorama.sin_datos}
      leyenda={<Leyenda items={datos.actores.map((a, i) => ({ texto: NOMBRE_ACTOR[a] ?? a, color: COLOR_SERIE[i] }))} />}
    >
      {(ancho, lienzo) => (
        <>
          <ul className="medidores" onPointerLeave={ocultar} data-orden="alfabetico">
            {datos.medios.map((m) => (
              <li key={m.medio} className="medidores__medio" data-medio={m.medio_texto}>
                <p className="medidores__nombre">
                  <strong>{m.medio_texto}</strong>
                  <span>
                    {numero(m.notas)} {T.panorama.notas.toLowerCase()}
                  </span>
                </p>
                {datos.actores.map((a, i) => {
                  const v = Number(m[a]);
                  return (
                    <div
                      key={a}
                      className="medidores__fila"
                      onPointerMove={(e) => {
                        const p = puntero(e, lienzo.current);
                        mostrar(p.x, p.y, (
                          <>
                            <strong>{m.medio_texto}</strong>
                            <span>
                              {NOMBRE_ACTOR[a]}: {porcentaje(v)} de {numero(m.notas)} {T.panorama.notas.toLowerCase()}
                            </span>
                          </>
                        ));
                      }}
                    >
                      <span className="medidores__actor">{NOMBRE_ACTOR[a]}</span>
                      <span className="medidores__pista">
                        <span className="medidores__barra" style={{ width: `${(v / escala) * 100}%`, background: COLOR_SERIE[i] }} />
                      </span>
                      <span className="medidores__valor">{porcentaje(v)}</span>
                    </div>
                  );
                })}
              </li>
            ))}
          </ul>
          <Emergente punta={punta} ancho={ancho} />
        </>
      )}
    </Grafico>
  );
}
