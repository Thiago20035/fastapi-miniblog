from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Literal

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from .post import PostORM

Role = Literal["user", "editor", "admin"]
ROLES: tuple[str, ...] = ("user", "editor", "admin")
# Nivel de cada rol: un rol hereda los permisos de los niveles inferiores
ROLE_LEVEL = {role: level for level, role in enumerate(ROLES)}


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(
        Enum(*ROLES, name="user_role"), default="user", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    posts: Mapped[List["PostORM"]] = relationship(back_populates="user", passive_deletes=True)
