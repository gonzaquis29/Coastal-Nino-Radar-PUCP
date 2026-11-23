// Pruebas de la interfaz sin la API: U2 y U6 sobre lo que se dibuja, P10 y P12 sobre los gráficos y el registro (P5).
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { aCsv } from "../graficos/base";
import { posicion } from "../componentes/Medidor";
import { Resultado } from "../componentes/Resultado";
import generado from "../generado/textos.json";
import { _cola, _reiniciar, registrar, vista } from "../registro/registro";
import { cercania, conDatos, panorama } from "./datos";

const JERGA = ["capa", "distancia", "coseno", "umbral", "auc", "nli", "embedding", "origen", "percentil"];
const PROMESAS = ["correcto", "verdadero", "falso", "verdad"];
const COLORES_DE_ESTADO = ["--bien", "--alerta", "--mal", "coincide", "revisar", "no_coincide"];

const palabras = (t: string) => new Set(t.toLowerCase().match(/[a-záéíóúüñ]+/g) ?? []);

beforeEach(() => {
  // jsdom no trae ResizeObserver ni matchMedia
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  vi.stubGlobal("matchMedia", () => ({ matches: false }));
  vi.stubGlobal("fetch", vi.fn(async (ruta: string) => {
    const s = /\/api\/panorama\/(\w+)/.exec(ruta)?.[1] as keyof typeof panorama | undefined;
    return new Response(JSON.stringify(s ? panorama[s] : {}), { status: 200 });
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  _reiniciar();
});

describe("U2 y U6 en Verificar", () => {
  it("los textos del ciudadano no tienen jerga ni promesas", () => {
    const textos = [...Object.values(generado.comun), ...Object.values(generado.verificar), ...Object.values(generado.preguntar)];
    expect(textos.filter((t) => JERGA.some((j) => palabras(t).has(j)))).toEqual([]);
    expect(textos.filter((t) => PROMESAS.some((j) => palabras(t).has(j)))).toEqual([]);
  });

  it("sin datos no hay color de semáforo, ícono de veredicto ni promesas (U6)", () => {
    const { container } = render(<Resultado r={cercania} />);
    const html = container.innerHTML;
    for (const c of COLORES_DE_ESTADO) expect(html).not.toContain(c);
    expect(container.querySelector(".icono-estado")).toBeNull();
    expect(PROMESAS.some((p) => palabras(container.textContent ?? "").has(p))).toBe(false);
    expect(screen.getByRole("meter").getAttribute("aria-valuetext")).toBe("Alta");
  });

  it("fuera del tema: solo la explicación, sin medidor, color ni promesas (sección 9)", () => {
    const r = { ...cercania, tipo: "fuera_de_tema" as const, nivel: null, titulo: "Este texto no parece hablar de El Niño, del mar ni del clima.",
      resumen: "Si sí habla de eso, pega la nota completa.", aviso: null, oficial_cercano: null };
    const { container } = render(<Resultado r={r} />);
    expect(container.querySelector("[data-tipo=fuera_de_tema]")).not.toBeNull();
    expect(screen.queryByRole("meter")).toBeNull();
    for (const c of COLORES_DE_ESTADO) expect(container.innerHTML).not.toContain(c);
    expect(container.textContent).toContain("pega la nota completa");
  });

  it("con datos: veredicto con ícono y la comparación se abre a pedido (D4)", () => {
    const { container } = render(<Resultado r={conDatos} />);
    expect(container.querySelector(".resultado--revisar .icono-estado--revisar")?.textContent).toBe("!");
    const detalle = container.querySelector(".detalle") as HTMLElement;
    expect(detalle.hidden).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: /Ver por qué/ }));
    expect(detalle.hidden).toBe(false);
    expect(container.querySelector("mark")?.textContent).toBe("débil");
    expect(detalle.textContent).toContain("Comunicado N.° 8");
    expect(_cola().map((e) => e.evento)).toEqual(["ver_por_que"]);
  });

  it("el medidor ubica cada banda en su tercio", () => {
    expect(posicion(0.2, 0.3, 0.41)).toBeLessThan(1 / 3);
    const media = posicion(0.35, 0.3, 0.41);
    expect(media).toBeGreaterThanOrEqual(1 / 3);
    expect(media).toBeLessThan(2 / 3);
    expect(posicion(0.9, 0.3, 0.41)).toBeGreaterThanOrEqual(2 / 3);
    expect(posicion(5, 0.3, 0.41)).toBeLessThanOrEqual(1);
  });
});

