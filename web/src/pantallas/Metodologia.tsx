import { useEffect } from "react";
import { api } from "../api/cliente";
import { AvisoError } from "../componentes/Aviso";
import { useConsulta } from "../ganchos";
import { llenar, numero, T } from "../textos";
import "../estilos/panorama.css";

const PANTALLAS: Record<string, string> = {
  verificar: T.comun.nav_verificar,
  preguntar: T.comun.nav_preguntar,
  panorama: T.comun.nav_panorama,
  metodologia: T.comun.nav_metodologia,
};

/** D11: para el evaluador. Una fila por componente con su criterio, su resultado y si pasó. */
export default function Metodologia() {
  const m = useConsulta((s) => api.metodologia(s));
  const { ejecutar } = m;
  useEffect(() => {
    ejecutar();
  }, [ejecutar]);
  const d = m.datos;
  const maximo = Math.max(1, ...(d?.uso.embudo.map((e) => e.sesiones) ?? [1]));
  return (
    <div className="metodologia envoltura-ancha">
      <header className="panorama__cabeza">
        <h1>{T.metodologia.titulo}</h1>
        <p>{T.metodologia.intro}</p>
      </header>
      {m.error && <AvisoError tipo={m.error} reintentar={() => ejecutar()} />}
      {!d && !m.error && <p className="cargando">{T.comun.cargando}</p>}
      {d && (
        <div className="metodologia__cuerpo">
          <section aria-labelledby="titulo-validacion">
            <h2 id="titulo-validacion">{T.metodologia.validacion}</h2>
            <ul className="validacion">
              {d.tarjetas.map((t) => (
                <li key={t.titulo} className={t.pasa ? "pasa" : "no-pasa"}>
                  <details>
                    <summary>
                      <span className={`validacion__estado ${t.pasa ? "pasa" : "no-pasa"}`}>
                        <span aria-hidden="true">{t.pasa ? "✓" : "–"}</span>
                        {t.pasa ? T.metodologia.pasa : T.metodologia.no_pasa}
                      </span>
                      <span className="validacion__titulo">
                        <strong>{t.titulo}</strong>
                        <span>{t.que_mide}</span>
                      </span>
                      <span className="validacion__cuenta">{llenar(T.metodologia.pasan, { pasan: t.pasan, total: t.total })}</span>
                    </summary>
                    <div className="tabla">
                      <table>
                        <caption className="solo-lectores">{t.titulo}</caption>
                        <thead>
                          <tr>
                            <th scope="col">{T.metodologia.criterio}</th>
                            <th scope="col" className="num">
                              {T.metodologia.valor}
                            </th>
                            <th scope="col" className="num">
                              {T.metodologia.umbral}
                            </th>
                            <th scope="col">{T.metodologia.pasa}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {t.criterios.map((c) => (
                            <tr key={c.criterio}>
                              <td>{c.criterio}</td>
                              <td className="num">{c.valor}</td>
                              <td className="num">{c.umbral}</td>
                              <td>{c.pasa ? T.metodologia.pasa : T.metodologia.no_pasa}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </details>
                </li>
              ))}
            </ul>
          </section>

          <aside className="metodologia__lado">
            <section className="tarjeta uso" aria-labelledby="titulo-uso">
              <h2 id="titulo-uso">{T.metodologia.uso}</h2>
              <p className="bloque__ayuda">{T.metodologia.uso_ayuda}</p>
              {d.uso.sesiones === 0 ? (
                <p className="mensaje">{T.metodologia.sin_uso}</p>
              ) : (
                <>
                  <p className="uso__cifra">
                    <strong>{numero(d.uso.sesiones)}</strong> {T.metodologia.sesiones.toLowerCase()}
                  </p>
                  <h3>{T.metodologia.embudo}</h3>
                  <ol className="embudo">
                    {d.uso.embudo.map((e) => (
                      <li key={e.paso}>
                        <span className="embudo__paso">{e.paso}</span>
                        <span className="embudo__pista">
                          <span className="embudo__barra" style={{ width: `${(e.sesiones / maximo) * 100}%` }} />
                        </span>
                        <span className="embudo__valor">{numero(e.sesiones)}</span>
                      </li>
                    ))}
                  </ol>
                  {Object.keys(d.uso.segundos_por_pantalla).length > 0 && (
                    <>
                      <h3>{T.metodologia.segundos}</h3>
                      <ul className="uso__tiempos">
                        {Object.entries(d.uso.segundos_por_pantalla).map(([p, s]) => (
                          <li key={p}>
                            <span>{PANTALLAS[p] ?? p}</span>
                            <strong>{numero(s)} s</strong>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </>
              )}
            </section>
            <section className="tarjeta limitaciones" aria-labelledby="titulo-limitaciones">
              <h2 id="titulo-limitaciones">{T.metodologia.limitaciones}</h2>
              <ul>
                {d.limitaciones.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </section>
          </aside>
        </div>
      )}
    </div>
  );
}
