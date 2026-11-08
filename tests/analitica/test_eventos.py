import datetime as dt
import random

import numpy as np
import pytest

from radar.analitica import eventos as ev

D0 = dt.date(2026, 1, 1)


def _dias(n):
    return [D0 + dt.timedelta(k) for k in range(n)]


def _nota(fecha, sobre="0", menciona="0", comunicados="", dudosa="0"):
    return {"fecha_publicacion": f"{fecha}T10:00:00-05:00", "sobre_nino": sobre, "menciona_nino": menciona,
            "comunicados": comunicados, "fecha_dudosa": dudosa}  # fmt: skip


def test_series_cuenta_por_dia():
    notas = [_nota("2026-01-01", "1", "1"), _nota("2026-01-01"), _nota("2026-01-02", "0", "1", "enfen-2026-01:numero"),
             _nota("2026-01-02", dudosa="1"), _nota("2025-12-31", "1", "1")]  # fmt: skip
    dias, s = ev.series(notas, "2026-01-01", "2026-01-02")
    assert len(dias) == 2
    assert list(s["total"]) == [2, 1] and list(s["nino"]) == [1, 0]
    assert list(s["citan"]) == [0, 1] and list(s["otros"]) == [1, 0]


def test_eventos_completos_y_relativos():
    dias = _dias(30)
    fechas = [D0 + dt.timedelta(2), D0 + dt.timedelta(10), D0 + dt.timedelta(25)]
    eventos = ev.eventos_completos(fechas, dias)
    assert eventos == [D0 + dt.timedelta(10)]  # la primera no tiene −3; la última no tiene +7
    rel = ev.relativos(dias, eventos)
    assert rel[7] == -3 and rel[10] == 0 and rel[17] == 7 and rel[6] is None and rel[18] is None
    with pytest.raises(ValueError):
        ev.relativos(dias, [D0 + dt.timedelta(5), D0 + dt.timedelta(12)])


def test_poisson_recupera_coeficientes():
    rng = np.random.default_rng(0)
    X = np.column_stack([np.ones(2000), rng.normal(size=2000)])
    y = rng.poisson(np.exp(1.0 + 0.3 * X[:, 1]))
    beta = ev.poisson(X, y)
    assert beta == pytest.approx([1.0, 0.3], abs=0.05)


def test_poisson_con_exposicion():
    rng = np.random.default_rng(1)
    expo = rng.integers(50, 500, size=1000).astype(float)
    y = rng.poisson(0.1 * expo)
    beta = ev.poisson(np.ones((1000, 1)), y, expo)
    assert np.exp(beta[0]) == pytest.approx(0.1, rel=0.05)


def test_falsas_conservan_intervalos():
    dias = _dias(200)
    eventos = [D0 + dt.timedelta(k) for k in (20, 34, 50, 64, 80)]
    azar = random.Random(0)
    for _ in range(20):
        f = ev.falsas(eventos, dias, azar)
        assert sorted((b - a).days for a, b in zip(f, f[1:], strict=False)) == [14, 14, 16, 16]
        assert f[0] >= dias[0] + dt.timedelta(ev.ANTES) and f[-1] <= dias[-1] - dt.timedelta(ev.DESPUES)


def test_valor_p():
    nula = np.array([-1.0, 0.5, 2.0, -3.0])
    assert ev.valor_p(2.5, nula) == pytest.approx(2 / 5)
    assert ev.valor_p(0.1, nula) == 1.0


def test_detecta_un_pico_y_no_inventa_uno():
    rng = np.random.default_rng(2)
    dias = _dias(300)
    eventos = [D0 + dt.timedelta(k) for k in range(10, 290, 14)]
    rel = ev.relativos(dias, eventos)
    fija = ev.base(dias)
    lam = np.exp(2 + np.arange(300) / 150)
    plano = rng.poisson(lam).astype(float)
    con = plano.copy()
    for i, r in enumerate(rel):
        if r in ev.DIAS_EFECTO:
            con[i] = rng.poisson(lam[i] * 1.6)
    assert ev.efecto(fija, con, None, rel) == pytest.approx(np.log(1.6), abs=0.12)
    assert abs(ev.efecto(fija, plano, None, rel)) < 0.1


def test_con_pico_solo_toca_los_dias_del_efecto():
    y = np.full(20, 10.0)
    rel = [None] * 5 + list(range(-3, 8)) + [None] * 4
    nueva = ev.con_pico(y, rel, 0.5, random.Random(0))
    cambiados = {rel[i] for i in range(20) if nueva[i] != y[i]}
    assert cambiados <= set(ev.DIAS_EFECTO) and (nueva >= y).all()


def _serie_ciclica(efecto, semilla):
    rng = np.random.default_rng(semilla)
    dias = _dias(300)
    eventos = [D0 + dt.timedelta(k) for k in range(10, 290, 14)]
    rel = ev.relativos(dias, eventos)
    lam = np.exp(2 + np.arange(300) / 150)
    lam = np.array([lam[i] * (efecto if r in ev.DIAS_EFECTO else 1) for i, r in enumerate(rel)])
    return dias, rel, rng.poisson(lam).astype(float)


def test_contraste_resta_los_dias_antes():
    fija = np.ones((5, 2))
    c = ev.vector_contraste(fija)
    assert c.sum() == pytest.approx(0)
    assert c[2 + ev.ANTES] == pytest.approx(1 / 3) and c[2 + ev.ANTES - 1] == pytest.approx(-1 / 3)


def test_prueba_b_detecta_y_no_inventa():
    dias, rel, y = _serie_ciclica(1.6, 3)
    e, p, _ = ev.prueba_b(ev.base(dias), y, None, rel)
    assert e == pytest.approx(np.log(1.6), abs=0.15) and p < 0.01
    dias, rel, y = _serie_ciclica(1.0, 4)
    e, p, _ = ev.prueba_b(ev.base(dias), y, None, rel)
    assert abs(e) < 0.15 and p > 0.01


def test_hac_sin_retardo_es_el_sandwich_simple():
    rng = np.random.default_rng(5)
    X = np.column_stack([np.ones(500), rng.normal(size=500)])
    y = rng.poisson(np.exp(1 + 0.2 * X[:, 1])).astype(float)
    beta, Xv, yv, mu = ev.ajuste(X, y)
    v0 = ev.covarianza_hac(Xv, yv, mu, retardo=0)
    a = np.linalg.inv(X.T @ (mu[:, None] * X))
    assert np.sqrt(np.diag(v0)) == pytest.approx(np.sqrt(np.diag(a)), rel=0.15)  # Poisson bien especificado
