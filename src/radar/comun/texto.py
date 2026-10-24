"""Texto y fechas: normalización, comparación entre fuentes y fechas en español y en ISO 8601 (−05:00)."""

import datetime as dt
import hashlib
import re
import unicodedata

from radar.config import LIMA

MESES = {
    m: i + 1
    for i, m in enumerate(
        "enero febrero marzo abril mayo junio julio agosto setiembre octubre noviembre diciembre".split()
    )
}
MESES["septiembre"] = 9
MESES_CORTOS = {nombre[:3].capitalize(): numero for nombre, numero in MESES.items()}  # Ene, Feb, …, Set, Sep, …
_MES = "|".join(MESES)


def norm(texto):
    """Espacios simples, sin espacios duros ni guiones blandos, en forma NFC."""
    texto = unicodedata.normalize("NFC", texto or "").replace("\u00a0", " ").replace("\u00ad", "")
    return re.sub(r"\s+", " ", texto).strip()


def sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def clave(texto):
    """Minúsculas, sin tildes ni signos: para comparar el mismo texto venido de dos fuentes."""
    return re.sub(r"[^a-z0-9]+", " ", sin_tildes(texto.lower())).strip()


def sha1_corto(texto):
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:10]


def fecha_es(texto):
    """'16 octubre 2026', '15 de enero de 2026' → '2026-10-16'; None si no hay fecha."""
    m = re.search(rf"(\d{{1,2}})\s+(?:de\s+)?({_MES})\s+(?:de\s+|del\s+)?(\d{{4}})", texto or "", re.I)
    return f"{int(m.group(3)):04d}-{MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}" if m else None


def fecha_hora_es(texto):
    """'Viernes , 23 de Octubre de 2026 a las 00:00 horas' → '2026-10-23T00:00:00-05:00' (o solo la fecha)."""
    m = re.search(r"(\d{1,2}) de (\w+)\s+de (\d{4})(?: a las\s+(\d{1,2}):(\d{2}))?", norm(texto), re.I)
    if not m or m.group(2).lower() not in MESES:
        return None
    fecha = f"{m.group(3)}-{MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    return fecha + (f"T{int(m.group(4)):02d}:{m.group(5)}:00-05:00" if m.group(4) else "")


def a_lima(texto):
    """ISO 8601 con zona → −05:00. Sin zona se asume UTC (solo se usa con date_gmt de WordPress)."""
    texto = (texto or "").strip()
    if not texto:
        return ""
    fecha = dt.datetime.fromisoformat(texto.replace("Z", "+00:00"))
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=dt.UTC)
    return fecha.astimezone(LIMA).isoformat(timespec="seconds")


def ahora():
    return dt.datetime.now(LIMA).replace(microsecond=0)
