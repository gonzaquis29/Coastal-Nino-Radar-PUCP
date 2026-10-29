"""Candado entre procesos, reparación de CSV cortados y antisuspensión (sin red)."""

import json
import os
import subprocess
import sys

import pytest

from radar.comun.archivos import anexar_csv, leer_csv, reparar_csv
from radar.comun.candado import Ocupado, candado, inicio_proceso
from radar.comun.energia import sin_suspension


def test_un_segundo_proceso_no_entra_y_se_libera_al_salir(tmp_path):
    ruta = tmp_path / "red.lock"
    with candado("primero", ruta):
        assert json.loads(ruta.read_text(encoding="utf-8"))["pid"] == os.getpid()
        with pytest.raises(Ocupado, match="primero"), candado("segundo", ruta):
            pass
    assert not ruta.exists()


def test_el_candado_de_un_proceso_que_ya_no_existe_se_toma(tmp_path):
    hijo = subprocess.Popen([sys.executable, "-c", "pass"])
    hijo.wait()
    ruta = tmp_path / "red.lock"
    ruta.write_text(json.dumps({"pid": hijo.pid, "inicio": 1, "comando": "cortado"}), encoding="utf-8")
    with candado("nuevo", ruta):
        assert json.loads(ruta.read_text(encoding="utf-8"))["comando"] == "nuevo"


def test_mismo_pid_con_otra_hora_de_inicio_es_otro_proceso(tmp_path):
    ruta = tmp_path / "red.lock"
    propio = inicio_proceso(os.getpid())
    ruta.write_text(json.dumps({"pid": os.getpid(), "inicio": (propio or 0) + 12345, "comando": "x"}), "utf-8")
    if propio:  # en Windows se compara la hora de creación; en otros sistemas no se conoce
        with candado("nuevo", ruta):
            pass


def test_un_proceso_vivo_conserva_el_candado(tmp_path):
    hijo = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        ruta = tmp_path / "red.lock"
        ruta.write_text(json.dumps({"pid": hijo.pid, "inicio": inicio_proceso(hijo.pid), "comando": "vivo"}), "utf-8")
        with pytest.raises(Ocupado, match="vivo"), candado("nuevo", ruta):
            pass
    finally:
        hijo.kill()


@pytest.mark.parametrize("cola", ["medio,1,a", "medio,1", ""])
def test_reparar_quita_solo_la_linea_a_medias(tmp_path, cola):
    ruta = tmp_path / "notas.csv"
    anexar_csv(ruta, ("medio", "id", "x"), [{"medio": "rpp", "id": "1", "x": "a"}])
    with open(ruta, "a", encoding="utf-8", newline="") as archivo:
        archivo.write(cola)
    assert reparar_csv(ruta, ("medio", "id", "x")) == (1 if cola else 0)
    anexar_csv(ruta, ("medio", "id", "x"), [{"medio": "rpp", "id": "2", "x": "b"}])
    assert [f["id"] for f in leer_csv(ruta)] == ["1", "2"]


def test_anexar_a_un_archivo_que_quedo_vacio_escribe_el_encabezado(tmp_path):
    ruta = tmp_path / "notas.csv"
    ruta.write_bytes(b"")
    anexar_csv(ruta, ("medio", "id"), [{"medio": "rpp", "id": "1"}])
    assert leer_csv(ruta) == [{"medio": "rpp", "id": "1"}]


def test_sin_suspension_no_falla():
    with sin_suspension():
        pass
