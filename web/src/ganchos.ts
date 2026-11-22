import { useCallback, useEffect, useRef, useState } from "react";
import { ErrorApi, type TipoError } from "./api/cliente";
import type { Macroregion } from "./api/tipos";

/** localStorage puede fallar (ventana privada, permisos): nunca rompe la página. */
export const guardado = {
  leer(clave: string): string | null {
    try {
      return window.localStorage.getItem(clave);
    } catch {
      return null;
    }
  },
  escribir(clave: string, valor: string | null) {
    try {
      if (valor === null) window.localStorage.removeItem(clave);
      else window.localStorage.setItem(clave, valor);
    } catch {
      /* sin almacenamiento: la preferencia dura lo que la pestaña */
    }
  },
};

const ZONAS: Macroregion[] = ["costa_norte", "costa_centro", "lima"];

/** La macro-región se pide una vez y se recuerda en el navegador (D3). */
export function useZona(): [Macroregion | null, (z: Macroregion) => void] {
  const [zona, setZona] = useState<Macroregion | null>(() => {
    const z = guardado.leer("radar.zona");
    return ZONAS.includes(z as Macroregion) ? (z as Macroregion) : null;
  });
  const cambiar = useCallback((z: Macroregion) => {
    guardado.escribir("radar.zona", z);
    setZona(z);
  }, []);
  return [zona, cambiar];
}

export type Tema = "sistema" | "claro" | "oscuro";

export function useTema(): [Tema, (t: Tema) => void] {
  const [tema, setTema] = useState<Tema>(() => {
    const t = guardado.leer("radar.tema");
    return t === "claro" || t === "oscuro" ? t : "sistema";
  });
  useEffect(() => {
    const raiz = document.documentElement;
    if (tema === "sistema") raiz.removeAttribute("data-theme");
    else raiz.setAttribute("data-theme", tema === "claro" ? "light" : "dark");
    guardado.escribir("radar.tema", tema === "sistema" ? null : tema);
  }, [tema]);
  return [tema, setTema];
}

export interface Estado<T> {
  datos: T | null;
  error: TipoError | null;
  cargando: boolean;
}

/**
 * Una consulta a la API que se puede repetir: la nueva cancela a la anterior, y mientras carga se conserva el
 * resultado previo (sin saltos de diseño).
 */
export function useConsulta<T, A extends unknown[]>(funcion: (senal: AbortSignal, ...args: A) => Promise<T>) {
  const [estado, setEstado] = useState<Estado<T>>({ datos: null, error: null, cargando: false });
  const actual = useRef<AbortController | null>(null);
  const funcionRef = useRef(funcion);
  funcionRef.current = funcion;

  const ejecutar = useCallback(async (...args: A): Promise<T | null> => {
    actual.current?.abort();
    const control = new AbortController();
    actual.current = control;
    setEstado((e) => ({ ...e, cargando: true, error: null }));
    try {
      const datos = await funcionRef.current(control.signal, ...args);
      if (control.signal.aborted) return null;
      setEstado({ datos, error: null, cargando: false });
      return datos;
    } catch (e) {
      if (control.signal.aborted) return null;
      setEstado((s) => ({ ...s, cargando: false, error: e instanceof ErrorApi ? e.tipo : "error" }));
      return null;
    }
  }, []);

  useEffect(() => () => actual.current?.abort(), []);
  const reiniciar = useCallback(() => {
    actual.current?.abort();
    setEstado({ datos: null, error: null, cargando: false });
  }, []);
  return { ...estado, ejecutar, reiniciar, setDatos: (datos: T) => setEstado((e) => ({ ...e, datos })) };
}

/** Ancho disponible de un contenedor, para que los gráficos se ajusten sin desbordar. */
export function useAncho<E extends HTMLElement>(inicial = 640): [React.RefObject<E | null>, number] {
  const ref = useRef<E | null>(null);
  const [ancho, setAncho] = useState(inicial);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const obs = new ResizeObserver(([e]) => setAncho(Math.max(280, Math.floor(e.contentRect.width))));
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return [ref, ancho];
}

export const esCelular = () =>
  typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(max-width: 767px)").matches
    : false;
