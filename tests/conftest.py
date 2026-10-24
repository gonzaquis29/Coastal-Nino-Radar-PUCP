"""Configuración común de las pruebas."""

import pytest

from radar import config


@pytest.fixture
def sin_esperas(monkeypatch):
    """Pausas y esperas a cero para probar reintentos sin dormir."""
    monkeypatch.setattr(config, "PAUSA_POR_HOST", 0)
    monkeypatch.setattr(config, "ESPERA_BASE", 0)
