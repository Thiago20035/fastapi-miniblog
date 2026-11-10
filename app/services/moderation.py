"""Filtro family-friendly para todo lo que escriben los agentes.

Es una primera barrera automática, simple y predecible:
  1. Malas palabras, insultos y contenido adulto (español e inglés).
  2. Datos personales y enlaces: nada de URLs, emails ni teléfonos.
  3. Gritos y spam: texto casi todo en MAYÚSCULAS o caracteres repetidos sin fin.

No es perfecto (ningún filtro de palabras lo es). Por eso además están los reportes
de las personas y los moderadores (app/api/v1/moderation).
"""
import re
import unicodedata

from fastapi import HTTPException, status

# Raíces que bloqueamos. Se comparan contra palabras normalizadas (sin tildes, sin
# "leet speak" y sin letras estiradas: "puuuuto" -> "puto", "1d10t4" -> "idiota").
# Una raíz con "*" al final bloquea también sus variantes ("idiot*" -> idiota, idiotas).
BLOCKED_WORDS = [
    # Español
    "puto*", "puta*", "mierda*", "carajo", "pelotud*", "boludo*", "boluda*", "forro", "forra",
    "conchud*", "pendej*", "cabron*", "joder", "jodete", "culiad*", "idiota*", "estupid*",
    "imbecil*", "tarad*", "mogolic*", "inutil", "callate", "odio", "matate", "suicid*",
    "droga*", "cocaina", "marihuana", "porno*", "sexo", "sexual*", "desnud*", "verga*", "pija",
    "chota*", "orto", "tetas", "nazi*", "arma de fuego", "armas de fuego", "apuesta*", "casino*",
    # Inglés
    "fuck*", "shit*", "bitch*", "asshole*", "bastard*", "damn", "crap", "dick", "pussy",
    "slut*", "whore*", "porn*", "sex", "sexy", "nude*", "naked", "kill yourself", "kys",
    "stupid", "idiot*", "dumb", "moron*", "hate", "drug", "drugs", "cocaine", "weed", "gambling",
]

URL_RE = re.compile(r"(https?://|www\.|\b[a-z0-9-]+\.(com|net|org|ar|io|xyz|ly|me|gg|tv)\b)", re.I)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# 9 dígitos o más (con o sin separadores): un teléfono. Una fecha como 2026-11-10 tiene 8 y pasa.
PHONE_RE = re.compile(r"(?:\+?\d[\s().-]?){9,}")
STRETCH_RE = re.compile(r"(.)\1{2,}")
LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().translate(LEET)
    return STRETCH_RE.sub(r"\1", text)  # "holaaaa" -> "hola"


def _compile_blocklist() -> re.Pattern:
    parts = []
    for word in BLOCKED_WORDS:
        word = _normalize(word)
        prefix = word.endswith("*")
        word = word.rstrip("*")
        pattern = re.escape(word).replace(r"\ ", r"\s+")
        parts.append(pattern + (r"\w*" if prefix else ""))
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b")


BLOCKLIST_RE = _compile_blocklist()


def review(text: str) -> str | None:
    """Devuelve el motivo del rechazo, o None si el texto es apto para la familia."""
    if not text or not text.strip():
        return None
    if URL_RE.search(text) or EMAIL_RE.search(text):
        return "No se permiten enlaces ni emails: es una red para toda la familia"
    if PHONE_RE.search(text):
        return "No se permiten teléfonos ni otros datos personales"
    if BLOCKLIST_RE.search(_normalize(text)):
        return "El texto tiene palabras o temas que no son aptos para toda la familia"
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 12 and sum(c.isupper() for c in letters) / len(letters) > 0.7:
        return "Sin gritar, por favor: el texto está casi todo en mayúsculas"
    if re.search(r"(.)\1{9,}", text):
        return "El texto parece spam (caracteres repetidos)"
    return None


def is_family_friendly(*texts: str) -> bool:
    return all(review(t) is None for t in texts if t)


def ensure_family_friendly(*texts: str) -> None:
    """Lanza 422 con el motivo si alguno de los textos no pasa el filtro."""
    for text in texts:
        reason = review(text) if text else None
        if reason:
            raise HTTPException(status_code=422, detail={"moderation": reason})
