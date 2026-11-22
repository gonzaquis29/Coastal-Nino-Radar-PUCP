"""API de la app (docs/app/definicion.md, sección 4). Sirve también la interfaz ya construida (web/dist).

Arranque: python -m radar.app (carga el semáforo y el Panorama una sola vez; las rutas no piden nada a internet).
"""

import contextlib
import datetime as dt
import logging
import threading
import time

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from radar import config
from radar.app import esquemas, eventos, metodologia, servicio
from radar.app import textos as tx

registro = logging.getLogger(__name__)
DIST = config.DIR_WEB / "dist"
# El semáforo y el agente no garantizan ser seguros entre hilos: se atiende una consulta con modelos a la vez
CANDADO_MODELOS = threading.Lock()
ESTADO = {"listo": False, "segundos_arranque": None}
# La interfaz no carga nada de fuera: solo sus propios archivos y llamadas a esta misma API
CABECERAS = {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self';"
    " connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
    "X-Frame-Options": "DENY",
}
RUTAS_DOCUMENTACION = ("/api/docs", "/api/openapi.json")  # Swagger carga sus archivos de fuera: sin la CSP


def hoy():
    return dt.date.today().isoformat()


@contextlib.asynccontextmanager
async def ciclo(_app):
    inicio = time.perf_counter()
    servicio.servicio()
    servicio.panorama()
    servicio.servicio().verificar("El Niño costero", hoy(), "lima")  # carga los modelos que se usan tarde
    ESTADO.update(listo=True, segundos_arranque=round(time.perf_counter() - inicio, 1))
    registro.info("API lista en %s s", ESTADO["segundos_arranque"])
    yield


def crear(cargar=True):
    app = FastAPI(title="Radar Niño Costero", lifespan=ciclo if cargar else None, docs_url="/api/docs",
                  openapi_url="/api/openapi.json", redoc_url=None)  # fmt: skip
    topes = eventos.Topes()
    app.add_middleware(GZipMiddleware, minimum_size=1000)  # la interfaz y el Panorama viajan comprimidos (U4)

    @app.middleware("http")
    async def cabeceras(request: Request, siguiente):
        respuesta = await siguiente(request)
        for clave, valor in CABECERAS.items():
            if clave == "Content-Security-Policy" and request.url.path.startswith(RUTAS_DOCUMENTACION):
                continue
            respuesta.headers.setdefault(clave, valor)
        if request.url.path.startswith("/api/"):
            respuesta.headers.setdefault("Cache-Control", "no-store")
        elif request.url.path.startswith("/assets/"):
            respuesta.headers["Cache-Control"] = "public, max-age=31536000, immutable"  # nombres con hash
        return respuesta

    @app.get("/api/salud")
    def salud():
        return ESTADO

    @app.get("/api/estado")
    def estado(macroregion: esquemas.Macroregion = "lima",
               fecha: str | None = Query(default=None, pattern=esquemas.FECHA)):  # fmt: skip
        return servicio.servicio().estado(fecha or hoy(), macroregion)

    @app.post("/api/verificar")
    def verificar(pedido: esquemas.PedidoVerificar):
        with CANDADO_MODELOS:
            return servicio.servicio().verificar(pedido.texto, pedido.fecha or hoy(), pedido.macroregion,
                                                 pedido.interes)  # fmt: skip

    @app.post("/api/preguntar")
    def preguntar(pedido: esquemas.PedidoPreguntar):
        with CANDADO_MODELOS:
            return servicio.servicio().preguntar(pedido.consulta, pedido.fecha or hoy(), pedido.macroregion,
                                                 pedido.interes)  # fmt: skip

    @app.get("/api/panorama/{seccion}")
    def panorama(seccion: esquemas.Seccion, desde: str | None = Query(default=None, pattern=esquemas.FECHA),
                 hasta: str | None = Query(default=None, pattern=esquemas.FECHA),
                 macroregion: esquemas.Macroregion | None = None):  # fmt: skip
        p = servicio.panorama()
        if seccion in esquemas.SECCIONES_CON_FILTRO:
            return getattr(p, seccion)(desde=desde, hasta=hasta, macroregion=macroregion)
        return getattr(p, seccion)()

    @app.get("/api/metodologia")
    def ver_metodologia():
        return metodologia.metodologia()

    @app.get("/api/opciones")
    def opciones():
        return {"macroregiones": [{"id": k, "texto": v} for k, v in tx.MACROREGIONES.items()],
                "intereses": [{"id": k, "texto": v} for k, v in tx.INTERESES.items()]}  # fmt: skip

    @app.post("/api/eventos", status_code=204)
    def registrar(lote: eventos.Lote):
        if not topes.permite(lote.sesion):
            raise HTTPException(429, "Demasiados eventos")
        if eventos.lleno():
            registro.warning("El registro de uso llegó a su tamaño máximo: no se guardan más eventos")
            return Response(status_code=204)
        eventos.registrar(lote)

    @app.get("/api/{resto:path}", include_in_schema=False)
    def no_existe(resto: str):
        raise HTTPException(404, "Ruta no encontrada")

    if (DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{resto:path}", include_in_schema=False)
    def interfaz(resto: str):
        archivo = (DIST / resto).resolve()
        if resto and archivo.is_file() and archivo.is_relative_to(DIST.resolve()):
            return FileResponse(archivo)
        if (DIST / "index.html").exists():
            return FileResponse(DIST / "index.html")  # las rutas de la interfaz las resuelve React
        raise HTTPException(503, "Falta construir la interfaz: cd web && npm run build")

    return app


app = crear()
