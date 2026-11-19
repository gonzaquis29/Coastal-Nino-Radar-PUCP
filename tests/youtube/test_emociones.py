"""Pruebas sintéticas de radar.youtube.emociones (sin modelos: se usan clasificadores falsos)."""

import pytest

from radar import config
from radar.youtube import emociones as em
from radar.youtube import privacidad

SAL = b"sal-de-prueba-0123456789"


@pytest.fixture(autouse=True)
def sal(monkeypatch, tmp_path):
    monkeypatch.setattr(privacidad, "_sal", lambda: SAL)
    monkeypatch.setattr(config, "DIR_YOUTUBE", tmp_path / "processed")


def video(id_="v1", canal="UCcanal"):
    return {"id": id_, "canal": canal, "titulo": "Fenómeno El Niño en Piura", "descripcion": "Perú",
            "publicado": "2026-08-01T15:00:00Z", "descargado": "2026-11-16", "comentarios": 50}  # fmt: skip


def comentario(id_, texto, autor="a1", video_="v1", hilo="", publicado="2026-08-02T10:00:00Z"):
    return {"id": id_, "video": video_, "autor": autor, "texto": texto, "hilo": hilo, "publicado": publicado,
            "descargado": "2026-11-16"}  # fmt: skip


def test_texto():
    assert em.sin_emojis("Ya llegó el Niño 😱😱") == "Ya llegó el Niño"
    assert em.palabras("😂😂") == 0
    assert em.palabras("[mencion] que miedo 😱") == 2
    assert em.idioma("que miedo tengo de las lluvias") == "es"
    assert em.idioma("this is the end of the world") == "en"
    assert em.idioma("Bendiciones hermanos") == "dudoso"
    assert em.idioma("Bendiciones Piurá") == "es"
    assert em.para_modelo("[mencion] mira [enlace]") == "@usuario mira url"
    assert em.grupo_emoji("jaja 😂🤣 ❤️") == "alegria"
    assert em.grupo_emoji("😂😭") == ""
    assert em.grupo_emoji("❤️🙏") == ""


def test_unidades_filtra_y_limita():
    videos = {"v1": video()}
    dueno = privacidad.seudonimo("UCcanal")
    cs = [
        comentario("c1", "que miedo da todo esto"),
        comentario("c2", "que miedo da todo esto", publicado="2026-08-02T11:00:00Z"),  # repetido
        comentario("c3", "otra cosa que digo yo", publicado="2026-08-02T12:00:00Z"),
        comentario("c4", "y una más de las mías", publicado="2026-08-02T13:00:00Z"),
        comentario("c5", "la cuarta ya no entra", publicado="2026-08-02T14:00:00Z"),  # más de 3
        comentario("c6", "Síguenos en nuestro canal", autor=dueno),
        comentario("c7", "compra aquí [enlace] ya", autor="a2"),
        comentario("c8", "😂😂", autor="a3"),
        comentario("c9", "this is the end", autor="a4"),
        comentario("c10", "muy bien", autor="a5"),
        comentario("c11", "[mencion] tienes razón en eso", autor="a6", hilo="h1"),
        comentario("c12", "esto es de otro video", video_="v9"),
    ]
    lista, descartes, pasan = em.unidades({c["id"]: c for c in cs}, videos, {})
    por_id = {c["id"]: c["unidad"] for c in lista}
    assert por_id == {"c1": "principal", "c3": "principal", "c4": "principal", "c10": "corto", "c11": "respuesta"}
    assert descartes["repetido del mismo autor"] == 1
    assert descartes["más de 3 por autor y video"] == 1
    assert descartes["del dueño del canal"] == 1
    assert descartes["con enlace o datos de contacto"] == 1
    assert descartes["vacío o solo emojis"] == 1
    assert descartes["en inglés"] == 1
    assert set(pasan) == {"v1"}
    textos = em.items(lista, pasan)
    assert any(x["unidad"] == "titulo" for x in textos)
    assert next(x for x in textos if x["id"] == "c11")["texto"].startswith("@usuario")


def test_muestra_m3_limites_y_semilla(monkeypatch):
    monkeypatch.setattr(em, "MUESTRA_M3", 8)
    poblacion = [{"id": f"c{i}", "video": f"v{i % 2}", "autor": f"a{i % 6}"} for i in range(40)]
    m = em.muestra_m3(poblacion)
    assert m == em.muestra_m3(list(reversed(poblacion)))
    assert len({c["autor"] for c in m}) == len(m) == 6  # 1 por autor: solo hay 6 autores
    assert max(sum(c["video"] == v for c in m) for v in ("v0", "v1")) <= em.POR_VIDEO_M3


