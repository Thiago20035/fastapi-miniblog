from datetime import datetime
from typing import Optional, List, Union, Literal, Annotated
from pydantic import BaseModel, Field, field_validator, EmailStr, ConfigDict
from fastapi import Form
from app.api.v1.users.schemas import UserSummary
from app.api.v1.categories.schemas import CategoryPublic


def split_tags(raw: Optional[List[str]]) -> List[str]:
    """Los formularios mandan los tags como 'python, fastapi'.

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


class Tag(BaseModel):
    name: str = Field(..., min_length=2, max_length=30,
                      description="Nombre de la etiqueta")

    model_config = ConfigDict(from_attributes=True)


class PostBase(BaseModel):
    title: str
    content: str
    tags: Optional[List[Tag]] = Field(default_factory=list)  # []
    user: Optional[UserSummary] = None
    category: Optional[CategoryPublic] = None
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PostCreate(BaseModel):
    title: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Titulo del post (mínimo 3 caracteres, máximo 100)",
        examples=["Mi primer post con FastAPI"]
    )
    content: Optional[str] = Field(
        default="Contenido no disponible",
        min_length=10,
        description="Contenido del post (mínimo 10 caracteres)",
        examples=["Este es un contenido válido porque tiene 10 caracteres o más"]
    )
    tags: List[Tag] = Field(default_factory=list)  # []
    category_id: Optional[int] = Field(None, ge=1)

    @field_validator("title")
    @classmethod
    def not_allowed_title(cls, value: str) -> str:
        if "spam" in value.lower():
            raise ValueError("El título no puede contener la palabra: 'spam'")
        return value

    @classmethod
    def as_form(
        cls,
        title: Annotated[str, Form(min_length=3)],
        content: Annotated[str, Form(min_length=10)],
        tags: Annotated[Optional[List[str]], Form()] = None,
        category_id: Annotated[Optional[int], Form(ge=1)] = None,
    ):
        return cls(
            title=title,
            content=content,
            tags=[Tag(name=t) for t in split_tags(tags)],
            category_id=category_id,
        )


class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=100)
    content: Optional[str] = Field(None, min_length=10)
    category_id: Optional[int] = Field(None, ge=1, description="null para quitar la categoría")
    tags: Optional[List[str]] = Field(None, description="Reemplaza los tags del post")

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        return None if value is None else split_tags(value)


class PostPublic(PostBase):
    id: int
    slug: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PostSummary(BaseModel):
    id: int
    title: str
    slug: str

    model_config = ConfigDict(from_attributes=True)
