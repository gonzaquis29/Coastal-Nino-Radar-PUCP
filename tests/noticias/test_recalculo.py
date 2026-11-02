"""Recálculo reanudable (B1): cortes en cada escritura posible, con la línea a medias, y en el reemplazo de archivos.
Medio falso y entradas sintéticas de WordPress; ninguna nota real."""

import os
import shutil
import threading

import pytest
import requests

from radar import config
from radar.comun import archivos
from radar.comun.archivos import escribir_csv, leer_csv
from radar.noticias import esquemas, recalculo
from radar.noticias.medios import NoExiste, filas_de_nota
from radar.noticias.nota import LISTA_SIN_CERRAR, leer_api, leer_html

RELLENO = " ".join(["palabra"] * 60)
ANTES = "2026-10-26T10:00:00-05:00"


def resumen(i):
    """Solo la nota 3 trae en el resumen el titular de otra nota (como El Tiempo antes del corte)."""
    return f"Resumen {i}." + (" PUEDES LEER ► El Niño sería fuerte" if i == 3 else "")


def entrada(i, cuerpo):
    contenido = f"<p>{cuerpo} {RELLENO}</p><p><a href='https://www.gob.pe/{i}'>x</a></p>"
    if i == 4:  # un titular ajeno sin rótulo: con la extracción de antes daba magnitud
        contenido += "<p><a href='https://rpp.pe/peru/otra-noticia-9'>El Niño costero de intensidad fuerte</a></p>"
    return {"id": i, "link": f"https://rpp.pe/peru/x-noticia-{i}", "date_gmt": "2026-10-20T15:00:00",
            "modified_gmt": "2026-10-20T15:00:00", "title": {"rendered": f"Titular {i}"},
            "excerpt": {"rendered": f"<p>{resumen(i)}</p>"}, "content": {"rendered": contenido}}  # fmt: skip


CUERPOS = {
    "1": "El Niño costero de intensidad fuerte llegaría en verano.",
    "2": "Lluvias de fuerte intensidad en Piura por El Niño.",
    "3": "La feria del libro abre sus puertas.",
    "4": "Otra nota sin El Niño.",
}
RED = "5"  # falla por red en cada ejecución
NO_EXISTE = "6"


class MedioFalso:
    nombre = "rpp"

    def __init__(self, cliente, parar=None):
        self.parar = parar or threading.Event()
        self.lista = {
            i: {"medio": "rpp", "id": i, "url": f"https://rpp.pe/peru/x-noticia-{i}", "titulo": f"Titular {i}",
                "seccion": "peru", "fecha_lista": "", "via": "archivo", "http": 200}
            for i in [*CUERPOS, RED, NO_EXISTE]
        }  # fmt: skip

    def descargar(self, filas):
        for fila in filas:
            i = fila["id"]
            if i == RED:
                yield fila, requests.ConnectionError("sin red")
            elif i == NO_EXISTE:
                yield fila, NoExiste("HTTP 404")
            else:
                yield fila, leer_api(entrada(int(i), CUERPOS[i]))


@pytest.fixture
def raiz(tmp_path, monkeypatch):
    """Archivos de antes: las filas como las habría dejado el código anterior (otros valores de rasgos)."""
    monkeypatch.setattr(config, "DIR_RAW_NOTICIAS", tmp_path / "raw")
    monkeypatch.setattr(recalculo, "MEDIOS", {"rpp": MedioFalso})
    monkeypatch.setattr(recalculo, "Cliente", lambda **_: None)
    monkeypatch.setattr(recalculo, "PISO_DE_GENERACION", {})  # archivos de antes de cualquier recálculo aplicado
    medio = MedioFalso(None)
    notas, enlaces = [], []
    for i in [*CUERPOS, RED, NO_EXISTE]:
        campos = leer_api(entrada(int(i), CUERPOS.get(i, "Texto de El Niño.")))
        nota, links = filas_de_nota("rpp", medio.lista[i], campos, "candidata")
        # lo que daba el código anterior: la regla laxa ("lluvias de fuerte intensidad" contaba) y el resumen entero
        antes = recalculo.magnitudes_regla_anterior(f"{resumen(int(i))} {campos['cuerpo_con_ajenos']}")
        nota.update(recolectado=ANTES, magnitudes=antes, resumen=resumen(int(i)), menciona_nino=True,
                    sobre_nino=recalculo._sobre(nota["titular"], resumen(int(i)), campos["cuerpo"]))  # fmt: skip
        notas.append(nota)
        enlaces += links + [{**links[0], "url": "https://rpp.pe/recomendado"}]
    escribir_csv(tmp_path / "raw" / "rpp" / "notas.csv", esquemas.NOTAS, notas)
    escribir_csv(tmp_path / "raw" / "rpp" / "enlaces.csv", esquemas.ENLACES, enlaces)
    return tmp_path