describe("Panorama (P10 y P12)", () => {
  async function abrir() {
    const { default: Panorama } = await import("../pantallas/Panorama");
    const r = render(<Panorama />);
    await waitFor(() => expect(r.container.querySelectorAll("section.grafico").length).toBe(6));
    return r;
  }

  it("cada gráfico tiene Cómo leer, tabla, descarga y emergente; Descriptivo solo en C", async () => {
    const { container } = await abrir();
    const graficos = [...container.querySelectorAll<HTMLElement>("section.grafico")];
    expect(graficos.map((g) => g.dataset.seccion)).toEqual(["linea", "magnitudes", "reaccion", "temas", "citas", "youtube"]);
    for (const g of graficos) {
      expect(g.querySelector("[data-como-leer]")).not.toBeNull();
      expect(g.querySelector("[data-emergente]")).not.toBeNull();
      expect(g.querySelector("[data-descargar]")).not.toBeNull();
      fireEvent.click(within(g).getByRole("button", { name: "Ver tabla" }));
      expect(g.querySelector("table")).not.toBeNull();
    }
    const descriptivos = graficos.filter((g) => g.querySelector("[data-descriptivo]")).map((g) => g.dataset.seccion);
    expect(descriptivos).toEqual(["reaccion"]);
  });

  it("E en orden alfabético y F con los tipos en orden fijo, sin nombres de canal (P12)", async () => {
    const { container } = await abrir();
    const medios = [...container.querySelectorAll<HTMLElement>("[data-medio]")].map((m) => m.dataset.medio!);
    expect(medios).toEqual([...medios].sort((a, b) => a.localeCompare(b, "es")));
    const tipos = [...container.querySelectorAll<HTMLElement>("[data-indicador=tasa] [data-tipo]")].map((t) => t.dataset.tipo);
    expect(tipos).toEqual(["medio", "oficial", "otros"]);
  });

  it("la tabla de B no tiene columna de medio (P12)", async () => {
    const { container } = await abrir();
    const b = container.querySelector<HTMLElement>("[data-seccion=magnitudes]")!;
    fireEvent.click(within(b).getByRole("button", { name: "Ver tabla" }));
    const columnas = [...b.querySelectorAll("th")].map((th) => th.textContent);
    expect(columnas).toEqual(["Fecha", "Magnitud", "Grupo"]);
  });

  it("el emergente de A aparece al pasar el cursor", async () => {
    const { container } = await abrir();
    const a = container.querySelector<HTMLElement>("[data-seccion=linea]")!;
    fireEvent.pointerMove(a.querySelector(".zona-toque")!, { clientX: 50, clientY: 50 });
    expect(a.querySelector(".emergente")?.textContent).toContain("Coinciden: 1");
  });
});

describe("CSV y registro de uso", () => {
  it("el CSV lleva BOM y escapa las comillas", () => {
    const csv = aCsv({ columnas: [{ id: "a", texto: "A" }], filas: [{ a: 'dijo "hola"' }] });
    expect(csv).toBe('﻿"A"\r\n"dijo ""hola"""\r\n');
  });

  it("los eventos no llevan el texto consultado (P5)", () => {
    vista("verificar");
    registrar({ evento: "verificar", tipo_resultado: "cercania", resultado: "cercano", macroregion: "lima", palabras: 12 });
    vista("panorama");
    const cola = _cola();
    expect(cola.map((e) => e.evento)).toEqual(["vista", "verificar", "vista"]);
    const permitidas = new Set(["evento", "pantalla", "anterior", "segundos", "tipo_resultado", "resultado", "macroregion",
      "palabras", "interes", "tipo", "posicion", "herramienta", "fuera_alcance", "seccion", "filtro"]);
    for (const e of cola) for (const k of Object.keys(e)) expect(permitidas.has(k)).toBe(true);
    expect(cola[2]).toMatchObject({ pantalla: "panorama", anterior: "verificar" });
  });
});

describe("Citas", () => {
  it("oculta la viñeta del PDF pero no cambia el resto del texto oficial", async () => {
    const { Cita } = await import("../componentes/Cita");
    const { container } = render(<Cita texto={`${String.fromCharCode(0xf0b7)} La anchoveta continuaría cerca.`} fuente="ENFEN" />);
    expect(container.querySelector("p")?.textContent).toBe("La anchoveta continuaría cerca.");
  });

  it("no enlaza direcciones que no son https", async () => {
    const { enlaceSeguro } = await import("../api/cliente");
    expect(enlaceSeguro("javascript:alert(1)")).toBeNull();
    expect(enlaceSeguro("http://ejemplo.pe")).toBeNull();
    expect(enlaceSeguro("https://enfen.imarpe.gob.pe/x")).toBe("https://enfen.imarpe.gob.pe/x");
  });
});
