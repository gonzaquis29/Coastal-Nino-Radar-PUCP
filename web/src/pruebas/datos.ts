// Respuestas sintéticas con la forma exacta de la API (nada de notas reales: el repo es público).
import type { Panorama, ResultadoCercania, ResultadoDatos } from "../api/tipos";

const comunicado = {
  id: "enfen-2026-20",
  numero: 20,
  fecha: "2026-11-13",
  fecha_texto: "13 de noviembre de 2026",
  estado: "Alerta de El Niño Costero",
  magnitud: "extraordinaria",
  plazo: "hasta febrero de 2027",
  url: "https://enfen.example/20",
  proximo: "2026-11-30",
};
const estado = { fecha: "2026-11-22", macroregion: "lima" as const, macroregion_texto: "Lima y Callao", comunicado, avisos: [] };
const queHacer = {
  interes: "prevencion" as const,
  interes_texto: "Prevención y emergencias",
  intereses: [
    { id: "pesca" as const, texto: "Pesca y mar" },
    { id: "prevencion" as const, texto: "Prevención y emergencias" },
  ],
  oficiales: [{ texto: "Se recomienda a la población mantenerse informada.", parrafo: "p1", comunicado }],
  nota: null,
};

export const cercania: ResultadoCercania = {
  tipo: "cercania",
  nivel: "cercano",
  titulo: "Cercanía: Alta",
  resumen: "Habla de lo mismo que el comunicado vigente del ENFEN.",
  aviso: "Este texto no trae datos que podamos comparar.",
  medidor: { valor: 0.6, media_desde: 0.3, alta_desde: 0.41 },
  fecha: "2026-11-22",
  palabras: 12,
  estado,
  oficial_cercano: { texto: "El ENFEN mantiene el estado de alerta.", parrafo: "p2", comunicado },
  que_hacer: queHacer,
};

export const conDatos: ResultadoDatos = {
  tipo: "datos",
  nivel: "revisar",
  icono: "!",
  titulo: "Usa un dato anterior del ENFEN",
  resumen: "Algunos datos de este texto no son los del comunicado vigente del ENFEN. Revisa por qué.",
  aviso: null,
  fecha: "2026-11-22",
  palabras: 10,
  estado,
  afirmaciones: [
    {
      frase: "El Niño costero será débil",
      datos: [
        {
          dato: "magnitud",
          dato_texto: "Magnitud",
          valor: "débil",
          categoria: "desactualizada",
          nivel: "revisar",
          icono: "!",
          veredicto: "Usa un dato anterior del ENFEN",
          resaltado: [21, 26],
          oficial: {
            comunicado,
            dice: "magnitud máxima prevista para la costa: extraordinaria",
            cita: { cita: "Se prevé una magnitud extraordinaria.", parrafo: "p3" },
            anterior: { ...comunicado, id: "enfen-2026-08", numero: 8, fecha_texto: "10 de abril de 2026" },
          },
        },
      ],
    },
  ],
  linea_tiempo: [{ ...comunicado, vigente: true, respaldo: false }],
  oficial_cercano: null,
  que_hacer: queHacer,
};

export const panorama: Panorama = {
  hallazgos: [
    { id: "reaccion", valor: "2 de 3", texto: "comunicados…", descriptivo: true, serie: [{ x: "a", y: 1 }, { x: "b", y: 2 }] },
    { id: "coinciden", valor: "50 %", texto: "de las notas…", descriptivo: false, serie: [{ x: "a", y: 0.5 }, { x: "b", y: 0.4 }] },
    { id: "anteriores", valor: "3", texto: "notas…", descriptivo: false, serie: [{ x: "a", y: 1 }, { x: "b", y: 2 }] },
  ],
  linea: {
    grupos: [
      { id: "coinciden", texto: "Coinciden" },
      { id: "difieren", texto: "Difieren" },
      { id: "sin_datos", texto: "Sin datos" },
    ],
    semanas: [
      { semana: "2026-01-05", coinciden: 1, difieren: 2, sin_datos: 3 },
      { semana: "2026-01-12", coinciden: 2, difieren: 0, sin_datos: 5 },
    ],
    comunicados: [{ id: "enfen-2026-01", numero: 1, desde: "2026-01-01", hasta: null, estado: "Vigilancia", magnitud: "débil" }],
  },
  magnitudes: {
    magnitudes: ["débil", "moderada", "fuerte", "extraordinaria"],
    grupos: [
      { id: "respaldada", texto: "Coincide" },
      { id: "desactualizada", texto: "Dato anterior" },
    ],
    escalon: [{ desde: "2026-01-01", hasta: null, magnitud: "débil", numero: 1 }],
    puntos: [
      { fecha: "2026-01-06", magnitud: "débil", grupo: "respaldada" },
      { fecha: "2026-01-09", magnitud: "fuerte", grupo: "desactualizada" },
    ],
  },
  reaccion: { comunicados: [{ fecha: "2026-01-15", numero: 1, veces: 1.6 }, { fecha: "2026-01-30", numero: 2, veces: 0.8 }] },
  temas: {
    categorias: ["Pesca y mar", "Otros temas"],
    hasta: "2026-11-09",
    meses: [
      { mes: "2026-01", "Pesca y mar": 2, "Otros temas": 1 },
      { mes: "2026-02", "Pesca y mar": 4, "Otros temas": 3 },
    ],
  },
  citas: {
    actores: ["ENFEN", "SENAMHI", "INDECI"],
    medios: [
      { medio: "andina", medio_texto: "Andina", notas: 10, ENFEN: 0.1, SENAMHI: 0.2, INDECI: 0.3 },
      { medio: "rpp", medio_texto: "RPP", notas: 5, ENFEN: 0.9, SENAMHI: 0.1, INDECI: 0.1 },
    ],
  },
  youtube: {
    disponible: true,
    por_region: false,
    nota: "La cercanía mide el tema.",
    tipos: [
      { id: "medio", texto: "Medios" },
      { id: "oficial", texto: "Instituciones oficiales" },
      { id: "otros", texto: "Otros canales" },
    ],
    corte: "2026-11-22",
    total: 3,
    puntos: [
      { tipo: "medio", mes: "2026-01", cercania: 0.5, tasa: 0.01 },
      { tipo: "otros", mes: "2026-02", cercania: 0.3, tasa: 0 },
      { tipo: "oficial", mes: "2026-03", cercania: 0.8, tasa: 0.02 },
    ],
    indicador_tasa: [
      { tipo: "medio", texto: "Medios", mediana: 0.0077, n: 390 },
      { tipo: "oficial", texto: "Instituciones oficiales", mediana: 0.0159, n: 48 },
      { tipo: "otros", texto: "Otros canales", mediana: 0.0123, n: 1166 },
    ],
    indicador_respuesta: { respuesta: "sí", texto: "Sí. …", rho: -0.1683, ic_inf: -0.2602, ic_sup: -0.0995, n: 968 },
  },
};
