"""Criterios de la memoria de la API (docs/app/definicion.md, sección 16)."""

import numpy as np

from radar.app import validar_memoria as vm


def test_sinteticos_y_umbrales_fijados():
    assert len(vm.TEXTOS) == 40 and len(set(vm.CONSULTAS)) == 20
    assert (vm.MEMORIA_MAXIMA, vm.PICO_MAXIMO, vm.LENTITUD_MAXIMA) == (1000, 1100, 1.10)


def test_huella_no_depende_del_orden_de_los_conjuntos():
    assert vm.huella({"a": {"x", "y", "z"}, "b": (1, 2)}) == vm.huella({"b": [1, 2], "a": ["x", "y", "z"]})
    assert vm.huella([1, 2]) != vm.huella([2, 1])


def test_k1_exige_tokens_y_vectores_iguales():
    a, igual = {"tokens": {"m": ["1", "2"]}}, np.zeros((2, 2))
    assert vm.k1(a, a, [(igual, igual)])["pasa"]
    assert not vm.k1(a, {"tokens": {"m": ["1", "3"]}}, [(igual, igual)])["pasa"]
    assert not vm.k1(a, a, [(igual, igual + 1e-3)])["pasa"]


def test_k5_usa_el_peor_pico_y_k6_la_lentitud_relativa():
    def datos(pico, verificar):
        api = {"residente": 900, "pico": 1000, "verificar": verificar}
        return {"arranques": [{"arranque": 5, "primera": 2}] * 3, "apis": [api, api, api | {"pico": pico}]}

    k5, k6 = vm.k5_k6(datos(1000, 0.1), datos(1200, 0.105))
    assert not k5["pasa"] and k6["pasa"]
    k5, k6 = vm.k5_k6(datos(1000, 0.1), datos(1050, 0.12))
    assert k5["pasa"] and not k6["pasa"]
