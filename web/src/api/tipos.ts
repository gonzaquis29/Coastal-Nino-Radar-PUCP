// Lo que devuelve la API (radar.app.servicio). Los campos son fijos; P7 los recorre de punta a punta.

export type Macroregion = "costa_norte" | "costa_centro" | "lima";
export type Interes = "pesca" | "lluvias" | "calor" | "prevencion";
export type Nivel = "coincide" | "revisar" | "no_coincide";
export type Banda = "cercano" | "intermedio" | "lejano";

export interface Comunicado {
  id: string;
  numero: number;
  fecha: string;
  fecha_texto: string;
  estado: string;
  magnitud: string;
  plazo: string;
  url: string;
  proximo: string;
}

export interface Aviso {
  numero: number;
  titulo: string;
  tipo: string;
  nivel: string;
  vigente: boolean;
  inicio: string;
  fin: string;
  url: string;
}

export interface Estado {
  fecha: string;
  macroregion: Macroregion;
  macroregion_texto: string;
  comunicado: Comunicado | null;
  avisos: Aviso[];
}

export interface Parrafo {
  texto: string;
  parrafo: string;
  comunicado: Comunicado | null;
}

export interface Dato {
  dato: string;
  dato_texto: string;
  valor: string;
  categoria: string;
  nivel: Nivel | null;
  icono: string;
  veredicto: string;
  resaltado: [number, number] | null;
  oficial: {
    comunicado: Comunicado;
    dice: string;
    cita: { cita: string; parrafo: string } | null;
    anterior?: Comunicado;
  };
}

export interface Afirmacion {
  frase: string;
  datos: Dato[];
}

export interface Nota {
  medio: string;
  medio_texto: string;
  id: string;
  titular: string;
  fecha: string;
  url: string;
  macroregion: string;
}

export interface QueHacer {
  interes: Interes;
  interes_texto: string;
  intereses: { id: Interes; texto: string }[];
  oficiales: Parrafo[];
  nota: Nota | null;
}

interface ResultadoBase {
  fecha: string;
  palabras: number;
  estado: Estado;
  titulo: string;
  resumen: string;
  aviso: string | null;
  oficial_cercano: Parrafo | null;
  que_hacer: QueHacer;
}

export interface ResultadoDatos extends ResultadoBase {
  tipo: "datos";
  nivel: Nivel;
  icono: string;
  afirmaciones: Afirmacion[];
  linea_tiempo: (Comunicado & { vigente: boolean; respaldo: boolean })[];
}

export interface ResultadoCercania extends ResultadoBase {
  tipo: "cercania";
  nivel: Banda;
  medidor: { valor: number; media_desde: number; alta_desde: number };
}

export interface ResultadoInsuficiente extends ResultadoBase {
  tipo: "insuficiente";
  nivel: null;
}

export interface ResultadoFueraDeTema extends ResultadoBase {
  tipo: "fuera_de_tema";
  nivel: null;
}

export type Resultado = ResultadoDatos | ResultadoCercania | ResultadoInsuficiente | ResultadoFueraDeTema;

export interface Respuesta {
  herramienta: "estado_vigente" | "buscar_oficial" | "medir_discrepancia" | "recomendar" | "fuera";
  texto: string;
  citas: { cita: string; parrafo: string; fuente: string; comunicado: Comunicado | null; url: string | null }[];
  entendido: {
    fecha: string;
    fecha_texto: string;
    macroregion: Macroregion;
    macroregion_texto: string;
    interes: Interes;
    interes_texto: string;
  };
}

// ---------------------------------------------------------------- Panorama

export interface Hallazgo {
  id: "reaccion" | "coinciden" | "anteriores";
  valor: string;
  texto: string;
  descriptivo: boolean;
  serie: { x: string; y: number }[];
}

export interface ComunicadoTramo {
  id: string;
  numero: number;
  desde: string;
  hasta: string | null;
  estado: string;
  magnitud: string;
}

export interface Linea {
  grupos: { id: "coinciden" | "difieren" | "sin_datos"; texto: string }[];
  semanas: { semana: string; coinciden: number; difieren: number; sin_datos: number }[];
  comunicados: ComunicadoTramo[];
}

export interface Magnitudes {
  magnitudes: string[];
  grupos: { id: string; texto: string }[];
  escalon: { desde: string; hasta: string | null; magnitud: string; numero: number }[];
  puntos: { fecha: string; magnitud: string; grupo: string }[];
}

export interface Reaccion {
  comunicados: { fecha: string; numero: number | null; veces: number }[];
}

export interface Temas {
  categorias: string[];
  hasta: string;
  meses: ({ mes: string } & Record<string, number | string>)[];
}

export interface Citas {
  actores: string[];
  medios: ({ medio: string; medio_texto: string; notas: number } & Record<string, number | string>)[];
}

export interface Youtube {
  disponible: boolean;
  por_region: false;
  nota: string;
  tipos: { id: string; texto: string }[];
  corte?: string;
  total?: number;
  puntos: { tipo: string; mes: string; cercania: number; tasa: number }[];
  indicador_tasa: { tipo: string; texto: string; mediana: number; n: number }[];
  indicador_respuesta: {
    respuesta: string;
    texto: string;
    rho: number;
    ic_inf: number;
    ic_sup: number;
    n: number;
  } | null;
}

export interface Panorama {
  hallazgos: Hallazgo[];
  linea: Linea;
  magnitudes: Magnitudes;
  reaccion: Reaccion;
  temas: Temas;
  citas: Citas;
  youtube: Youtube;
}

export type Seccion = keyof Panorama;

export interface Metodologia {
  tarjetas: {
    titulo: string;
    que_mide: string;
    pasa: boolean;
    pasan: number;
    total: number;
    criterios: { criterio: string; valor: string; umbral: string; pasa: boolean }[];
  }[];
  limitaciones: string[];
  uso: {
    sesiones: number;
    eventos: Record<string, number>;
    embudo: { paso: string; sesiones: number }[];
    resultados: Record<string, number>;
    herramientas: Record<string, number>;
    segundos_por_pantalla: Record<string, number>;
  };
}

export interface Opciones {
  macroregiones: { id: Macroregion; texto: string }[];
  intereses: { id: Interes; texto: string }[];
}
