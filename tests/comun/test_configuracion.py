"""Coherencia de config/*.csv con las macro-regiones del README."""

from radar.comun import regiones


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
