"""Candado entre procesos: un solo proceso a la vez pide páginas, para que el ritmo por host (config.PAUSA_POR_HOST) se
cumpla también entre procesos (recolección diaria, histórico, recálculo, pruebas de viabilidad, corpus oficial).

El archivo guarda el pid, la hora de inicio del proceso y el comando. Si el proceso que lo tomó ya no existe (se cortó
o se apagó el equipo), el candado se toma igual. La hora de inicio evita confundirlo con otro proceso que, tras un
reinicio, reciba el mismo pid.
"""

import contextlib
import ctypes
import json
import os
import sys

from radar import config
from radar.comun.texto import ahora


class Ocupado(RuntimeError):
    """Otro proceso vivo tiene el candado."""


# ---------------------------------------------------------------- procesos (Windows sin os.kill: lo terminaría)
_CONSULTA_LIMITADA = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
_SIGUE_ACTIVO = 259  # STILL_ACTIVE
_ACCESO_DENEGADO = 5


def _kernel32():
    from ctypes import wintypes

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.restype = wintypes.HANDLE
    k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    k.GetProcessTimes.argtypes = (wintypes.HANDLE, *(ctypes.POINTER(ctypes.c_ulonglong) for _ in range(4)))
    k.CloseHandle.argtypes = (wintypes.HANDLE,)
    return k


def _inicio_windows(pid):
    """Hora de creación del proceso (en unidades de 100 ns), None si no existe, 0 si existe pero no se puede leer."""
    k = _kernel32()
    manija = k.OpenProcess(_CONSULTA_LIMITADA, False, pid)
    if not manija:
        return 0 if ctypes.get_last_error() == _ACCESO_DENEGADO else None
    try:
        codigo = ctypes.c_ulong()  # DWORD
        if not k.GetExitCodeProcess(manija, ctypes.byref(codigo)) or codigo.value != _SIGUE_ACTIVO:
            return None
        creado, salida, nucleo, usuario = (ctypes.c_ulonglong() for _ in range(4))
        if not k.GetProcessTimes(manija, *(ctypes.byref(x) for x in (creado, salida, nucleo, usuario))):
            return 0
        return creado.value
    finally:
        k.CloseHandle(manija)


def inicio_proceso(pid):
    """Huella de inicio del proceso pid (None si no existe; 0 si existe y no se pudo leer)."""
    if sys.platform == "win32":
        return _inicio_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        return 0
    return 0


def vivo(datos):
    """El proceso que tomó el candado sigue en marcha (mismo pid y misma hora de inicio)."""
    inicio = inicio_proceso(int(datos.get("pid", 0)))
    if inicio is None:
        return False
    return not inicio or not datos.get("inicio") or inicio == datos["inicio"]


# ---------------------------------------------------------------- candado


def _leer(ruta):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _crear(ruta, datos):
    descriptor = os.open(ruta, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False)
        archivo.flush()
        os.fsync(archivo.fileno())


@contextlib.contextmanager
def candado(comando, ruta=None):
    """Toma el candado mientras dura el bloque; si otro proceso vivo lo tiene, lanza Ocupado."""
    ruta = ruta or config.ARCHIVO_CANDADO
    ruta.parent.mkdir(parents=True, exist_ok=True)
    datos = {
        "pid": os.getpid(),
        "inicio": inicio_proceso(os.getpid()),
        "comando": comando,
        "desde": ahora().isoformat(),
    }
    for _ in range(2):
        try:
            _crear(ruta, datos)
            break
        except FileExistsError:
            otro = _leer(ruta)
            if otro and vivo(otro):
                raise Ocupado(f"{otro.get('comando')} (pid {otro.get('pid')}, desde {otro.get('desde')})") from None
            with contextlib.suppress(FileNotFoundError):
                os.remove(ruta)  # de un proceso que ya no existe
    else:
        raise Ocupado("otro proceso tomó el candado al mismo tiempo")
    try:
        yield
    finally:
        if _leer(ruta).get("pid") == datos["pid"]:
            with contextlib.suppress(FileNotFoundError):
                os.remove(ruta)


def exclusivo(comando):
    """Decorador para el main de un proceso que pide páginas: si otro lo está haciendo, avisa y sale con código 2."""

    def decorar(main):
        def envuelto(*args, **kwargs):
            try:
                with candado(comando):
                    return main(*args, **kwargs)
            except Ocupado as e:
                print(f"Otro proceso está pidiendo páginas: {e}. Espera a que termine (o córtalo) y vuelve a correr.")
                return 2

        return envuelto

    return decorar
