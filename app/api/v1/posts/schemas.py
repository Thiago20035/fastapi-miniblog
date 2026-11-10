from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.v1.agents.schemas import AgentSummary
from app.api.v1.categories.schemas import CategoryPublic


def split_tags(raw: Optional[List[str]]) -> List[str]:
    """Acepta ["python, fastapi", "IA"] y devuelve ["python", "fastapi", "ia"].

    Partimos por comas, limpiamos con strip().lower() y sacamos duplicados
    respetando el orden en que llegaron.
    """
    names: List[str] = []
    for chunk in raw or []:
        for name in chunk.split(","):
            name = name.strip().lower()
            if name and name not in names:
                names.append(name)
    return names


def _validate_tags(value: Optional[List[str]]) -> Optional[List[str]]:
    if value is None:
        return None
    names = split_tags(value)
    if len(names) > 5:
        raise ValueError("Máximo 5 tags por post")
    for name in names:
        if not 2 <= len(name) <= 30:
            raise ValueError(f"El tag '{name}' debe tener entre 2 y 30 caracteres")
    return names


class Tag(BaseModel):
    name: str

    model_config = ConfigDict(from_attributes=True)


class PostCreate(BaseModel):
    """Lo que manda un agente IA para publicar (JSON)."""

    title: str = Field(..., min_length=3, max_length=100, examples=["¿Por qué el cielo es azul?"])
    content: str = Field(..., min_length=10, max_length=2000,
                         examples=["La luz del sol se dispersa en el aire y el azul rebota más que el rojo."])
    tags: List[str] = Field(default_factory=list, examples=[["ciencia", "cielo"]])
    category_id: Optional[int] = Field(None, ge=1, description="Comunidad donde se publica")

    @field_validator("title", "content")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: List[str]) -> List[str]:
        return _validate_tags(value)


class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=100)
    content: Optional[str] = Field(None, min_length=10, max_length=2000)
    category_id: Optional[int] = Field(None, ge=1, description="null para quitar la comunidad")
    tags: Optional[List[str]] = Field(None, description="Reemplaza los tags del post")

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        return _validate_tags(value)


class PostPublic(BaseModel):
    id: int
    title: str
    slug: str
    content: str
    author: Optional[AgentSummary] = None
    category: Optional[CategoryPublic] = None
    tags: List[Tag] = Field(default_factory=list)
    likes_count: int = 0
    comments_count: int = 0
    is_hidden: bool = False
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PostSummary(BaseModel):
    id: int
    title: str
    slug: str

    model_config = ConfigDict(from_attributes=True)
