"""Actualiza todas las fuentes y reconstruye eventos.csv.   Uso (desde la raíz):  python src/actualizar.py"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import consolidar
import fuentes
import zonas

PROC = Path("data/processed")


def actualizar() -> dict:
    PROC.mkdir(parents=True, exist_ok=True)
    f_est = PROC / "estado_fuentes.json"
    estado = json.loads(f_est.read_text(encoding="utf8")) if f_est.exists() else {}
    res = {}

    def correr(nombre, fn):  # una fuente caída no debe tumbar el resto; se conserva su último dato y se declara el fallo
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
        e = estado.setdefault(nombre, {})
        try:
            r = fn()
            res[nombre] = e["n"] = r if isinstance(r, int) else len(r)
            e.update(ok=ahora, error="")
        except Exception as ex:
            res[nombre] = f"error: {type(ex).__name__}: {ex}"
            e["error"] = f"{ahora} ({type(ex).__name__})"

    correr("USGS", fuentes.sismos_usgs)
    correr("SENAMHI", fuentes.avisos_senamhi)
    correr("INDECI", fuentes.notas_indeci)
    ev = consolidar.construir()
    correr("ZONAS", lambda: zonas.construir(ev))
    res["eventos"] = len(ev)
    f_est.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf8")
    (PROC / "ultima_actualizacion.txt").write_text(datetime.now().strftime("%Y-%m-%d %H:%M"))
    return res


if __name__ == "__main__":
    print(actualizar())
