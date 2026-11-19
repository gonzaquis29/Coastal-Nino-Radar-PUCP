"""Borra los datos de YouTube con más de 30 días (políticas de la API; docs/youtube/definicion.md, sección 5).

Incluye las respuestas crudas, los derivados por video y los estados de cada etapa. Queda solo la validación
(agregados sin ids). La sal de los seudónimos está en una variable de entorno: al borrar la última descarga, bórrala
también (el programa lo recuerda).

Uso: python -m radar.youtube.borrar [--simular] [--todo]
"""

import argparse
import contextlib
import sys

from radar import config
from radar.youtube import almacen


def borrar(simular=False, todo=False, en=None):
    objetivo = almacen.archivos() if todo else almacen.vencidos(en)
    if not simular:
        for r in objetivo:
            r.unlink()
    return objetivo


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--simular", action="store_true", help="solo lista lo que borraría")
    parser.add_argument("--todo", action="store_true", help="borra todos los datos de YouTube, vencidos o no")
    args = parser.parse_args(argv)
    with contextlib.suppress(AttributeError, ValueError):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    borrados = borrar(args.simular, args.todo)
    verbo = "Se borrarían" if args.simular else "Borrados"
    print(f"{verbo} {len(borrados)} archivo(s) de YouTube.")
    for r in borrados:
        print(f"  {r.parent.name}/{r.name}")
    if not args.simular and not almacen.archivos():
        print(f"No quedan datos de YouTube: borra también la variable de entorno {config.VARIABLE_SAL_YOUTUBE}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
