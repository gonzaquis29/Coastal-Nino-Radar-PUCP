"""Archivos: rutas seguras, escritura atómica, CSV con esquema y estado de descargas."""

import pytest

from radar.comun import archivos


def test_ruta_segura_rechaza_salir_de_la_carpeta(tmp_path):
    for nombre in ("../fuera.pdf", "a/b.pdf", "", ".oculto"):
        with pytest.raises(archivos.NombreInvalido):
            archivos.ruta_segura(tmp_path, nombre)
    assert archivos.ruta_segura(tmp_path, "comunicado-oficial-enfen-n-18-2026.pdf").parent == tmp_path


def test_csv_lf_listas_y_sin_temporales(tmp_path):
    archivos.escribir_csv(tmp_path / "a.csv", ["x", "y"], [{"x": 1, "y": {"b", "a"}}, {"x": True, "y": ["c", "d"]}])
    assert (tmp_path / "a.csv").read_bytes() == b"x,y\n1,a|b\n1,c|d\n"
    assert not list(tmp_path.glob(".tmp-*"))


def test_columna_fuera_del_esquema_es_error_y_no_pisa_el_anterior(tmp_path):
    ruta = tmp_path / "a.csv"
    archivos.escribir_csv(ruta, ["x"], [{"x": 1}])
    with pytest.raises(ValueError):
        archivos.escribir_csv(ruta, ["x"], [{"x": 2, "intrusa": 3}])
    assert ruta.read_text(encoding="utf-8") == "x\n1\n"


def test_estado_se_guarda_al_salir_aunque_haya_error(tmp_path):
    ruta = tmp_path / "estado.json"
    with pytest.raises(RuntimeError), archivos.EstadoDescargas(ruta, cada=100) as estado:
        estado.marcar("a", {"sha256": "x"})
        raise RuntimeError("corte")
    assert archivos.EstadoDescargas(ruta).get("a") == {"sha256": "x"}


def test_estado_se_guarda_cada_n_cambios(tmp_path):
    ruta = tmp_path / "estado.json"
    estado = archivos.EstadoDescargas(ruta, cada=2)
    estado.marcar("a", {})
    assert not ruta.exists()
    estado.marcar("b", {})
    assert ruta.exists()
