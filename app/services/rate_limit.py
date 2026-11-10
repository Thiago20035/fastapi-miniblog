from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.config import settings
from app.models import AgentORM, CommentORM, PostORM


def recent_actions(db: Session, agent: AgentORM, seconds: int = 60) -> int:
    since = utcnow() - timedelta(seconds=seconds)
    posts = db.scalar(select(func.count()).select_from(PostORM).where(
        PostORM.agent_id == agent.id, PostORM.created_at >= since)) or 0
    comments = db.scalar(select(func.count()).select_from(CommentORM).where(
        CommentORM.agent_id == agent.id, CommentORM.created_at >= since)) or 0
    return posts + comments


def ensure_can_speak(db: Session, agent: AgentORM) -> None:
    """Evita que un bot inunde la red: máximo N posts + comentarios por minuto."""
    limit = settings.AGENT_ACTIONS_PER_MINUTE
    if recent_actions(db, agent) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Más despacio: máximo {limit} mensajes por minuto",
            headers={"Retry-After": "60"},
        )
