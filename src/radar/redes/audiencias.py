"""Red canal–canal por comentaristas compartidos (docs/redes/youtube.md): bipartita autor–canal, proyección con el
coseno de Salton, nulo curveball, comunidades y medidas. Funciones puras, sin archivos ni datos de YouTube."""

import math
import random

import networkx as nx
import numpy as np
from scipy import sparse
from scipy.stats import hypergeom, spearmanr

INTERCAMBIOS_POR_AUTOR = 5  # curveball: con ~5 intercambios por fila la matriz ya está mezclada (Strona et al., 2014)
PESO, DISTANCIA, COMPARTIDOS = "peso", "distancia", "compartidos"


class Bipartita:
    """Autores (filas) y canales (columnas) como listas de índices; los canales tienen nombre."""

    def __init__(self, canales, filas):
        self.canales = list(canales)
        self.filas = [tuple(sorted(f)) for f in filas if f]

    @classmethod
    def de_conjuntos(cls, autores_por_canal):
        canales = sorted(autores_por_canal)
        indice = {c: i for i, c in enumerate(canales)}
        por_autor = {}
        for canal, autores in autores_por_canal.items():
            for autor in autores:
                por_autor.setdefault(autor, []).append(indice[canal])
        return cls(canales, (por_autor[a] for a in sorted(por_autor)))

    def matriz(self):
        """Incidencia dispersa autores × canales (1 si el autor comentó en el canal)."""
        filas = np.repeat(np.arange(len(self.filas)), [len(f) for f in self.filas])
        columnas = np.fromiter((c for f in self.filas for c in f), dtype=np.int64, count=len(filas))
        datos = np.ones(len(filas), dtype=np.int32)
        return sparse.csr_matrix((datos, (filas, columnas)), shape=(len(self.filas), len(self.canales)))


def filtrar(autores_por_canal, minimo_autores=1, maximo_canales_por_autor=None):
    """Quita los canales con menos de `minimo_autores` y, si se pide, a los autores de más de N canales."""
    canales = {c: set(a) for c, a in autores_por_canal.items() if len(a) >= minimo_autores}
    if maximo_canales_por_autor is None:
        return canales
    cuenta = {}
    for autores in canales.values():
        for a in autores:
            cuenta[a] = cuenta.get(a, 0) + 1
    return {c: {a for a in autores if cuenta[a] <= maximo_canales_por_autor} for c, autores in canales.items()}


def curveball(filas, semilla, intercambios=None):
    """Baraja la bipartita conservando el grado de cada autor y de cada canal (Strona et al., 2014)."""
    azar = random.Random(semilla)
    filas = [set(f) for f in filas]
    n = len(filas)
    if n < 2:
        return [tuple(sorted(f)) for f in filas]
    for _ in range(intercambios if intercambios is not None else INTERCAMBIOS_POR_AUTOR * n):
        i, j = azar.randrange(n), azar.randrange(n)
        if i == j:
            continue
        a, b = filas[i], filas[j]
        solo_a, solo_b = a - b, b - a
        if not solo_a or not solo_b:
            continue
        comunes = a & b
        mezcla = list(solo_a | solo_b)
        azar.shuffle(mezcla)
        filas[i] = comunes | set(mezcla[: len(solo_a)])
        filas[j] = comunes | set(mezcla[len(solo_a) :])
    return [tuple(sorted(f)) for f in filas]


def proyectar(bipartita):
    """Grafo canal–canal: arista si comparten un autor; peso = coseno de Salton; distancia = 1 / peso."""
    incidencia = bipartita.matriz()
    compartidos = (incidencia.T @ incidencia).tocoo()
    grados = np.asarray(incidencia.sum(axis=0)).ravel()
    grafo = nx.Graph()
    grafo.add_nodes_from(range(len(bipartita.canales)))
    mascara = compartidos.row < compartidos.col
    for i, j, w in zip(compartidos.row[mascara], compartidos.col[mascara], compartidos.data[mascara], strict=True):
        peso = float(w / math.sqrt(grados[i] * grados[j]))
        grafo.add_edge(int(i), int(j), **{PESO: peso, DISTANCIA: 1 / peso, COMPARTIDOS: int(w)})
    return grafo


def componente_mayor(grafo):
    if grafo.number_of_edges() == 0:
        return grafo.subgraph([]).copy()
    return grafo.subgraph(max(nx.connected_components(grafo), key=len)).copy()


def louvain(grafo, semilla):
    """(comunidades, Q ponderada)."""
    if grafo.number_of_edges() == 0:
        return [], float("nan")
    comunidades = nx.community.louvain_communities(grafo, weight=PESO, resolution=1, seed=semilla)
    return comunidades, float(nx.community.modularity(grafo, comunidades, weight=PESO))


