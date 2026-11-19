"""Índice de perspicuidad de Szigriszt-Pazos, en la escala INFLESZ (Barrio-Cantalejo et al., 2008), para U3.

INFLESZ: menos de 40 muy difícil, 40 a 55 algo difícil, 55 a 65 normal, 65 a 80 bastante fácil, más de 80 muy fácil.
"""

import re
import unicodedata

PALABRA = re.compile(r"[a-záéíóúüñ]+", re.I)
ORACION = re.compile(r"[.!?]+(?:\s|$)")
FUERTES = set("aeoáéíóú")  # la í y la ú con tilde rompen el diptongo, igual que una vocal fuerte
VOCALES = set("aeiouáéíóúü")


def silabas(palabra):
    """Cuenta núcleos vocálicos: dos fuertes seguidas (hiato) cuentan dos; débil + vocal es diptongo."""
    p = palabra.lower()
    p = re.sub(r"(?<=[gq])u(?=[eiéí])", "", p)  # la u muda de "que", "gui"
    p = re.sub(r"y$", "i", p)
    cuenta, anterior = 0, ""
    for letra in p:
        if letra in VOCALES:
            if not anterior or (anterior in FUERTES and letra in FUERTES):
                cuenta += 1
            anterior = letra
        else:
            anterior = ""
    return max(1, cuenta)


def inflesz(texto):
    texto = unicodedata.normalize("NFC", texto)
    palabras = PALABRA.findall(texto)
    if not palabras:
        return None
    oraciones = max(1, len(ORACION.findall(texto.strip() + " ")))
    total_silabas = sum(silabas(p) for p in palabras)
    return 206.835 - 62.3 * total_silabas / len(palabras) - len(palabras) / oraciones
