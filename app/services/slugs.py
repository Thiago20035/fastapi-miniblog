import re
import unicodedata
from typing import Callable

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


def slugify(text: str, max_length: int = 60) -> str:
    """'Programación en Python!' -> 'programacion-en-python'"""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_length].strip("-") or "sin-titulo"


def unique_slug(text: str, exists: Callable[[str], bool], max_length: int = 60) -> str:
    """Genera un slug y, si ya está tomado, le agrega -2, -3, ..."""
    base = slugify(text, max_length)
    slug, n = base, 2
    while exists(slug):
        suffix = f"-{n}"
        slug = f"{base[: max_length - len(suffix)].rstrip('-')}{suffix}"
        n += 1
    return slug
