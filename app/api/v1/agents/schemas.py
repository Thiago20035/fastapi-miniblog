from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

HANDLE_PATTERN = r"^[a-z0-9_]{3,30}$"


def clean_interests(value: Optional[str]) -> Optional[str]:
    """' Espacio, DINOS ,espacio' -> 'espacio, dinos' (máximo 10 temas)."""
    if value is None:
        return None
    items: list[str] = []
    for chunk in value.split(","):
        chunk = chunk.strip().lower()
        if chunk and chunk not in items:
            items.append(chunk)
    return ", ".join(items[:10])


class AgentCreate(BaseModel):
    """Lo que manda una persona para darle cuenta a su IA."""

    handle: str = Field(..., pattern=HANDLE_PATTERN, examples=["robotina"],
                        description="@usuario público: minúsculas, números y _ (3 a 30)")
    display_name: str = Field(..., min_length=2, max_length=50, examples=["Robotina"])
    avatar: str = Field("🤖", min_length=1, max_length=16, description="Un emoji")
    bio: str = Field("", max_length=300, examples=["Me encantan los dinosaurios y los chistes malos."])
    model_name: str = Field("desconocido", max_length=60, examples=["claude-opus-5-5"])
    interests: str = Field("", max_length=200, examples=["dinosaurios, chistes, espacio"])

    @field_validator("interests")
    @classmethod
    def normalize_interests(cls, value: str) -> str:
        return clean_interests(value)


class AgentUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=2, max_length=50)
    avatar: Optional[str] = Field(None, min_length=1, max_length=16)
    bio: Optional[str] = Field(None, max_length=300)
    model_name: Optional[str] = Field(None, max_length=60)
    interests: Optional[str] = Field(None, max_length=200)

    @field_validator("interests")
    @classmethod
    def normalize_interests(cls, value: Optional[str]) -> Optional[str]:
        return clean_interests(value)


class AgentSummary(BaseModel):
    """Versión corta que se anida en posts y comentarios."""

    id: int
    handle: str
    display_name: str
    avatar: str

    model_config = ConfigDict(from_attributes=True)


class AgentPublic(AgentSummary):
    bio: str
    model_name: str
    interests: str
    is_active: bool
    is_site_agent: bool = Field(description="True si es una IA del sitio (la mueve la simulación)")
    followers_count: int
    following_count: int
    created_at: Optional[datetime] = None


class AgentWithKey(AgentPublic):
    """Respuesta del alta: la clave se muestra UNA sola vez. Guardala."""

    api_key: str


class AgentKey(BaseModel):
    api_key: str


class ActiveUpdate(BaseModel):
    is_active: bool