def correr(ejecucion="e1"):
    return recalculo.Recalculo("rpp", threading.Event(), ejecucion, recalculo.FASE_RESTO).correr()


def contenido(raiz):
    """Lo recalculado, sin la hora del recálculo (lo único que cambia entre corridas)."""
    d = raiz / "raw" / "rpp" / "recalculo"
    cambios = [{k: v for k, v in f.items() if k != "recalculado"} for f in leer_csv(d / "cambios.csv")]
    notas = [{k: v for k, v in f.items() if k != "recalculado"} for f in leer_csv(d / "notas.csv")]
    return notas, leer_csv(d / "enlaces.csv"), cambios


class Corte(BaseException):
    """Como un apagón: nada lo atrapa."""


def test_cortes_en_cada_escritura_dan_lo_mismo_que_sin_cortes(raiz, monkeypatch):
    for ejecucion in ("e1", "e2", "e3"):  # la nota con error de red queda sin releer a la 3.ª ejecución
        correr(ejecucion)
    referencia = contenido(raiz)
    escrituras = sum(1 for _ in leer_csv(raiz / "raw/rpp/recalculo/notas.csv")) * 3
    shutil.rmtree(raiz / "raw/rpp/recalculo")
    original = archivos.anexar_csv
    for corte in range(escrituras):
        shutil.rmtree(raiz / "raw/rpp/recalculo", ignore_errors=True)
        llamadas = {"n": 0}

        def anexar_con_corte(ruta, columnas, filas, corte=corte, llamadas=llamadas):
            if llamadas["n"] == corte:
                original(ruta, columnas, filas)
                datos = ruta.read_bytes()
                ruta.write_bytes(datos[: len(datos) - 7])  # la última línea queda a medias
                raise Corte()
            llamadas["n"] += 1
            original(ruta, columnas, filas)

        monkeypatch.setattr(recalculo, "anexar_csv", anexar_con_corte)
        with pytest.raises(Corte):
            for ejecucion in ("e1", "e2", "e3"):
                correr(ejecucion)
        monkeypatch.setattr(recalculo, "anexar_csv", original)
        for ejecucion in ("e1", "e2", "e3"):
            correr(ejecucion)
        assert contenido(raiz) == referencia, f"corte en la escritura {corte}"


def test_causas_y_notas_sin_releer(raiz):
    for ejecucion in ("e1", "e2"):
        correr(ejecucion)
    cambios = {c["id"]: c for c in leer_csv(raiz / "raw/rpp/recalculo/cambios.csv")}
    assert RED not in cambios  # dos ejecuciones con error de red: sigue pendiente
    correr("e3")
    cambios = {c["id"]: c for c in leer_csv(raiz / "raw/rpp/recalculo/cambios.csv")}
    assert cambios[RED]["estado"] == "sin_releer" and "red en 3" in cambios[RED]["motivo"]
    assert cambios[NO_EXISTE]["estado"] == "sin_releer"
    # nota 2: "lluvias de fuerte intensidad" con la regla anterior era magnitud; ahora no
    assert cambios["2"]["magnitudes_ahora"] == "" and "regla" in cambios["2"]["causa_magnitudes"]
    # nota 3: era "sobre El Niño" por el titular ajeno del resumen
    assert cambios["3"]["sobre_ahora"] == "0" and cambios["3"]["causa_sobre"] == "resumen"
    assert cambios["3"]["resumen_cambia"] == "1"
    # nota 4: la magnitud venía del titular ajeno
    assert cambios["4"]["magnitudes_antes"] == "fuerte" and cambios["4"]["causa_magnitudes"] == "ajenos"
    nuevas = {n["id"]: n for n in leer_csv(raiz / "raw/rpp/recalculo/notas.csv")}
    viejas = {n["id"]: n for n in leer_csv(raiz / "raw/rpp/notas.csv")}
    assert nuevas[NO_EXISTE] == viejas[NO_EXISTE]  # se conserva la fila anterior
    assert nuevas["1"]["recolectado"] == ANTES and nuevas["1"]["magnitudes"] == "fuerte"


