from datetime import datetime, timezone


def utcnow() -> datetime:
    """Hora UTC sin zona horaria.

    SQLite guarda las fechas sin zona; usando siempre UTC "naive" las comparaciones
    (por ejemplo, el límite de mensajes por minuto) dan igual en SQLite y en PostgreSQL.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
