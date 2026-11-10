from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.report import ReportStatus


class ReportCreate(BaseModel):
    """Una persona avisa que algo no es apto. Se manda post_id o comment_id (uno solo)."""

    post_id: Optional[int] = Field(None, ge=1)
    comment_id: Optional[int] = Field(None, ge=1)
    reason: str = Field(..., min_length=3, max_length=300, examples=["Lenguaje no apto para chicos"])

    @model_validator(mode="after")
    def exactly_one_target(self):
        if (self.post_id is None) == (self.comment_id is None):
            raise ValueError("Mandá post_id o comment_id (uno de los dos)")
        return self


class ReportPublic(BaseModel):
    id: int
    post_id: Optional[int] = None
    comment_id: Optional[int] = None
    reason: str
    status: ReportStatus
    reporter_id: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ReportResolve(BaseModel):
    action: Literal["hide", "dismiss"] = Field(
        ..., description="hide: oculta el contenido | dismiss: el contenido está bien")


class VisibilityUpdate(BaseModel):
    is_hidden: bool


class TextCheck(BaseModel):
    text: str = Field(..., max_length=2000)


class TextCheckResult(BaseModel):
    ok: bool
    reason: Optional[str] = None
