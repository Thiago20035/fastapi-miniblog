from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.core.db import Base

ReportStatus = Literal["open", "hidden", "dismissed"]
REPORT_STATUSES = ("open", "hidden", "dismissed")


class ReportORM(Base):
    """Una persona avisa que un post o comentario no es apto para la familia."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reason: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(
        Enum(*REPORT_STATUSES, name="report_status"), default="open", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    reporter_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    # Exactamente uno de los dos
    post_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), nullable=True, index=True)
    comment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True)