def test_aplicar_cortado_a_mitad_se_termina_y_conserva_lo_anterior(raiz, monkeypatch):
    for ejecucion in ("e1", "e2", "e3"):
        correr(ejecucion)
    viejas = (raiz / "raw/rpp/notas.csv").read_bytes()
    reemplazar = os.replace
    llamadas = {"n": 0}

    def reemplazo_con_corte(origen, destino):
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            raise Corte()
        reemplazar(origen, destino)

    monkeypatch.setattr(recalculo.os, "replace", reemplazo_con_corte)
    with pytest.raises(Corte):
        recalculo._cambiar("rpp")
    monkeypatch.setattr(recalculo.os, "replace", reemplazar)
    recalculo._cambiar("rpp")
    assert (raiz / "raw/rpp/notas.anterior.csv").read_bytes() == viejas
    ids_antes = [n["id"] for n in leer_csv(raiz / "raw/rpp/notas.anterior.csv")]
    assert [n["id"] for n in leer_csv(raiz / "raw/rpp/notas.csv")] == ids_antes  # mismo orden
    assert all(e["url"] != "https://rpp.pe/recomendado" or e["id"] in (NO_EXISTE, RED)
               for e in leer_csv(raiz / "raw/rpp/enlaces.csv"))  # fmt: skip
    recalculo._cambiar("rpp")  # ya hecho: no hace nada
    assert (raiz / "raw/rpp/notas.anterior.csv").read_bytes() == viejas


def test_regla_anterior_reproducida():
    assert recalculo.magnitudes_regla_anterior("Lluvias de fuerte intensidad por El Niño.") == ["fuerte"]
    assert recalculo.magnitudes_regla_anterior("El Niño fuerte llegará.") == []
    assert recalculo.generacion("2026-10-28T18:09:52-05:00") == "capa1"
    assert recalculo.generacion("2026-10-27T09:00:00-05:00") == "anterior"


def test_sin_filas_de_control_el_instrumento_no_pasa_y_se_releen_primero(raiz):
    correr()
    m1b = next(f for f in recalculo.informe()[0] if f["criterio"].startswith("M1b"))
    assert not m1b["pasa"]  # todas las filas son de la generación "anterior": no hay con qué controlar
    viejas = leer_csv(raiz / "raw/rpp/notas.csv")
    viejas[-1]["recolectado"] = "2026-10-30T09:00:00-05:00"  # la última, de la generación de control
    escribir_csv(raiz / "raw/rpp/notas.csv", esquemas.NOTAS, viejas)
    shutil.rmtree(raiz / "raw/rpp/recalculo")
    pendientes, _ = recalculo.Recalculo("rpp", threading.Event(), "e1", recalculo.FASE_RESTO).pendientes(set())
    assert pendientes[0]["id"] == viejas[-1]["id"]


def test_segunda_pasada_separa_el_rescate_de_una_edicion(monkeypatch, tmp_path):
    """Archivos ya recalculados ("actual", por el piso aunque la nota se recolectó antes): el cuerpo cambia solo por
    el rescate de los recomendados sin cerrar, y eso no es una edición de la página."""
    monkeypatch.setitem(recalculo.PISO_DE_GENERACION, "rpp", "actual")  # el piso de la segunda pasada (31-oct)
    tarjeta = ("<div class='article__block-item'><article class='news'><h2><a href='https://rpp.pe/lima/otra-noticia-2'>"
               "Vecinos piden ayuda</a></h2></article></div>")  # fmt: skip
    pagina = ('<html><head><script type="application/ld+json">{"@type": "NewsArticle", "headline": "Titular",'
              ' "datePublished": "2026-02-01T10:00:00-05:00"}</script></head><body><div class="body">'
              f"<p>{RELLENO}</p><div class='article__block'><div class='article__block-list'>{tarjeta}"
              "<p>El Niño costero de intensidad fuerte llegaría en verano.</p></div></div></div></body></html>"
              ).encode()  # fmt: skip
    url = "https://rpp.pe/lima/esta-noticia-1"
    fila = {"medio": "rpp", "id": "noticia-1", "url": url, "titulo": "Titular", "seccion": "lima",
            "fecha_lista": "", "via": "archivo", "http": 200}  # fmt: skip
    with monkeypatch.context() as m:  # lo que guardó el código "actual", sin rescate
        m.setattr("radar.noticias.nota.LISTA_SIN_CERRAR", {})
        vieja, _ = filas_de_nota("rpp", fila, leer_html("rpp", pagina, url), "candidata")
    vieja["recolectado"] = "2026-10-20T10:00:00-05:00"
    escribir_csv(tmp_path / "notas.csv", esquemas.NOTAS, [vieja])
    vieja = leer_csv(tmp_path / "notas.csv")[0]  # como queda guardada
    assert "rpp" in LISTA_SIN_CERRAR and vieja["magnitudes"] == ""
    campos = leer_html("rpp", pagina, url)
    nueva, enlaces = filas_de_nota("rpp", fila, campos, "candidata")
    cambio = recalculo.comparar(vieja, nueva, campos, enlaces, "rpp", "ahora")
    assert cambio["generacion"] == "actual" and cambio["pagina_editada"] is False
    assert cambio["magnitudes_ahora"] == "fuerte" and cambio["causa_magnitudes"] == "rescate"
    assert cambio["magnitudes_texto_nuevo"] == ""  # el control: el cuerpo de antes reproduce lo guardado


