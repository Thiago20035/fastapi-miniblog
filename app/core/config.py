"""Configuración central leída de variables de entorno.

Se importa antes que `db.py` y `security.py`, así el `.env` ya está cargado
cuando esos módulos leen sus valores.
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

    # ---------------------------------------------------------------- Red social de IAs
    # Cuántos posts + comentarios puede publicar cada agente por minuto (anti-spam)
    AGENT_ACTIONS_PER_MINUTE: int = int(os.getenv("AGENT_ACTIONS_PER_MINUTE", "10"))
    # Cuántos agentes puede registrar cada persona
    MAX_AGENTS_PER_USER: int = int(os.getenv("MAX_AGENTS_PER_USER", "5"))
    # Con esta cantidad de reportes abiertos, un post o comentario se oculta solo
    AUTO_HIDE_REPORTS: int = int(os.getenv("AUTO_HIDE_REPORTS", "3"))

    # Cerebro de los agentes del sitio: "auto" (Claude si hay ANTHROPIC_API_KEY), "claude" u "offline"
    AI_BRAIN: str = os.getenv("AI_BRAIN", "auto").lower()
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")


settings = Settings()

# Algunos servicios (Heroku, versiones viejas de Render) dan "postgres://", que SQLAlchemy 2 ya no acepta
if settings.DATABASE_URL.startswith("postgres://"):
    settings.DATABASE_URL = "postgresql://" + settings.DATABASE_URL[len("postgres://"):]

if not settings.JWT_SECRET:
    # Sólo para desarrollo: sin secreto en el entorno, generamos uno por proceso.
    # Los tokens dejan de valer al reiniciar el servidor. En producción, definir JWT_SECRET.
    import secrets

    settings.JWT_SECRET = secrets.token_urlsafe(48)
    warnings.warn("JWT_SECRET no definido: se generó uno temporal (sólo desarrollo).", stacklevel=1)
