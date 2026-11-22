"""Pruebas sintéticas de la analítica web: sin datos reales."""

import datetime as dt
import math

import numpy as np
import pytest

from radar.analitica import indicadores as ind
from radar.analitica import web


def test_restar_mediana_y_rangos_centrados():
    assert ind.restar_mediana([1, 3, 10, 20], ["a", "a", "b", "b"]).tolist() == [-1, 1, -5, 5]
    centrados = ind.rangos_centrados([5, 1, 3, 100, 200], ["x", "x", "x", "y", "y"])
    assert centrados.tolist() == pytest.approx([1 / 3, -1 / 3, 0, -0.25, 0.25])


def test_correlacion_dentro_ignora_lo_que_separa_a_los_canales():
    azar = np.random.default_rng(0)
    grupos = np.repeat(np.arange(20), 10)
    nivel = -5.0 * grupos  # entre canales la relación es negativa
    x = azar.normal(size=200)
    y = x + nivel + azar.normal(scale=0.3, size=200)
    assert np.corrcoef(x + grupos, y)[0, 1] < 0
    assert ind.correlacion_dentro(x + grupos, y, grupos) > 0.9


def test_correlacion_dentro_descuenta_la_covariable():
    azar = np.random.default_rng(1)
    grupos = np.repeat(np.arange(30), 8)
    z = azar.normal(size=240)
    x, y = z + azar.normal(scale=0.2, size=240), z + azar.normal(scale=0.2, size=240)
    assert ind.correlacion_dentro(x, y, grupos) > 0.8
    assert abs(ind.correlacion_dentro(x, y, grupos, [z])) < 0.4  # en rangos de grupos de 8 queda un resto


def test_remuestras_de_grupos_separan_las_copias():
    grupos = np.array(["a", "a", "b", "b", "b"])
    for indices, nuevos in ind.remuestras_de_grupos(grupos, 20, 3):
        assert len(indices) == len(nuevos)
        assert len(set(nuevos.tolist())) == 2
        for g in set(nuevos.tolist()):
            assert len({grupos[i] for i in indices[nuevos == g]}) == 1


def test_correlacion_dentro_ic():
    azar = np.random.default_rng(2)
    grupos = np.repeat(np.arange(25), 6)
    x = azar.normal(size=150)
    rho, replicas = ind.correlacion_dentro_ic(x, -x + azar.normal(scale=0.5, size=150), grupos, [], 50, 0)
    assert rho < -0.7 and len(replicas) == 50 and max(replicas) < 0


@pytest.mark.parametrize(
    ("ic", "signos", "esperada"),
    [
        ((-0.3, -0.1), [-0.2, -0.1, -0.2], "sí"),
        ((0.1, 0.3), [0.2, 0.1, 0.2], "no"),
        ((-0.1, 0.2), [0.1, 0.1, 0.1], "no concluyente"),
        ((-0.3, -0.1), [-0.2, 0.05, -0.2], "no concluyente"),
        ((-0.3, -0.1), [-0.2, math.nan, -0.2], "no concluyente"),
    ],
)
def test_respuesta(ic, signos, esperada):
    assert ind.respuesta(ic, signos) == esperada


def test_con_minimo_por_grupo_y_terciles():
    assert ind.con_minimo_por_grupo(["a", "a", "a", "b"], 3).tolist() == [True, True, True, False]
    assert sorted(ind.terciles(np.arange(9.0)).tolist()) == [0, 0, 0, 1, 1, 1, 2, 2, 2]


def test_semana_de():
    assert ind.semana_de("2026-11-13T10:00:00-05:00") == dt.date(2026, 11, 8)  # viernes → domingo anterior
    assert ind.semana_de(dt.date(2026, 11, 8)) == dt.date(2026, 11, 8)


def test_correlacion_cruzada_encuentra_el_desfase():
    azar = np.random.default_rng(4)
    notas = azar.normal(size=60)
    trends = np.concatenate([[0.0], notas[:-1]])  # Trends va una semana detrás
    cruzada = ind.correlacion_cruzada(notas, trends)
    assert max(cruzada, key=lambda k: abs(cruzada[k])) == 1
    assert cruzada[1] == pytest.approx(1.0)
    assert ind.maximo_absoluto({0: math.nan, 1: -0.4}) == pytest.approx(0.4)


def test_iaaft_conserva_la_distribucion():
    azar = np.random.default_rng(5)
    serie = np.concatenate([np.zeros(15), azar.integers(1, 100, 31)]).astype(float)
    sustituta = ind.iaaft(serie, np.random.default_rng(6))
    assert sorted(sustituta) == sorted(serie)
    assert not np.array_equal(sustituta, serie)
    nulo = ind.nulo_cruzado(ind.diferencias_log(serie), serie, 20, 0)
    assert nulo.shape == (20,) and (nulo >= 0).all()


def test_sube_tras_comunicado():
    semanas = {dt.date(2026, 3, 1) + dt.timedelta(7 * k): v for k, v in enumerate([10, 10, 10, 30, 30, 10])}
    assert ind.sube_tras_comunicado(semanas, dt.date(2026, 3, 27)) is True  # viernes de la semana del 22-mar
    assert ind.sube_tras_comunicado(semanas, dt.date(2026, 3, 6)) is None  # sin 3 semanas antes
    assert ind.sube_tras_comunicado(semanas, dt.date(2026, 4, 5)) is None  # sin la semana siguiente


def test_dias_de_reaccion():
    emision = dt.date(2026, 5, 1)
    citas = [dt.date(2026, 4, 30), dt.date(2026, 5, 3), dt.date(2026, 5, 2), dt.date(2026, 6, 1)]
    assert ind.dias_de_reaccion(emision, citas, 14) == (1, True, 1)
    assert ind.dias_de_reaccion(emision, [dt.date(2026, 6, 1)], 14) == (None, True, 0)


def test_proporciones_principales():
    assert ind.proporciones_principales({"a": 5, "b": 3, "c": 2}, 2) == [("a", 0.5), ("b", 0.3), ("otras", 0.2)]
    assert ind.proporciones_principales({}, 2) == []


def test_registro_de_uso_sintetico():
    eventos, sesiones, pasos, tiempos = web.registros_sinteticos()
    assert web.resumen_uso(eventos) == (sesiones, pasos, tiempos)
    assert math.isnan(ind.embudo([])[0][2])  # sin sesiones no hay proporción


def test_guardar_validacion_no_borra_otras_etapas(tmp_path, monkeypatch):
    monkeypatch.setattr(web.config, "DIR_ANALITICA", tmp_path)
    web.guardar_validacion(
        [web.criterio(web.PRUEBA, "W1 a", 1, "-", True), web.criterio(web.PRUEBA, "W9 b", 2, "-", True)]
    )
    web.guardar_validacion([web.criterio(web.PRUEBA, "W9 b", 3, "-", True)])
    filas = {f["criterio"]: f["valor"] for f in web.leer_csv(web.ruta("validacion"))}
    assert filas == {"W1 a": "1", "W9 b": "3"}
    assert web.ya_corridas(["engagement", "uso"]) == []