def test_tercera_pasada_separa_la_regla_de_menciones(monkeypatch, tmp_path):
    """Archivos de la generación "rescate": el cuerpo no cambia, pero la regla de menciones del 1-nov reconoce "FEN"
    y "Fenómeno el Niño"; el cambio se atribuye a "menciones" y no a una edición."""
    pagina = ('<html><head><script type="application/ld+json">{"@type": "NewsArticle", "headline": "Titular",'
              ' "datePublished": "2026-02-01T10:00:00-05:00"}</script></head><body><div class="body">'
              "<p>Piura se prepara para un FEN de magnitud fuerte.</p>"
              f"<p>{RELLENO}</p></div></body></html>").encode()  # fmt: skip
    url = "https://rpp.pe/lima/esta-noticia-1"
    fila = {"medio": "rpp", "id": "noticia-1", "url": url, "titulo": "Titular", "seccion": "lima",
            "fecha_lista": "", "via": "archivo", "http": 200}  # fmt: skip
    with monkeypatch.context() as m:  # lo que guardó el código con la regla de menciones anterior
        m.setattr("radar.noticias.rasgos.NINO", recalculo._NINO_ANTERIOR)
        vieja, _ = filas_de_nota("rpp", fila, leer_html("rpp", pagina, url), "candidata")
    vieja["recolectado"] = "2026-10-20T10:00:00-05:00"
    escribir_csv(tmp_path / "notas.csv", esquemas.NOTAS, [vieja])
    vieja = leer_csv(tmp_path / "notas.csv")[0]
    assert vieja["sobre_nino"] == "0" and vieja["magnitudes"] == ""
    campos = leer_html("rpp", pagina, url)
    nueva, enlaces = filas_de_nota("rpp", fila, campos, "candidata")
    cambio = recalculo.comparar(vieja, nueva, campos, enlaces, "rpp", "ahora")
    assert cambio["generacion"] == "rescate" and cambio["pagina_editada"] is False
    assert cambio["sobre_ahora"] is True and cambio["causa_sobre"] == "menciones"
    assert cambio["magnitudes_ahora"] == "fuerte" and cambio["causa_magnitudes"] == "menciones"
    assert cambio["sobre_texto_nuevo"] is False and cambio["magnitudes_texto_nuevo"] == ""  # el control reproduce


def test_cuarta_pasada_la_fecha_de_andina_no_es_una_edicion(tmp_path):
    """Andina no tiene fecha de edición: una edición se ve en el sha1 del cuerpo. Una fila guardada con la línea
    "Publicado:" se compara con el cuerpo de antes, que la conserva, así que no cuenta como edición y se controla."""
    pagina = ('<html><head><script type="application/ld+json">{"@type": "NewsArticle", "headline": "Titular",'
              ' "datePublished": "2026-02-01T10:00:00-05:00"}</script></head><body><div class="col paddingnota">'
              f"<div class='col linknotas'><div>El Niño costero de magnitud fuerte. {RELLENO}</div>"
              "<br />Publicado: 1/2/2026</div></div></body></html>").encode()  # fmt: skip
    url = "https://andina.pe/agencia/noticia-x-1.aspx"
    fila = {"medio": "andina", "id": "1", "url": url, "titulo": "Titular", "seccion": "", "fecha_lista": "",
            "via": "numero", "http": 200}  # fmt: skip
    campos = leer_html("andina", pagina, url)
    vieja, _ = filas_de_nota("andina", fila, {**campos, "cuerpo": campos["cuerpo_con_fecha"]}, "candidata")
    vieja["recolectado"] = "2026-11-01T08:40:00-05:00"
    escribir_csv(tmp_path / "notas.csv", esquemas.NOTAS, [vieja])
    vieja = leer_csv(tmp_path / "notas.csv")[0]
    nueva, enlaces = filas_de_nota("andina", fila, campos, "candidata")
    assert nueva["sha1_cuerpo"] != vieja["sha1_cuerpo"]
    cambio = recalculo.comparar(vieja, nueva, campos, enlaces, "andina", "ahora")
    assert cambio["generacion"] == "rescate" and cambio["pagina_editada"] is False
    assert cambio["sobre_texto_nuevo"] == (vieja["sobre_nino"] == "1") and cambio["causa_sobre"] == ""
    assert cambio["magnitudes_texto_nuevo"] == vieja["magnitudes"] and cambio["causa_magnitudes"] == ""
    assert recalculo.generacion("2026-11-02T08:00:00-05:00", "andina") == "fecha"
