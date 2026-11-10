from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize(value: str) -> str:
    return value.strip().lower()


class TagPublic(BaseModel):
    id: int
    name: str = Field(..., min_length=2, max_length=30)

    model_config = ConfigDict(from_attributes=True)


class TagCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=30, examples=["fastapi"])

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _normalize(value)


class TagUpdate(TagCreate):
    pass


class TagWithCount(TagPublic):
    uses: int
