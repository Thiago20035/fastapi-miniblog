from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.v1.users.repository import UserRepository
from app.api.v1.users.schemas import Token, UserCreate, UserLogin, UserPublic
from app.core.db import get_db
from app.core.security import create_access_token, get_current_user
from app.models import UserORM

router = APIRouter(prefix="/auth", tags=["auth"])

invalid_credentials = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales inválidas",
    headers={"WWW-Authenticate": "Bearer"},
)


def _issue_token(user: UserORM | None) -> dict:
    if not user:
        raise invalid_credentials
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario desactivado")
    token = create_access_token(sub=str(user.id), extra={"role": user.role})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: Session = Depends(get_db)):
    """Registro público. Todo usuario nuevo arranca con rol `user`."""
    repository = UserRepository(db)
    if repository.get_by_email(data.email):
        raise HTTPException(status_code=409, detail="El email ya está registrado")
    if repository.get_by_username(data.username):
        raise HTTPException(status_code=409, detail="El nombre de usuario ya está en uso")
    user = repository.create(email=data.email, username=data.username, password=data.password)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login por formulario (el que usa el botón Authorize de /docs). En `username` va el email."""
    return _issue_token(UserRepository(db).authenticate(form_data.username, form_data.password))


@router.post("/login/json", response_model=Token)
def login_json(data: UserLogin, db: Session = Depends(get_db)):
    """Mismo login pero con JSON {email, password}, cómodo para un frontend."""
    return _issue_token(UserRepository(db).authenticate(data.email, data.password))


@router.get("/me", response_model=UserPublic)
def read_me(current: UserORM = Depends(get_current_user)):
    return current
