import { enlaceSeguro } from "../api/cliente";
import type { Comunicado } from "../api/tipos";
import { llenar, T } from "../textos";

interface Props {
  texto: string;
  comunicado?: Comunicado | null;
  fuente?: string;
  url?: string | null;
  etiqueta?: string;
  alAbrir?: () => void;
}

// Las viñetas de los PDF llegan como caracteres de uso privado (se ven como un cuadro): solo se ocultan en pantalla
const VINETA = new RegExp(`^[${String.fromCharCode(0xe000)}-${String.fromCharCode(0xf8ff)}${String.fromCharCode(0x2022, 0x25aa, 0x25cf)}]\\s*`);

/** Un texto oficial literal (P4), siempre con su fuente. Los textos se muestran como texto, nunca como HTML. */
export function Cita({ texto, comunicado, fuente, url, etiqueta, alAbrir }: Props) {
  const destino = enlaceSeguro(url ?? comunicado?.url);
  const nombre = comunicado
    ? llenar(T.comun.comunicado, { numero: comunicado.numero, fecha: comunicado.fecha_texto })
    : fuente;
  return (
    <blockquote className="cita">
      {etiqueta && <span className="cita__etiqueta">{etiqueta}</span>}
      <p>{texto.replace(VINETA, "")}</p>
      {(nombre || destino) && (
        <footer>
          {nombre && (
            <span>
              {T.comun.fuente}: {nombre}
            </span>
          )}
          {destino && (
            <a href={destino} target="_blank" rel="noopener noreferrer" onClick={alAbrir}>
              {T.comun.abrir_fuente}
              <span aria-hidden="true"> ↗</span>
            </a>
          )}
        </footer>
      )}
    </blockquote>
  );
}
