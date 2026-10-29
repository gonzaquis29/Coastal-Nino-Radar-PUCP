"""Mientras corre un proceso largo, pide a Windows que no suspenda el equipo por inactividad. El pedido es del proceso:
se libera al salir y no cambia la configuración de energía. No evita la suspensión al cerrar la tapa ni al apagar."""

import contextlib
import ctypes
import sys

_CONTINUO = 0x80000000  # ES_CONTINUOUS
_SISTEMA = 0x00000001  # ES_SYSTEM_REQUIRED


@contextlib.contextmanager
def sin_suspension():
    if sys.platform != "win32":
        yield
        return
    k = ctypes.windll.kernel32
    k.SetThreadExecutionState(_CONTINUO | _SISTEMA)
    try:
        yield
    finally:
        k.SetThreadExecutionState(_CONTINUO)
