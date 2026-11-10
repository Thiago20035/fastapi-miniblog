from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.slugs import SLUG_PATTERN, slugify


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=60, examples=["Programación"])
    slug: Optional[str] = Field(
        None, min_length=2, max_length=60, pattern=SLUG_PATTERN,
        description="Si no se manda, se genera a partir del nombre", examples=["programacion"],
    )

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def default_slug(self):
        if not self.slug:
            self.slug = slugify(self.name)
        return self


class CategoryUpdate(BaseModel):
    """Actualización parcial: todos los campos son opcionales."""

    name: Optional[str] = Field(None, min_length=2, max_length=60)
    slug: Optional[str] = Field(None, min_length=2, max_length=60, pattern=SLUG_PATTERN)


class CategoryPublic(BaseModel):
    id: int
    name: str
    slug: str

    model_config = ConfigDict(from_attributes=True)


class CategoryWithCount(CategoryPublic):
    posts: int
