import { useId, useState } from "react";
import { enlaceSeguro } from "../api/cliente";
import type { Estado, Macroregion } from "../api/tipos";
import { fechaCorta, llenar, T } from "../textos";
import { Palabra } from "./Glosario";
import { Escalera, Regla } from "./Regla";

interface Props {
  estado: Estado | null;
  zona: Macroregion;
  cambiarZona: (z: Macroregion) => void;
  /** La magnitud que dice el mensaje verificado, para marcarla en la regla junto a la del ENFEN. */
  magnitudMensaje?: string | null;
}

const ZONAS = Object.entries(T.macroregiones) as [Macroregion, string][];

/**
 * Lo vigente en la zona (sección 11): el estado del ENFEN en su escalera, la magnitud en la regla y de dónde sale.
 * Reemplaza la línea de estado de D2; los avisos del Senamhi van aparte (AvisosZona).
 */
export function PanelZona({ estado, zona, cambiarZona, magnitudMensaje }: Props) {
  const [eligiendo, setEligiendo] = useState(false);
  const idZona = useId();
  const c = estado?.comunicado;
  const url = enlaceSeguro(c?.url);

  return (
    <section className="zona" aria-labelledby="titulo-zona">
      <div className="zona__cabeza">
        <p className="eyebrow">
          <button
            type="button"
            className="zona__cambiar"
            aria-expanded={eligiendo}
            aria-controls={idZona}
            onClick={() => setEligiendo((v) => !v)}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12Z" fill="none" stroke="currentColor" strokeWidth="2.4" />
              <circle cx="12" cy="10" r="2.6" fill="currentColor" />
            </svg>
            {T.macroregiones[zona]}
            <span className="solo-lectores">. {T.verificar.cambiar_zona}</span>
          </button>
          {estado && <span> · {llenar(T.verificar.hoy, { fecha: fechaCorta(estado.fecha) })}</span>}
        </p>
        <h1 id="titulo-zona" className="zona__estado">
          {c ? c.estado : estado ? T.verificar.sin_comunicado : <span className="esqueleto" aria-hidden="true" />}
          {!c && !estado && <span className="solo-lectores">{T.comun.cargando}</span>}
        </h1>
      </div>

      {eligiendo && (
        <div id={idZona} className="zona__panel aparece" role="group" aria-label={T.verificar.elige_zona}>
          <div className="chips">
            {ZONAS.map(([id, texto]) => (
              <button
                key={id}
                type="button"
                className="chip"
                aria-pressed={id === zona}
                onClick={() => {
                  cambiarZona(id);
                  setEligiendo(false);
                }}
              >
                {texto}
              </button>
            ))}
          </div>
        </div>
      )}

      {c && (
        <>
          <p className="zona__bajada">
            {T.verificar.lo_dice} <Palabra termino="enfen">ENFEN</Palabra>
            {`, ${T.glosario.enfen_corto}. `}
            {llenar(T.comun.comunicado, { numero: c.numero, fecha: c.fecha_texto })}
            {url && (
              <>
                {" · "}
                <a href={url} target="_blank" rel="noopener noreferrer">
                  {T.verificar.leer_comunicado}
                  <span aria-hidden="true"> ↗</span>
                </a>
              </>
            )}
          </p>
          <div className="zona__medidas">
            <div className="zona__medida">
              <p className="eyebrow">
                {T.verificar.estado_de} <Palabra termino="nino">{T.verificar.nino_costero}</Palabra>
              </p>
              <Escalera estado={c.estado} />
            </div>
            <Regla
              enfen={c.magnitud}
              mensaje={magnitudMensaje}
              titulo={T.verificar.magnitud_titulo}
              conGlosario
            />
          </div>
        </>
      )}

    </section>
  );
}

// La escala del Senamhi tiene 4 niveles; verde es «sin peligro» y no trae aviso (sección 15)
const ESCALA_SENAMHI = ["verde", "amarillo", "naranja", "rojo"];
const NOMBRE_NIVEL: Record<string, string> = {
  amarillo: T.verificar.nivel_amarillo,
  naranja: T.verificar.nivel_naranja,
  rojo: T.verificar.nivel_rojo,
};

/** El nivel de un aviso en la escala de los 4 del Senamhi: los tramos se llenan hasta el nivel, con nombre y posición. */
function NivelSenamhi({ nivel }: { nivel: string }) {
  const posicion = ESCALA_SENAMHI.indexOf(nivel) + 1;
  if (posicion < 2) {
    return <span className="nivel-senamhi nivel-senamhi--otro">{llenar(T.verificar.nivel_aviso, { nivel })}</span>;
  }
  const nombre = NOMBRE_NIVEL[nivel];
  return (
    <span
      className={`nivel-senamhi nivel-senamhi--${nivel}`}
      role="img"
      aria-label={llenar(T.verificar.nivel_escala_lectores, { nombre: nombre.toLowerCase(), posicion })}
    >
      <span className="nivel-senamhi__escala" aria-hidden="true">
        {ESCALA_SENAMHI.map((n, i) => (
          <i key={n} className={i < posicion ? `nivel-senamhi__tramo nivel-senamhi__tramo--${n}` : "nivel-senamhi__tramo"} />
        ))}
      </span>
      <span className="nivel-senamhi__nombre" aria-hidden="true">
        {llenar(T.verificar.nivel_escala, { nombre, posicion })}
      </span>
    </span>
  );
}

/** Los avisos vigentes del Senamhi para la zona, a la vista. En el celular van después del mensaje (sección 11). */
export function AvisosZona({ estado }: { estado: Estado | null }) {
  if (!estado) return null;
  const vigentes = estado.avisos.filter((a) => a.vigente);
  return (
    <div className="zona__avisos">
      <h2 className="eyebrow">
        {T.verificar.avisos_del} <Palabra termino="senamhi">Senamhi</Palabra> {T.verificar.para_tu_zona}
      </h2>
      {vigentes.length === 0 ? (
        <p className="zona__sin-avisos">{T.verificar.sin_avisos}</p>
      ) : (
        <ul className="avisos">
          {vigentes.map((a) => {
            const enlace = enlaceSeguro(a.url);
            return (
              <li key={a.numero}>
                <span className="avisos__numero">N.° {a.numero}</span>
                <span className="avisos__texto">
                  {enlace ? (
                    <a href={enlace} target="_blank" rel="noopener noreferrer">
                      {a.titulo}
                    </a>
                  ) : (
                    a.titulo
                  )}
                  <small>{llenar(T.verificar.aviso_hasta, { fin: fechaCorta(a.fin.slice(0, 10)) })}</small>
                </span>
                <span className="avisos__nivel">
                  <NivelSenamhi nivel={a.nivel} />
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
