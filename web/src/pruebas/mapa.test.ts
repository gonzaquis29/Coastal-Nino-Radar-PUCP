// Cálculos del mapa con datos inventados, sin MapLibre ni la API.
import { describe, expect, it } from "vitest";
import type { AvisoMapa, DatosMapa } from "../api/tipos";
import { avisosDelDia, buscarLugares, consejos, cuantosDias, diaMas, frase, type Lugar, macroregionDe, nivelEn, sismoFuerte, titulo } from "../mapa/datos";

const aviso = (numero: number, inicio: string, fin: string, nivel: AvisoMapa["nivel"] = "rojo"): AvisoMapa => ({
  numero, peligro: "lluvias", titulo: "LLUVIAS", texto: "", nivel, emision: "2026-11-22", inicio, fin, url: "https://ejemplo",
});
const datos: DatosMapa = {
  disponible: true,
  ahora: "2026-11-24T15:00:00",
  actualizado: "2026-11-24T14:00:00",
  avisos: [
    aviso(1, "2026-11-24T00:00:00", "2026-11-26T23:59:00", "amarillo"),
    aviso(2, "2026-11-24T00:00:00", "2026-11-24T12:00:00"),
    aviso(3, "2026-11-24T00:00:00", "2026-11-24T23:59:00"),
  ],
  notas: [{ titulo: "x", fecha: "2026-11-23", url: "https://n", peligro: "lluvias", departamentos: ["PIURA"], recomendaciones: ["Refuerza tu techo.", "Refuerza tu techo.", "Evita los ríos."] }],
  sismos: [
    { id: "a", magnitud: 6.7, momento: "2026-11-20T19:09:00", lugar: "", lat: 0, lon: 0, profundidad: 1, url: "" },
    { id: "b", magnitud: 7.5, momento: "2026-11-01T00:00:00", lugar: "", lat: 0, lon: 0, profundidad: 1, url: "" },
  ],
  zonas: { "1": { "2026-11-24": { inicio: "2026-11-24T00:00:00", fin: "2026-11-24T23:59:59", distritos: "0243" } } },
  macroregiones: { PIURA: "costa_norte", CUSCO: "otras" },
  fuentes: {},
};
const lugares: Lugar[] = [["PIURA", "PIURA", "CASTILLA", -5, -80], ["LIMA", "LIMA", "SAN JUAN DE MIRAFLORES", -12, -77], ["LIMA", "LIMA", "MIRAFLORES", -12, -77]];

describe("mapa", () => {
  it("suma días sin depender de la zona horaria", () => expect(diaMas("2026-11-30T23:00:00", 1)).toBe("2026-12-01"));
  it("no muestra los avisos ya vencidos hoy y ordena por nivel", () => {
    expect(avisosDelDia(datos, 0, "todo").map((a) => a.numero)).toEqual([3, 1]);
    expect(avisosDelDia(datos, 1, "todo").map((a) => a.numero)).toEqual([1]);
    expect(avisosDelDia(datos, 0, "calor")).toEqual([]);
  });
  it("cuenta los días con avisos publicados", () => expect(cuantosDias(datos)).toBe(3));
  it("da el nivel de un distrito y el más alto de un departamento", () => {
    expect(nivelEn(datos, datos.avisos[0], 0, [1])).toBe(2);
    expect(nivelEn(datos, datos.avisos[0], 0, [0, 1, 2])).toBe(4);
    expect(nivelEn(datos, datos.avisos[0], 1, [2])).toBe(0);
    expect(nivelEn(datos, datos.avisos[2], 0, [2])).toBe(0);
  });
  it("destaca solo sismos fuertes de la última semana", () => expect(sismoFuerte(datos, datos.sismos)?.id).toBe("a"));
  it("busca sin tildes y pone primero el nombre exacto", () => {
    expect(buscarLugares("miraflores", lugares).map((o) => o.indice)).toEqual([2, 1]);
    expect(buscarLugares("piura", lugares)[0]).toEqual({ dep: "PIURA", indice: null });
    expect(buscarLugares("x", lugares)).toEqual([]);
  });
  it("no repite consejos y respeta el departamento", () => {
    expect(consejos(datos, "PIURA", ["lluvias"]).map((c) => c.texto)).toEqual(["Refuerza tu techo.", "Evita los ríos."]);
    expect(consejos(datos, "LIMA", ["lluvias"])).toEqual([]);
  });
  it("solo enlaza con El Niño las macro-regiones que sigue la app", () => {
    expect(macroregionDe(datos, "PIURA")).toBe("costa_norte");
    expect(macroregionDe(datos, "CUSCO")).toBeNull();
  });
  it("escribe los nombres como se leen", () => {
    expect(titulo("SAN JUAN DE MIRAFLORES")).toBe("San Juan de Miraflores");
    expect(titulo("ANCASH")).toBe("Áncash");
    expect(frase("LLUVIAS EN LA COSTA (EXTENSIÓN DEL AVISO 4)")).toBe("Lluvias en la costa");
  });
});
