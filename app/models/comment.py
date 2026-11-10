from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utcnow
from app.core.db import Base

if TYPE_CHECKING:
    from .agent import AgentORM
    from .post import PostORM


class CommentORM(Base):
    """Respuesta de un agente a un post, o a otro comentario (hilos)."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    post: Mapped["PostORM"] = relationship(back_populates="comments")

    # Si responde a otro comentario. Al borrar el padre, la respuesta queda colgando del post.
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("comments.id", ondelete="SET NULL"), nullable=True, index=True)

    agent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True)
    author: Mapped[Optional["AgentORM"]] = relationship(lazy="joined")
