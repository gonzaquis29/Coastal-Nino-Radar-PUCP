"""Pruebas sintéticas de la red de audiencias de YouTube: sin datos reales."""

import math

import numpy as np
import pytest

from radar.redes import audiencias as au


def _dos_grupos():
    """Dos grupos de 4 canales: cada grupo comparte sus propios autores; un solo autor cruza entre grupos."""
    autores = {}
    for g in range(2):
        for k in range(4):
            autores[f"c{g}{k}"] = {f"a{g}{x}" for x in range(12) if (x + k) % 3}
    autores["c00"].add("puente")
    autores["c10"].add("puente")
    return autores


def test_bipartita_y_matriz():
    b = au.Bipartita.de_conjuntos({"x": {"a", "b"}, "y": {"b"}})
    assert b.canales == ["x", "y"]
    assert sorted(b.filas) == [(0,), (0, 1)]
    assert b.matriz().toarray().sum() == 3


def test_filtrar():
    datos = {"chico": {"a"}, "grande": {"a", "b", "c"}, "otro": {"a", "d", "e"}}
    assert set(au.filtrar(datos, 3)) == {"grande", "otro"}
    sin_activos = au.filtrar(datos, 3, maximo_canales_por_autor=1)
    assert "a" not in sin_activos["grande"] and "a" not in sin_activos["otro"]


def test_curveball_conserva_grados():
    azar = np.random.default_rng(0)
    filas = [tuple(sorted(set(azar.integers(0, 20, azar.integers(1, 6))))) for _ in range(300)]
    barajadas = au.curveball(filas, semilla=1)
    assert sorted(len(f) for f in filas) == sorted(len(f) for f in barajadas)  # grado de cada autor
    grados = np.bincount([c for f in filas for c in f], minlength=20)
    assert (np.bincount([c for f in barajadas for c in f], minlength=20) == grados).all()  # grado de cada canal
    assert barajadas != [tuple(sorted(f)) for f in filas]
    assert au.curveball(filas, semilla=1) == barajadas  # semilla fija


def test_proyectar_salton():
    b = au.Bipartita.de_conjuntos({"x": {"a", "b", "c", "d"}, "y": {"a"}, "z": {"q"}})
    g = au.proyectar(b)
    assert g.number_of_nodes() == 3 and g.number_of_edges() == 1
    datos = g.get_edge_data(0, 1)
    assert datos[au.COMPARTIDOS] == 1
    assert datos[au.PESO] == pytest.approx(1 / math.sqrt(4 * 1))
    assert datos[au.DISTANCIA] == pytest.approx(2.0)
    assert au.componente_mayor(g).number_of_nodes() == 2


def test_comunidades_y_nulo():
    b = au.Bipartita.de_conjuntos(_dos_grupos())
    g = au.componente_mayor(au.proyectar(b))
    comunidades, q = au.louvain(g, semilla=3)
    assert len(comunidades) == 2 and q > 0.3
    nodos = sorted(g)
    assert au.nmi(comunidades, au.propagacion(g, 3), nodos) == pytest.approx(1.0)
    nulos = [au.nulo(b, semilla=s)["q"] for s in range(20)]
    assert q > np.percentile(nulos, 95)  # la estructura de dos grupos no la da el azar


def test_cruce():
    b = au.Bipartita.de_conjuntos({"medio": {"a", "b"}, "x": {"a", "c", "d", "e"}, "y": {"f"}})
    indice = {c: i for i, c in enumerate(b.canales)}
    cruces = au.cruce(b, {indice["medio"]})
    assert cruces[indice["x"]] == pytest.approx(0.25)
    assert cruces[indice["y"]] == 0
    assert (au.cruce(b, set()) == 0).all()


def test_backbone():
    b = au.Bipartita.de_conjuntos(_dos_grupos())
    g = au.proyectar(b)
    grados = np.asarray(b.matriz().sum(axis=0)).ravel()
    fondo = au.backbone(g, len(b.filas), grados)
    assert fondo  # las aristas dentro de cada grupo son significativas
    i, j = b.canales.index("c00"), b.canales.index("c10")
    assert (i, j) not in fondo and (j, i) not in fondo  # la del puente no
    assert au.backbone(au.proyectar(au.Bipartita.de_conjuntos({"x": {"a"}})), 1, [1]) == []


def test_asortatividad():
    b = au.Bipartita.de_conjuntos(_dos_grupos())
    g = au.componente_mayor(au.proyectar(b))
    grupo = {i: float(b.canales[i][1]) for i in g}  # el valor es el grupo: muy asortativo
    observada, p = au.asortatividad_permutada(g, grupo, 200, 0)
    assert observada > 0.8 and p < 0.05
    assert math.isnan(au.pearson_ponderado([1, 2], [1, 2], [1, 1]))


def test_spearman_con_ic():
    x = np.arange(40.0)
    rho, (inf, sup), p, n = au.spearman_con_ic(x, x + np.sin(x), 200, 0)
    assert rho > 0.9 and inf > 0.8 and sup <= 1 and p < 0.01 and n == 40
    assert math.isnan(au.spearman_con_ic([1, 2], [1, 2], 10, 0)[0])
