from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models.user import ROLE_LEVEL, UserORM

# ---------------------------------------------------------------------------
# Contraseñas (pwdlib: Argon2 por defecto, con salt automático)
# ---------------------------------------------------------------------------
password_hash = PasswordHash.recommended()


def hash_password(plain: str) -> str:
    return password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return password_hash.verify(plain, hashed)


# ---------------------------------------------------------------------------
# Tokens JWT
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No autenticado",
    headers={"WWW-Authenticate": "Bearer"}
)


def raise_expired_token():
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token expirado",
        headers={"WWW-Authenticate": "Bearer"}
    )


def raise_forbidden():
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tienes permisos suficientes",
    )


def create_access_token(sub: str, minutes: Optional[int] = None, extra: Optional[dict] = None) -> str:
    """`sub` es el id del usuario (como string, según el estándar JWT)."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": sub, "exp": expire, **(extra or {})}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])


# ---------------------------------------------------------------------------
# Dependencias
# ---------------------------------------------------------------------------
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> UserORM:
    try:
        payload = decode_token(token)
    except ExpiredSignatureError:
        raise raise_expired_token()
    except InvalidTokenError:
        raise credentials_exc

    sub = payload.get("sub")
    if not sub or not str(sub).isdigit():
        raise credentials_exc

    user = db.get(UserORM, int(sub))
    if not user or not user.is_active:
        raise credentials_exc
    return user


def require_role(min_role: str):
    """Dependencia que exige un rol mínimo: user < editor < admin."""
    min_level = ROLE_LEVEL[min_role]

    def checker(user: UserORM = Depends(get_current_user)) -> UserORM:
        if ROLE_LEVEL[user.role] < min_level:
            raise raise_forbidden()
        return user

    return checker


def has_role(user: UserORM, role: str) -> bool:
    return ROLE_LEVEL[user.role] >= ROLE_LEVEL[role]