def test_etiqueta_zs():
    cual = {e: 0.1 for e in em.EMOCIONES} | {"miedo": 0.5}
    assert em.etiqueta_zs(0.49, cual) == "others"
    assert em.etiqueta_zs(0.5, cual) == "miedo"


def falso(etiqueta_de):
    def clasificar(textos):
        salida = []
        for t in textos:
            e = etiqueta_de(t)
            salida.append(({c: (0.9 if c == e else 0.1 / 6) for c in em.CLASES}, 1, 0))
        return salida

    return clasificar


def polaridad_falsa(textos):
    return [({"negativo": 0.2, "neutral": 0.7, "positivo": 0.1}, 1, 0) for _ in textos]


def test_procesar_retoma_y_sin_emoji(tmp_path):
    ruta = tmp_path / "2026-11-16_emociones.csv"
    lista = [{"id": f"c{i}", "unidad": "principal", "video": "v1", "fecha": "2026-08-02T10:00:00Z",
              "texto": f"texto {i} 😱", "sin_emoji": f"texto {i}", "emoji": "miedo", "huella": f"h{i}"}
             for i in range(5)]  # fmt: skip
    llamadas = []

    def emocion(textos):
        llamadas.extend(textos)
        return falso(lambda t: "miedo" if "😱" in t else "others")(textos)

    class Corte(Exception):
        pass

    def cortar(textos):
        if len(llamadas) >= 4:
            raise Corte
        return emocion(textos)

    with pytest.raises(Corte):
        em.procesar(lista, ruta, cortar, polaridad_falsa, lote=2)
    assert len(em.hechos(ruta, em.COLUMNAS)) == 2  # el primer lote quedó guardado
    llamadas.clear()
    salida = em.procesar(lista, ruta, emocion, polaridad_falsa, lote=2)
    assert len(salida) == 5
    assert len([t for t in llamadas if "😱" in t]) == 3  # solo los que faltaban
    fila = salida["c0"]
    assert (fila["emocion"], fila["se_emocion"], fila["polaridad"]) == ("miedo", "others", "neutral")


def resultado(id_, emocion, se=None, emoji="", unidad="principal", video_="v1"):
    return {"id": id_, "unidad": unidad, "video": video_, "tramos": "1", "truncados": "0", "emocion": emocion,
            "se_emocion": se or emocion, "emoji": emoji, "polaridad": "neutral",
            "fecha": "2026-08-02T10:00:00Z"}  # fmt: skip


def test_medir_criterios():
    filas = [resultado(f"a{i}", "alegria", emoji="alegria") for i in range(60)]
    filas += [resultado(f"m{i}", "miedo", emoji="miedo") for i in range(50)]
    filas += [resultado(f"o{i}", "others") for i in range(40)]
    zs = {f["id"]: {"zs_emocion": f["se_emocion"]} for f in filas}
    medidas, _ = em.medir(filas, zs, set(zs))
    pasa = {f["criterio"][:2]: (f["valor"], f["pasa"]) for f in medidas}
    assert pasa["M0"] == (0, True)
    assert pasa["M1"] == (round(110 / 150, 3), True)
    assert pasa["M2"] == (1.0, True)
    assert pasa["M3"] == (1.0, True)
    assert em.decision(medidas).startswith("Pasan M0 a M3")


def test_m2_no_pasa_con_pocos_evaluables():
    filas = [resultado(f"a{i}", "alegria", emoji="alegria") for i in range(40)]
    filas += [resultado(f"m{i}", "miedo", emoji="miedo") for i in range(20)]  # grupo con < 30: no cuenta
    medidas, info = em.medir(filas, {}, set())
    m2 = next(f for f in medidas if f["criterio"].startswith("M2"))
    assert not m2["pasa"] and len(info["evaluables"]) == 40
    assert em.decision(medidas).startswith("Pasan M0 y M1")


def test_m1_no_pasa():
    filas = [resultado(f"o{i}", "others") for i in range(10)]
    medidas, _ = em.medir(filas, {}, set())
    assert em.decision(medidas).startswith("No pasa")


def test_partir_hasta_caber():
    def contar(textos):  # como el tokenizador: la frase cuenta más que la suma de sus palabras
        return [len(t.split()) * 2 for t in textos]

    partes = em.partir_hasta_caber(" ".join(f"p{i}" for i in range(20)), contar, 10)
    assert all(contar([p])[0] <= 10 for p in partes)
    assert " ".join(partes) == " ".join(f"p{i}" for i in range(20))
    assert em.partir_hasta_caber("una", contar, 1) == ["una"]
