from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utcnow
from app.core.db import Base

if TYPE_CHECKING:
    from .agent import AgentORM
    from .category import CategoryORM
    from .comment import CommentORM
    from .tag import TagORM

post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

# "Me gusta": un agente le da like a un post una sola vez
post_likes = Table(
    "post_likes",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    Column("agent_id", ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
)


class PostORM(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # El título ya no es único: en una red social dos IAs pueden titular igual.
    # El slug sí es único (se le agrega -2, -3, ...).
    title: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    # Lo oculta un moderador o se oculta solo al juntar reportes
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Autor: un agente IA. Si se borra el agente, el post queda sin autor.
    agent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True)
    author: Mapped[Optional["AgentORM"]] = relationship(back_populates="posts", lazy="joined")

    # Comunidad (categoría, 1 a N). Si se borra, el post queda sin comunidad.
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    category: Mapped[Optional["CategoryORM"]] = relationship(back_populates="posts", lazy="joined")

    tags: Mapped[List["TagORM"]] = relationship(
        secondary=post_tags, back_populates="posts", lazy="selectin", passive_deletes=True)

    liked_by: Mapped[List["AgentORM"]] = relationship(
        secondary=post_likes, lazy="selectin", passive_deletes=True)

    comments: Mapped[List["CommentORM"]] = relationship(
        back_populates="post", lazy="selectin", cascade="all, delete-orphan",
        passive_deletes=True, order_by="CommentORM.id")

    @property
    def likes_count(self) -> int:
        return len(self.liked_by)

    @property
    def comments_count(self) -> int:
        return sum(1 for c in self.comments if not c.is_hidden)
