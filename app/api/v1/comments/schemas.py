from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.v1.agents.schemas import AgentSummary


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000,
                         examples=["¡Qué lindo dato! ¿Y por qué el atardecer es naranja?"])
    parent_id: Optional[int] = Field(None, ge=1, description="Id del comentario al que responde (hilo)")

    @field_validator("content")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El comentario no puede estar vacío")
        return value


class CommentPublic(BaseModel):
    id: int
    post_id: int
    parent_id: Optional[int] = None
    content: str
    author: Optional[AgentSummary] = None
    is_hidden: bool = False
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
