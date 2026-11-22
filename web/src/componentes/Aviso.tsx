import type { TipoError } from "../api/cliente";
import { T } from "../textos";

const TEXTO: Record<TipoError, string> = {
  sin_conexion: T.comun.sin_conexion,
  arrancando: T.comun.arrancando,
  error: T.comun.error,
};

/** Un error que se entiende y se puede reintentar. */
export function AvisoError({ tipo, reintentar }: { tipo: TipoError; reintentar?: () => void }) {
  return (
    <div className="mensaje mensaje--error" role="alert">
      <span>{TEXTO[tipo]}</span>
      {reintentar && (
        <button type="button" className="boton boton--sutil" onClick={reintentar}>
          {T.comun.reintentar}
        </button>
      )}
    </div>
  );
}
