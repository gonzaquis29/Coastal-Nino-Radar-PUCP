"""Pruebas sintéticas del modelo de engagement: sin red, sin modelos de lenguaje y sin datos reales."""

import math

import numpy as np
import pytest

from radar.modelos import engagement as eg
from radar.modelos import rasgos as rg


def _video(**cambios):
    base = {"id": "v1", "canal": "c1", "publicado": "2026-03-10T15:00:00Z", "descargado": "2026-11-22",
            "vistas": 1000, "likes": 10, "comentarios": 2, "duracion": "PT3M5S", "categoria": "25",
            "titulo": "¡ALERTA! El Niño costero 😱", "descripcion": "Más en https://www.gob.pe/senamhi #ElNiño",
            "enlaces": ["https://www.gob.pe/senamhi"]}  # fmt: skip
    return base | cambios


def test_segundos():
    assert rg.segundos("PT1M51S") == 111
    assert rg.segundos("PT2H") == 7200
    assert rg.segundos("P1DT1S") == 86401
    assert rg.segundos("raro") is None


def test_particion_y_motivos():
    assert rg.particion(rg.FIN_ENTRENAMIENTO) == "entrenamiento"
    assert rg.particion(rg.FIN_ENTRENAMIENTO.replace(day=30).replace(month=9)) == "prueba"
    assert rg.motivo_fuera(_video(), {}, "2026-11-22") is None
    assert rg.motivo_fuera(_video(descargado="2026-11-16"), {}, "2026-11-22") == "descarga anterior al corte"
    # 8-nov entra (14 días al 22-nov); 9-nov no
    assert rg.motivo_fuera(_video(publicado="2026-11-08T17:00:00Z"), {}, "2026-11-22") is None
    assert rg.motivo_fuera(_video(publicado="2026-11-09T17:00:00Z"), {}, "2026-11-22") == "menos de 14 días"
    assert rg.motivo_fuera(_video(likes=None), {}, "2026-11-22").startswith("sin vistas")
    assert rg.motivo_fuera(_video(vistas=0), {}, "2026-11-22").startswith("sin vistas")


def test_beta_binomial_recupera_el_prior():
    azar = np.random.default_rng(0)
    p = azar.beta(2, 198, size=4000)  # media 0,01, α + β = 200
    n = azar.integers(200, 20000, size=4000)
    x = azar.binomial(n, p)
    alfa, beta = rg.beta_binomial(x, n)
    assert alfa / (alfa + beta) == pytest.approx(0.01, rel=0.05)
    assert alfa + beta == pytest.approx(200, rel=0.25)


def test_objetivo_suaviza_pocas_vistas():
    alfa, beta = 1.0, 99.0  # prior 0,01
    poco, mucho = rg.tasa(rg.objetivo([0, 0], [10, 100000], alfa, beta))
    assert poco == pytest.approx(1 / 110)  # casi el prior
    assert mucho < 0.0001  # casi la tasa observada (0)
    assert np.isfinite(rg.objetivo([5], [3], alfa, beta)).all()  # más éxitos que vistas no rompe


def test_texto_para_distancia():
    texto = rg.texto_para_distancia("Título @alguien", "Ver https://x.com/a y www.y.pe #Tag fin")
    assert "http" not in texto and "www" not in texto and "#" not in texto and "@" not in texto
    assert texto.splitlines() == ["Título", "Ver y fin"]
    largo = rg.texto_para_distancia("uno dos", " ".join(["p"] * 300))
    assert len(largo.split()) == rg.PALABRAS_TEXTO
    assert rg.texto_para_distancia("", "") == ""


def test_rasgos_titulo():
    r = rg.rasgos_titulo("¡ALERTA! ¿Niño extraordinario? 😱🌊")
    assert r["exclamaciones"] == 2 and r["emojis"] == 2 and r["pregunta"] and r["palabras_titulo"] == 4
    assert 0 < r["mayusculas"] < 1
    assert rg.rasgos_titulo("")["mayusculas"] == 0.0
    assert not rg.rasgos_titulo("hola")["pregunta"]


def test_enlaza_gob_y_momento():
    assert rg.enlaza_gob(["https://www.gob.pe/senamhi"]) and rg.enlaza_gob(["senamhi.gob.pe/x"])
    assert not rg.enlaza_gob(["https://gob.pe.ejemplo.com", "https://youtube.com"])
    assert rg.momento("2026-03-14T15:00:00Z") == (True, True)  # sábado 10:00 en Lima
    assert rg.momento("2026-03-16T02:00:00Z") == (True, False)  # lunes en UTC, domingo 21:00 en Lima
    assert rg.momento("2026-03-16T23:30:00Z") == (False, False)  # lunes 18:30 en Lima
    assert rg.categoria("25") == "25" and rg.categoria("10") == "otra"


