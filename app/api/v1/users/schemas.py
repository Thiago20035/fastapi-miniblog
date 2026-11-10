from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Role

USERNAME_PATTERN = r"^[a-zA-Z0-9_.-]+$"


class UserCreate(BaseModel):
    """Entrada del registro: la contraseña viaja en texto plano y se hashea al guardar."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    """Respuesta segura: nunca incluye la contraseña ni el hash."""

    id: int
    email: EmailStr
    username: str
    role: Role
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserSummary(BaseModel):
    """Versión corta que se anida dentro de cada post."""

    id: int
    username: str

    model_config = ConfigDict(from_attributes=True)


class UserUpdateMe(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    current_password: Optional[str] = None
    new_password: Optional[str] = Field(None, min_length=8, max_length=128)


class RoleUpdate(BaseModel):
    role: Role


class ActiveUpdate(BaseModel):
    is_active: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
