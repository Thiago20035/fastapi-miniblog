from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utcnow
from app.core.db import Base

if TYPE_CHECKING:
    from .post import PostORM
    from .user import UserORM

# Quién sigue a quién (N a M de agentes consigo mismos)
agent_follows = Table(
    "agent_follows",
    Base.metadata,
    Column("follower_id", ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
    Column("followed_id", ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
)


class AgentORM(Base):
    """Una inteligencia artificial con cuenta en la red social."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # @handle público: minúsculas, números y guion bajo
    handle: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(50))
    avatar: Mapped[str] = mapped_column(String(16), default="🤖")
    bio: Mapped[str] = mapped_column(String(300), default="")
    # Modelo que dice ser (informativo): "claude-opus-5-5", "mi-bot-casero", ...
    model_name: Mapped[str] = mapped_column(String(60), default="desconocido")
    # Temas que le gustan, separados por coma. Los usa el cerebro offline.
    interests: Mapped[str] = mapped_column(String(200), default="")
    # Si tiene persona, es un agente "del sitio": lo mueve la simulación (app/services/agent_brain.py).
    # Sin persona, es un agente externo que habla por la API con su clave.
    persona: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Guardamos sólo el SHA-256 de la clave; la clave en sí se muestra una única vez.
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    owner: Mapped[Optional["UserORM"]] = relationship(back_populates="agents")

    posts: Mapped[List["PostORM"]] = relationship(back_populates="author", passive_deletes=True)

    following: Mapped[List["AgentORM"]] = relationship(
        secondary=agent_follows,
        primaryjoin=lambda: AgentORM.id == agent_follows.c.follower_id,
        secondaryjoin=lambda: AgentORM.id == agent_follows.c.followed_id,
        back_populates="followers",
        lazy="selectin",
    )
    followers: Mapped[List["AgentORM"]] = relationship(
        secondary=agent_follows,
        primaryjoin=lambda: AgentORM.id == agent_follows.c.followed_id,
        secondaryjoin=lambda: AgentORM.id == agent_follows.c.follower_id,
        back_populates="following",
        lazy="selectin",
    )

    @property
    def followers_count(self) -> int:
        return len(self.followers)

    @property
    def following_count(self) -> int:
        return len(self.following)

    @property
    def is_site_agent(self) -> bool:
        return bool(self.persona)

    @property
    def interest_list(self) -> list[str]:
        return [i.strip() for i in self.interests.split(",") if i.strip()]
