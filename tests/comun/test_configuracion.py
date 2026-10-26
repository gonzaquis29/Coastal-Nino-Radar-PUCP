"""Coherencia de config/*.csv con las macro-regiones del README."""

import collections

from radar import config
from radar.comun import regiones
from radar.comun.archivos import leer_csv


def test_regiones_del_readme():
    deps = regiones.deps_por_macroregion()
    assert deps["costa_norte"] == {"TUMBES", "PIURA", "LAMBAYEQUE", "LA LIBERTAD"}
    assert deps["costa_centro"] == {"ANCASH", "ICA"}
    assert deps["lima"] == {"LIMA", "CALLAO"}
    assert sum(len(v) for v in deps.values()) == 25  # 24 departamentos y Callao
    assert regiones.macroregion_de_avisos("lima") == "costa_centro"
    assert regiones.macroregion_de_avisos("otras") is None


def test_estaciones_de_referencia():
    estaciones = regiones.estaciones_costa()
    assert len(estaciones) == len({e[0] for e in estaciones}) == 21
    assert {e[1] for e in estaciones} == set(regiones.MACROREGIONES_COSTA)
    assert all(-82 < lon < -74 and -15 < lat < -3 for _, _, lon, lat in estaciones)


def test_regiones_mencionadas():
    assert regiones.regiones_mencionadas("lluvias en la costa norte y en Áncash") == {"costa_norte", "costa_centro"}
    assert regiones.regiones_mencionadas("anomalías en el Pacífico atmosférico") == set()


def test_departamentos_con_litoral():
    assert regiones.departamentos_litoral() == {
        "TUMBES",
        "PIURA",
        "LAMBAYEQUE",
        "LA LIBERTAD",
        "ANCASH",
        "LIMA",
        "CALLAO",
        "ICA",
        "AREQUIPA",
        "MOQUEGUA",
        "TACNA",
    }


def test_macroregiones_explicitas():
    assert [m for _, m in regiones.macroregiones_explicitas("Calor en la costa sur y en el norte del país")] == [
        {"otras"},
        {"costa_norte"},
    ]
    assert regiones.regiones_mencionadas("anomalías en la costa sur") == set()  # los textos oficiales no usan "otras"


def test_lista_de_lugares_del_inei():
    lugares = leer_csv(config.ARCHIVO_LUGARES)
    assert collections.Counter(f["nivel"] for f in lugares) == {"departamento": 25, "provincia": 196, "distrito": 1890}
    assert len({f["ubigeo"] for f in lugares}) == len(lugares)
    assert all(len(f["ubigeo"]) == 6 and f["ubigeo"].isdigit() for f in lugares)
    deps = {d["departamento"] for d in regiones.departamentos()}
    assert {f["departamento"] for f in lugares} == deps
    en_uso = [f for f in lugares if f["usar"] == "1"]
    assert len({f["clave"] for f in en_uso}) == len(en_uso)  # un solo lugar por nombre
    assert not any(f["clave"] == "SANTA" for f in en_uso)  # README: "se excluyen provincias con nombres ambiguos"
