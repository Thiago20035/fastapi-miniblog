from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.api.v1.common.schemas import Page
from app.core.db import get_db
from app.core.security import get_current_user, require_role, verify_password
from app.core.security import hash_password
from app.models import UserORM
from app.models.user import Role

from .repository import UserRepository
from .schemas import ActiveUpdate, RoleUpdate, UserPublic, UserUpdateMe

router = APIRouter(prefix="/users", tags=["users"])

admin_only = require_role("admin")


# --------------------------- Perfil propio (cualquier rol) ---------------------------
@router.get("/me", response_model=UserPublic)
def get_me(current: UserORM = Depends(get_current_user)):
    return current


@router.patch("/me", response_model=UserPublic)
def update_me(data: UserUpdateMe, db: Session = Depends(get_db), current: UserORM = Depends(get_current_user)):
    repository = UserRepository(db)

    if data.username and data.username != current.username:
        other = repository.get_by_username(data.username)
        if other and other.id != current.id:
            raise HTTPException(status_code=409, detail="El nombre de usuario ya está en uso")
        current.username = data.username

    if data.new_password:
        if not data.current_password or not verify_password(data.current_password, current.hashed_password):
            raise HTTPException(status_code=400, detail="La contraseña actual no es correcta")
        current.hashed_password = hash_password(data.new_password)

    db.commit()
    db.refresh(current)
    return current


# --------------------------- Administración (sólo admin) ---------------------------
@router.get("", response_model=Page[UserPublic], dependencies=[Depends(admin_only)])
def list_users(
    search: Optional[str] = Query(None, min_length=1, max_length=50, description="Email o usuario"),
    role: Optional[Role] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    order_by: Literal["id", "email", "username", "created_at"] = Query("id"),
    direction: Literal["asc", "desc"] = Query("asc"),
    db: Session = Depends(get_db),
):
    result = UserRepository(db).paginate(search, role, page, per_page, order_by, direction)
    return {**result, "search": search}


def _get_or_404(repository: UserRepository, user_id: int) -> UserORM:
    user = repository.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


def _ensure_not_last_admin(repository: UserRepository, user: UserORM) -> None:
    if user.role == "admin" and user.is_active and repository.count_admins() <= 1:
        raise HTTPException(status_code=400, detail="No se puede dejar el sistema sin administradores")


@router.get("/{user_id}", response_model=UserPublic, dependencies=[Depends(admin_only)])
def get_user(user_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    return _get_or_404(UserRepository(db), user_id)


@router.patch("/{user_id}/role", response_model=UserPublic, dependencies=[Depends(admin_only)])
def change_role(data: RoleUpdate, user_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    repository = UserRepository(db)
    user = _get_or_404(repository, user_id)
    if data.role != "admin":
        _ensure_not_last_admin(repository, user)
    user.role = data.role
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/active", response_model=UserPublic, dependencies=[Depends(admin_only)])
def change_active(data: ActiveUpdate, user_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    repository = UserRepository(db)
    user = _get_or_404(repository, user_id)
    if not data.is_active:
        _ensure_not_last_admin(repository, user)
    user.is_active = data.is_active
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(admin_only)])
def delete_user(user_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    """Borra la persona. Sus agentes siguen existiendo, sin dueño (ON DELETE SET NULL)."""
    repository = UserRepository(db)
    user = _get_or_404(repository, user_id)
    _ensure_not_last_admin(repository, user)
    repository.delete(user)
    db.commit()
