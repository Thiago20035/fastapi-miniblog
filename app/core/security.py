import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models.agent import AgentORM
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
# Tokens JWT (personas)
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

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


def _user_from_token(token: str, db: Session) -> UserORM:
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


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> UserORM:
    return _user_from_token(token, db)


def get_optional_user(token: Optional[str] = Depends(oauth2_optional),
                      db: Session = Depends(get_db)) -> Optional[UserORM]:
    """Para endpoints públicos que muestran más cosas a los moderadores."""
    return _user_from_token(token, db) if token else None


def require_role(min_role: str):
    """Dependencia que exige un rol mínimo: user < moderator < admin."""
    min_level = ROLE_LEVEL[min_role]

    def checker(user: UserORM = Depends(get_current_user)) -> UserORM:
        if ROLE_LEVEL[user.role] < min_level:
            raise raise_forbidden()
        return user

    return checker


def has_role(user: Optional[UserORM], role: str) -> bool:
    return user is not None and ROLE_LEVEL[user.role] >= ROLE_LEVEL[role]


# ---------------------------------------------------------------------------
# Claves de agentes IA
# ---------------------------------------------------------------------------
# Los agentes no tienen contraseña: mandan su clave en el header X-Agent-Key.
# En la base sólo queda el SHA-256 (si alguien roba la base, no roba las claves).
agent_key_header = APIKeyHeader(name="X-Agent-Key", auto_error=False,
                                description="Clave del agente IA (se muestra al registrarlo)")

AGENT_KEY_PREFIX = "ak_"


def new_agent_key() -> tuple[str, str]:
    """Devuelve (clave_en_texto_plano, hash_para_guardar)."""
    key = AGENT_KEY_PREFIX + secrets.token_urlsafe(32)
    return key, hash_agent_key(key)


def hash_agent_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def get_current_agent(key: Optional[str] = Depends(agent_key_header),
                      db: Session = Depends(get_db)) -> AgentORM:
    if not key:
        raise HTTPException(status_code=401, detail="Falta el header X-Agent-Key")
    agent = db.execute(
        select(AgentORM).where(AgentORM.api_key_hash == hash_agent_key(key))
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=401, detail="Clave de agente inválida")
    if not agent.is_active:
        raise HTTPException(status_code=403, detail="Este agente está suspendido")
    return agent
