"""Pruebas sintéticas de radar.trends.cargar (CSV inventados con el formato de la exportación de la web)."""

import datetime as dt

import pytest

from radar import config
from radar.trends import cargar


def csv_trends(region, valores, inicio=dt.date(2025, 12, 28), encabezado="Semana"):
    filas = [f"{inicio + dt.timedelta(weeks=i)},{v}" for i, v in enumerate(valores)]
    return "Categoría: Todas las categorías\n\n" + f"{encabezado},El Niño: ({region})\n" + "\n".join(filas) + "\n"


def test_lee_la_exportacion_y_los_menores_que_uno():
    serie = cargar.leer_exportacion(csv_trends("Tumbes", [3, "<1", 0]), "tumbes")
    assert serie == [
        (dt.date(2025, 12, 28), 3.0, False),
        (dt.date(2026, 1, 4), 0.5, True),
        (dt.date(2026, 1, 11), 0.0, False),
    ]


def test_acepta_el_encabezado_en_ingles_y_la_libertad():
    assert cargar.leer_exportacion(csv_trends("La Libertad", [1], encabezado="Week"), "la-libertad")


def test_rechaza_otra_region():
    with pytest.raises(cargar.ExportacionInvalida):
        cargar.leer_exportacion(csv_trends("Piura", [1]), "tumbes")


def test_rechaza_un_periodo_que_no_empieza_en_enero():
    with pytest.raises(cargar.ExportacionInvalida):
        cargar.comprobar_fechas(
            cargar.leer_exportacion(csv_trends("Piura", [1, 2], inicio=dt.date(2026, 3, 1)), "piura")
        )


def test_descarta_la_semana_incompleta():
    serie = cargar.leer_exportacion(csv_trends("Piura", [1] * 47), "piura")  # hasta la semana del 15-nov
    semanas = cargar.semanas_completas(serie, exportado=dt.date(2026, 11, 21))
    assert semanas[-1][0] == dt.date(2026, 11, 8)  # la del 15-nov termina el 21-nov, después del corte
    assert semanas[0][0] == dt.date(2025, 12, 28)


def test_g1_cuenta_departamentos_con_dato_en_la_mitad_de_las_semanas():
    llena = [(dt.date(2026, 1, 4) + dt.timedelta(weeks=i), 5.0, False) for i in range(10)]
    vacia = [(s, 0.5, True) for s, _, _ in llena]
    exportado = dt.date(2026, 11, 16)
    series = {d: [(exportado, vacia if d == "tumbes" else llena)] for d in config.DEPARTAMENTOS_TRENDS}
    filas = {f["criterio"][:2]: f for f in cargar.medir(series)}
    assert filas["G1"]["valor"] == 3 and filas["G1"]["pasa"]
    assert "G2" not in filas


def test_g2_spearman_entre_dos_exportaciones():
    a = [(dt.date(2026, 1, 4) + dt.timedelta(weeks=i), float(i), False) for i in range(10)]
    b = [(s, v * 2 + 1, m) for s, v, m in a]
    series = {d: [(dt.date(2026, 11, 16), a), (dt.date(2026, 11, 21), b)] for d in config.DEPARTAMENTOS_TRENDS}
    g2 = next(f for f in cargar.medir(series) if f["criterio"].startswith("G2"))
    assert g2["valor"] == 1.0 and g2["pasa"]


def test_spearman_con_empates():
    assert cargar.spearman([1, 2, 2, 3], [1, 2, 2, 3]) == pytest.approx(1.0)
    assert cargar.spearman([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)