def propagacion(grafo, semilla):
    return list(nx.community.asyn_lpa_communities(grafo, weight=PESO, seed=semilla))


def etiquetas(comunidades, nodos):
    de = {n: k for k, c in enumerate(comunidades) for n in c}
    return [de[n] for n in nodos]


def nmi(comunidades_a, comunidades_b, nodos):
    from sklearn.metrics import normalized_mutual_info_score

    return float(normalized_mutual_info_score(etiquetas(comunidades_a, nodos), etiquetas(comunidades_b, nodos)))


def cruce(bipartita, objetivo):
    """Por canal: proporción de sus autores que también comentan en algún canal de `objetivo` (índices)."""
    incidencia = bipartita.matriz().tocsc()
    if not objetivo:
        return np.zeros(len(bipartita.canales))
    en_objetivo = (np.asarray(incidencia[:, sorted(objetivo)].sum(axis=1)).ravel() > 0).astype(np.int64)
    grados = np.asarray(incidencia.sum(axis=0)).ravel()
    compartidos = incidencia.T @ en_objetivo
    return np.divide(compartidos, grados, out=np.zeros(len(grados)), where=grados > 0)


def nulo(bipartita, semilla, objetivos=()):
    """Una red nula: (tamaño del componente mayor, Q de Louvain y el cruce con cada objetivo)."""
    barajada = Bipartita(bipartita.canales, curveball(bipartita.filas, semilla))
    componente = componente_mayor(proyectar(barajada))
    _, q = louvain(componente, semilla)
    return {"componente": componente.number_of_nodes(), "q": q, "cruces": [cruce(barajada, o) for o in objetivos]}


def backbone(grafo, autores_totales, grados, alfa=0.05):
    """Aristas con más autores compartidos que lo esperado por la hipergeométrica, con FDR de Benjamini-Hochberg."""
    aristas = list(grafo.edges(data=COMPARTIDOS))
    if not aristas:
        return []
    p = np.array([hypergeom.sf(w - 1, autores_totales, grados[i], grados[j]) for i, j, w in aristas])
    orden = np.argsort(p)
    limite = np.flatnonzero(p[orden] <= alfa * np.arange(1, len(p) + 1) / len(p))
    corte = limite[-1] + 1 if len(limite) else 0
    return [aristas[k][:2] for k in orden[:corte]]


def pearson_ponderado(x, y, pesos):
    x, y, pesos = (np.asarray(v, float) for v in (x, y, pesos))
    if len(x) < 3 or pesos.sum() == 0:
        return float("nan")
    mx, my = np.average(x, weights=pesos), np.average(y, weights=pesos)
    cov = np.average((x - mx) * (y - my), weights=pesos)
    var = np.average((x - mx) ** 2, weights=pesos) * np.average((y - my) ** 2, weights=pesos)
    return float(cov / math.sqrt(var)) if var > 0 else float("nan")


def asortatividad(grafo, valor):
    """Pearson ponderado entre los extremos de cada arista (en ambos sentidos), con los nodos que tienen valor."""
    x, y, w = [], [], []
    for i, j, peso in grafo.edges(data=PESO):
        if i in valor and j in valor:
            x += [valor[i], valor[j]]
            y += [valor[j], valor[i]]
            w += [peso, peso]
    return pearson_ponderado(x, y, w)


def asortatividad_permutada(grafo, valor, veces, semilla):
    """(observada, valor p de dos colas) frente a permutar el valor entre los nodos que lo tienen."""
    observada = asortatividad(grafo, valor)
    nodos, valores = list(valor), np.array(list(valor.values()))
    azar = np.random.default_rng(semilla)
    nulos = np.array(
        [asortatividad(grafo, dict(zip(nodos, azar.permutation(valores), strict=True))) for _ in range(veces)]
    )
    nulos = nulos[~np.isnan(nulos)]
    if math.isnan(observada) or not len(nulos):
        return observada, float("nan")
    centro = nulos.mean()
    p = (np.sum(np.abs(nulos - centro) >= abs(observada - centro)) + 1) / (len(nulos) + 1)
    return observada, float(p)


def spearman_con_ic(x, y, veces, semilla):
    """(rho, IC 95 % por bootstrap de las unidades, valor p, n)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 5:
        return float("nan"), (float("nan"), float("nan")), float("nan"), len(x)
    rho, p = spearmanr(x, y)
    azar = np.random.default_rng(semilla)
    replicas = []
    for _ in range(veces):
        idx = azar.integers(0, len(x), len(x))
        if np.ptp(x[idx]) and np.ptp(y[idx]):
            replicas.append(spearmanr(x[idx], y[idx])[0])
    ic = (float(np.percentile(replicas, 2.5)), float(np.percentile(replicas, 97.5))) if replicas else (math.nan,) * 2
    return float(rho), ic, float(p), len(x)
