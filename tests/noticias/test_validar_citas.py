"""Pruebas sintéticas de la validación del arreglo de citas por número."""

import types

from radar.noticias import validar_citas as v

CORPUS = types.SimpleNamespace(
    comunicados=[{"id": "c1", "fecha_emision": "2026-01-15"}, {"id": "c2", "fecha_emision": "2026-05-01"}],
    comunicado_vigente=lambda fecha: {"id": "c2"} if fecha >= "2026-05-01" else {"id": "c1"},
)


def test_ids_por_nivel():
    celda = "c1:numero|c2:enlace|c3:proximo"
    assert v.ids(celda, "numero") == {"c1"}
    assert v.ids(celda, "otros") == {"c2", "c3"}
    assert v.ids("") == set()


def test_con_numero_excluye_las_reservadas_para_t5():
    notas = [
        {"medio": "a", "id": "1", "comunicados": "c1:numero", "sobre_nino": "1"},  # sin ver: T5
        {"medio": "a", "id": "2", "comunicados": "c1:numero", "sobre_nino": "1"},
        {"medio": "a", "id": "3", "comunicados": "c1:numero", "sobre_nino": "0"},
        {"medio": "a", "id": "4", "comunicados": "c1:enlace", "sobre_nino": "0"},
    ]
    assert [n["id"] for n in v.con_numero(notas, {("a", "2")})] == ["2", "3"]


def test_coherencia_temporal():
    assert v.coherente("c1", "2026-02-01", CORPUS)  # vigente
    assert v.coherente("c1", "2026-03-10", CORPUS)  # 54 días, sigue vigente
    assert not v.coherente("c1", "2026-05-20", CORPUS)  # 125 días y ya no es el vigente
    assert not v.coherente("c1", "2026-08-01", CORPUS)  # 198 días y no vigente
    assert not v.coherente("c2", "2026-02-01", CORPUS)  # citado antes de emitirse
    assert not v.coherente("cx", "2026-02-01", CORPUS)


def test_criterios_cuentan_coherencia_y_retencion():
    nota = {"fecha_publicacion": "2026-02-01T10:00", "sobre_nino": "0"}
    casos = [
        (nota, {"antes": {"c1"}, "despues": {"c1"}, "otras": {"c1"}}),
        (nota, {"antes": {"c2"}, "despues": set(), "otras": set()}),
    ]
    r2, r3, r4 = v.criterios(casos, CORPUS)
    assert (r2["valor"], r2["pasa"]) == ("1/1", True)
    assert (r3["valor"], r3["pasa"]) == ("1/1", True)
    assert r4["valor"] == 1 and "otros temas" in r4["detalle"]
