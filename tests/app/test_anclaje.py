"""«Alta» anclada al tema (docs/app/definicion.md, sección 13), con resultados y notas sintéticos."""

from radar.app import servicio as sv
from radar.app import tema_clima as tc
from radar.app import validar_anclaje as va
from radar.comun import dominio
from radar.nlp import semaforo
from radar.noticias import externa


def resultado(banda=semaforo.CERCANO, tipo="recomendacion"):
    return {"origen": "distancia", "banda": banda, "tipo_parrafo": tipo, "color_reglas": semaforo.SIN_AFIRMACIONES,
            "color": semaforo.COLOR_DE_BANDA[banda], "umbrales": {"con_color": True}}  # fmt: skip


def test_palabras_especificas_sin_las_genericas():
    assert dominio.palabras_especificas("Gobierno declara emergencia y alerta en la costa") == set()
    assert dominio.palabras_especificas("Emergencia por lluvias en Piura") == {"lluvi"}


def test_anclaje_baja_a_media_solo_recomendacion_sin_palabras_especificas():
    r = sv.anclar(resultado(), "Gobierno declara estado de emergencia por la inseguridad", activo=True)
    assert r["banda"] == semaforo.INTERMEDIO and r["anclaje"] == "recomendacion_general"
    assert r["color"] == semaforo.COLOR_DE_BANDA[semaforo.INTERMEDIO]
    # con una palabra específica, nombrando el fenómeno o con otro párrafo, no cambia
    assert sv.anclar(resultado(), "Emergencia por lluvias en Piura", activo=True)["banda"] == semaforo.CERCANO
    assert sv.anclar(resultado(), "Emergencia ante El Niño costero", activo=True)["banda"] == semaforo.CERCANO
    assert sv.anclar(resultado(tipo="pronostico"), "Alerta de emergencia", activo=True)["banda"] == semaforo.CERCANO
    assert sv.anclar(resultado(semaforo.INTERMEDIO), "Alerta", activo=True)["banda"] == semaforo.INTERMEDIO


def test_anclaje_apagado_no_cambia_nada():
    assert sv.anclar(resultado(), "Alerta de emergencia", activo=False)["banda"] == semaforo.CERCANO


def test_fecha_un_anio_despues_hasta_el_corte():
    assert va.fecha_2026({"fecha_publicacion": "2025-10-03T10:00:00"}) == "2026-10-03"
    assert va.fecha_2026({"fecha_publicacion": "2025-12-20T10:00:00"}) == "2026-11-20"
    assert va.fecha_2026({"fecha_publicacion": "2026-09-05T10:00:00"}) == "2026-09-05"


def test_externa_solo_octubre_a_diciembre_de_2025():
    assert externa.en_fechas({"fecha_publicacion": "2025-10-01T00:00:00"})
    assert externa.en_fechas({"fecha_publicacion": "2025-12-31T23:00:00"})
    assert not externa.en_fechas({"fecha_publicacion": "2025-09-30T23:00:00"})
    assert not externa.en_fechas({"fecha_publicacion": "2026-01-01T00:00:00"})
    numeros = externa.numeros_andina()
    assert numeros.step == externa.ANDINA_CADA and numeros.stop == externa.ANDINA_HASTA


def test_criterios_v1_compara_con_hoy():
    # 200 negativos difíciles: hoy 6 «Alta», con el anclaje 2 (1 % y un tercio de hoy) -> pasa
    duros = [(True, i < 6, i < 2) for i in range(200)]
    otros = [(True, False, False)] * 200
    tema = [(True, True, True)] * 150
    c = {tc.DURO: duros, tc.OTRO: otros, tc.CLIMA: tema, tc.TEMA: tema}
    filas = {f["criterio"][:2]: f for f in va.criterios(c, None, "")}
    assert filas["V1"]["pasa"] and filas["V3"]["pasa"] and filas["V4"]["pasa"]
    c[tc.DURO] = [(True, i < 6, i < 4) for i in range(200)]  # dos tercios de hoy -> no pasa
    assert not {f["criterio"][:2]: f for f in va.criterios(c, None, "")}["V1"]["pasa"]


def test_grupo_chico_es_informativo():
    pocos = [(True, True, False)] * 10  # todas sus «Alta» bajan, pero son menos de 100
    nada = [(True, False, False)] * 200
    c = {tc.DURO: nada, tc.OTRO: nada, tc.CLIMA: [(True, True, True)] * 150, tc.TEMA: pocos}
    v5 = {f["criterio"][:2]: f for f in va.criterios(c, None, "")}["V5"]
    assert v5["pasa"] and "informativo" in v5["prueba"]


def test_sinteticos_completos_y_sin_el_fenomeno():
    assert len(va.OTRO_TEMA_GENERICO) == len(va.OTRO_TEMA_ESPECIFICO_CON_OTRO_SENTIDO) == 10
    assert len(va.DEL_TEMA_SIN_NINO) == 20
    todos = va.OTRO_TEMA_GENERICO + va.OTRO_TEMA_ESPECIFICO_CON_OTRO_SENTIDO + va.DEL_TEMA_SIN_NINO
    assert not any(dominio.nombra_el_fenomeno(t) for t in todos)
    assert not any(dominio.palabras_especificas(t) for t in va.OTRO_TEMA_GENERICO)