def test_spearman_por_tipo_pondera():
    y = np.arange(10.0)
    tipos = np.array(["medio"] * 4 + ["otros"] * 6)
    pred = np.concatenate([-y[:4], y[4:]])  # medio al revés (−1), otros perfecto (+1)
    assert rg.spearman_por_tipo(pred, y, tipos) == pytest.approx((4 * -1 + 6 * 1) / 10)
    assert math.isnan(rg.spearman([1, 1, 1], [1, 2, 3]))
    oficiales = np.array(["oficial"] * 10)
    assert math.isnan(rg.spearman_por_tipo(y, y, oficiales))


def test_remuestras_por_grupo():
    grupos = np.array(["a", "a", "b", "c"])
    primera = list(rg.remuestras_por_grupo(grupos, 5, 1))
    segunda = list(rg.remuestras_por_grupo(grupos, 5, 1))
    assert all(np.array_equal(a, b) for a, b in zip(primera, segunda, strict=True))  # semilla fija
    for idx in primera:
        assert np.sum(idx == 0) == np.sum(idx == 1)  # los videos de un canal entran juntos


def test_mae_r2_intervalo():
    assert rg.mae([1, 2], [2, 2]) == 0.5
    assert rg.r2([1, 2, 3], [1, 2, 3]) == 1.0
    assert rg.intervalo([0, 1, 2, 3, 4, float("nan")]) == (pytest.approx(0.1), pytest.approx(3.9))


def _fila(i, tipo, particion, x, vistas=1000, topico=0):
    fecha = "2026-08-10" if particion == "entrenamiento" else "2026-10-10"
    return {"id": f"v{i}", "canal": f"c{i % 7}", "fecha": fecha,
            "particion": particion, "tipo": tipo, "categoria": "25", "vistas": str(vistas), "likes": str(x),
            "comentarios": "0", "suscriptores": "1000", "videos_canal": "10", "canal_peru": "1", "duracion": "120",
            "fin_semana": "0", "diurno": "1", "enlaza_gob": "0", "mayusculas": "0.1", "exclamaciones": "0",
            "emojis": "0", "pregunta": "0", "palabras_titulo": "8", "magnitud": "0", "palabras_texto": "20",
            "tipo_texto": "corto", "coseno": str(0.3 + x / 100), "color_reglas": "sin_afirmaciones",
            "topico": str(topico), "coseno_topico": "0.5"}  # fmt: skip


def test_datos_y_modelos_sinteticos():
    """Un coseno que predice la tasa: el boosting lo aprende y la importancia del grupo cercanía es positiva."""
    pytest.importorskip("sklearn")
    filas = [_fila(i, "otros" if i % 3 else "medio", "entrenamiento", x=i % 30, topico=i % 2) for i in range(210)]
    eleccion = {"alfa": 1.0, "beta": 99.0, "topicos": [0, 1], "con_topicos": True, "con_no_coincide": False}
    d = eg.Datos(filas, eleccion)
    assert d.X.shape == (210, len(eg.CONTROLES) + 1 + len(eg.RASGOS) + 1 + 2)
    assert "no_coincide" not in d.columnas and "topico_1" in d.columnas
    modelo = eg.ajustar("G", {"profundidad": 2, "arboles": 100}, d.X, d.y)
    assert rg.spearman(modelo.predict(d.X), d.y) > 0.9
    media, _, _ = eg.importancia(modelo, d.X, d.y, d.indices("cercania"), 5, 0)
    assert media > 0
    sub = d.sub(d.tipo == "medio")
    assert len(sub.y) == 70 and len(sub.filas) == 70
    ridge = eg.ajustar("L", {"alfa": 1}, d.X, d.y)
    assert np.isfinite(ridge.predict(d.X)).all()
    rival = eg.ajustar_poisson("G", {"profundidad": 2, "arboles": 100}, d.X, d.exitos, d.vistas)
    assert (rival.predict(d.X) > 0).all()


def test_coseno_vacio_no_rompe_ridge():
    pytest.importorskip("sklearn")
    filas = [_fila(i, "otros", "entrenamiento", x=i % 10) for i in range(40)]
    filas[0]["coseno"] = ""
    d = eg.Datos(filas, {"alfa": 1.0, "beta": 99.0, "topicos": [0], "con_topicos": False, "con_no_coincide": True})
    assert np.isnan(d.X[0, d.columnas.index("coseno")])
    assert np.isfinite(eg.ajustar("L", {"alfa": 1}, d.X, d.y).predict(d.X)).all()
