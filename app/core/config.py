"""Configuración central leída de variables de entorno.

Se importa antes que `db.py` y `security.py`, así el `.env` ya está cargado
cuando esos módulos leen sus valores (antes `load_dotenv()` corría tarde, en main.py).
"""
import os
import warnings

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./blog.db")
    SQL_ECHO: bool = os.getenv("SQL_ECHO", "0") == "1"

    # Acepta JWT_SECRET (nombre de la clase) o SECRET_KEY (nombre anterior del repo)
    JWT_SECRET: str = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY") or ""
    JWT_ALG: str = os.getenv("JWT_ALG", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "3"))


settings = Settings()

if not settings.JWT_SECRET:
    # Sólo para desarrollo: sin secreto en el entorno, generamos uno por proceso.
    # Los tokens dejan de valer al reiniciar el servidor. En producción, definir JWT_SECRET.
    import secrets

    settings.JWT_SECRET = secrets.token_urlsafe(48)
    warnings.warn("JWT_SECRET no definido: se generó uno temporal (sólo desarrollo).", stacklevel=1)
