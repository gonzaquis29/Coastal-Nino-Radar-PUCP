import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { GlosarioProvider, useGlosario } from "./componentes/Glosario";
import { Marca } from "./componentes/Marca";
import { SelectorTema } from "./componentes/SelectorTema";
import { useTema } from "./ganchos";
import Preguntar from "./pantallas/Preguntar";
import Verificar from "./pantallas/Verificar";
import { type Pantalla, vista } from "./registro/registro";
import { T } from "./textos";

// Los gráficos solo se descargan al abrir el Panorama o Metodología (D12, U4)
const Mapa = lazy(() => import("./pantallas/Mapa"));
const Panorama = lazy(() => import("./pantallas/Panorama"));
const Metodologia = lazy(() => import("./pantallas/Metodologia"));

const RUTAS: Record<string, Pantalla> = {
  "/": "verificar",
  "/mapa": "mapa",
  "/preguntar": "preguntar",
  "/panorama": "panorama",
  "/metodologia": "metodologia",
};
const TITULOS: Record<Pantalla, string> = {
  verificar: T.verificar.titulo,
  mapa: T.mapa.titulo,
  preguntar: T.preguntar.titulo,
  panorama: T.panorama.titulo,
  metodologia: T.metodologia.titulo,
};

const pantallaDe = (ruta: string): Pantalla => RUTAS[ruta.replace(/\/+$/, "") || "/"] ?? "verificar";

export function irA(ruta: string) {
  if (ruta === window.location.pathname) return;
  window.history.pushState({}, "", ruta);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

/** Un enlace interno que no recarga la página. */
export function Enlace(props: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  const { href, onClick, ...resto } = props;
  return (
    <a
      href={href}
      onClick={(e) => {
        onClick?.(e);
        if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
        e.preventDefault();
        irA(href);
      }}
      {...resto}
    />
  );
}

/** El enlace del menú que abre el glosario en «¿Qué es el ENFEN?». */
function BotonGlosario() {
  const abrir = useGlosario();
  return (
    <button type="button" className="nav__glosario" aria-haspopup="dialog" onClick={() => abrir("enfen")}>
      {T.comun.nav_glosario}
    </button>
  );
}

export default function App() {
  const [pantalla, setPantalla] = useState<Pantalla>(() => pantallaDe(window.location.pathname));
  const [tema, setTema] = useTema();
  const principal = useRef<HTMLElement>(null);
  const primera = useRef(true);

  const alCambiar = useCallback(() => setPantalla(pantallaDe(window.location.pathname)), []);
  useEffect(() => {
    window.addEventListener("popstate", alCambiar);
    return () => window.removeEventListener("popstate", alCambiar);
  }, [alCambiar]);

  useEffect(() => {
    vista(pantalla);
    document.title = pantalla === "verificar" ? T.comun.marca : `${TITULOS[pantalla]} · ${T.comun.marca}`;
    if (primera.current) {
      primera.current = false;
      return;
    }
    window.scrollTo(0, 0);
    principal.current?.focus(); // quien usa lector de pantalla oye la pantalla nueva
  }, [pantalla]);

  const nav: [string, Pantalla, string][] = [
    ["/", "verificar", T.comun.nav_verificar],
    ["/mapa", "mapa", T.comun.nav_mapa],
    ["/preguntar", "preguntar", T.comun.nav_preguntar],
    ["/panorama", "panorama", T.comun.nav_panorama],
  ];

  return (
    <GlosarioProvider>
      <a className="saltar" href="#contenido">
        {T.comun.saltar}
      </a>
      <header className="cabecera">
        <div className="cabecera__fila">
          <Enlace href="/" className="marca" aria-label={T.comun.marca}>
            <Marca />
            <span className="marca__texto">{T.comun.marca}</span>
            <span className="marca__corta" aria-hidden="true">
              {T.comun.marca_corta}
            </span>
          </Enlace>
          <BotonGlosario />
          <nav className="nav" aria-label={T.comun.nav_principal}>
            {nav.map(([ruta, id, texto]) => (
              <Enlace key={id} href={ruta} aria-current={pantalla === id ? "page" : undefined}>
                {texto}
              </Enlace>
            ))}
          </nav>
          <SelectorTema tema={tema} cambiar={setTema} />
        </div>
      </header>
      <main id="contenido" ref={principal} tabIndex={-1} aria-label={TITULOS[pantalla]}>
        {pantalla === "verificar" && <Verificar />}
        {pantalla === "preguntar" && <Preguntar />}
        <Suspense fallback={<p className="cargando envoltura">{T.comun.cargando}</p>}>
          {pantalla === "mapa" && <Mapa />}
          {pantalla === "panorama" && <Panorama />}
          {pantalla === "metodologia" && <Metodologia />}
        </Suspense>
      </main>
      <footer className="pie" hidden={pantalla === "mapa"}>
        <div className="pie__fila">
          <p>{T.comun.pie}</p>
          <Enlace href="/metodologia" aria-current={pantalla === "metodologia" ? "page" : undefined}>
            {T.comun.nav_metodologia}
          </Enlace>
        </div>
      </footer>
    </GlosarioProvider>
  );
}
