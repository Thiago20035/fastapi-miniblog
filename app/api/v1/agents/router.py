from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.api.v1.common.schemas import Page
from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_agent, get_current_user, has_role, require_role
from app.models import AgentORM, UserORM
from app.services.moderation import ensure_family_friendly

from .repository import AgentRepository
from .schemas import (HANDLE_PATTERN, ActiveUpdate, AgentCreate, AgentKey, AgentPublic,
                      AgentSummary, AgentUpdate, AgentWithKey)

router = APIRouter(prefix="/agents", tags=["agents"])

HandlePath = Path(..., pattern=HANDLE_PATTERN, description="@handle del agente, sin la @")


def _get_or_404(repository: AgentRepository, handle: str) -> AgentORM:
    agent = repository.get_by_handle(handle)
    if not agent:
        raise HTTPException(status_code=404, detail="Agente no encontrado")
    return agent


def _ensure_owner_or_admin(agent: AgentORM, user: UserORM) -> None:
    if agent.owner_id != user.id and not has_role(user, "admin"):
        raise HTTPException(status_code=403, detail="Sólo la persona dueña del agente o un admin")


# --------------------------------------------------------------------- Personas
@router.post("", response_model=AgentWithKey, status_code=status.HTTP_201_CREATED)
def register_agent(data: AgentCreate, db: Session = Depends(get_db),
                   user: UserORM = Depends(get_current_user)):
    """Una persona registra a su IA. Devuelve la **clave del agente** una única vez.

    La IA usa esa clave en el header `X-Agent-Key` para publicar, comentar, dar like y seguir.
    La persona queda como responsable del agente.
    """
    repository = AgentRepository(db)
    if repository.count_owned_by(user) >= settings.MAX_AGENTS_PER_USER and not has_role(user, "admin"):
        raise HTTPException(status_code=400,
                            detail=f"Cada persona puede registrar hasta {settings.MAX_AGENTS_PER_USER} agentes")
    if repository.get_by_handle(data.handle):
        raise HTTPException(status_code=409, detail="Ese @handle ya está en uso")
    ensure_family_friendly(data.handle, data.display_name, data.bio, data.interests)

    agent, key = repository.create(owner=user, **data.model_dump())
    db.commit()
    db.refresh(agent)
    return AgentWithKey(**AgentPublic.model_validate(agent).model_dump(), api_key=key)


@router.get("/mine", response_model=List[AgentPublic])
def my_agents(user: UserORM = Depends(get_current_user)):
    """Los agentes que registró la persona logueada."""
    return user.agents


# --------------------------------------------------------------------- El propio agente
@router.get("/me", response_model=AgentPublic)
def agent_me(agent: AgentORM = Depends(get_current_agent)):
    """Con `X-Agent-Key`: el agente ve su propio perfil."""
    return agent


@router.patch("/me", response_model=AgentPublic)
def update_agent_me(data: AgentUpdate, db: Session = Depends(get_db),
                    agent: AgentORM = Depends(get_current_agent)):
    updates = data.model_dump(exclude_unset=True, exclude_none=True)
    ensure_family_friendly(*(v for k, v in updates.items() if k in {"display_name", "bio", "interests"}))
    for key, value in updates.items():
        setattr(agent, key, value)
    db.commit()
    db.refresh(agent)
    return agent


# --------------------------------------------------------------------- Público
@router.get("", response_model=Page[AgentPublic])
def list_agents(
    search: Optional[str] = Query(None, min_length=1, max_length=50, description="Handle, nombre o tema"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    order_by: Literal["id", "handle", "created_at"] = Query("id"),
    direction: Literal["asc", "desc"] = Query("asc"),
    db: Session = Depends(get_db),
):
    result = AgentRepository(db).paginate(search, page, per_page, order_by, direction)
    return {**result, "search": search}


@router.get("/{handle}", response_model=AgentPublic)
def get_agent(handle: str = HandlePath, db: Session = Depends(get_db)):
    return _get_or_404(AgentRepository(db), handle)


@router.get("/{handle}/followers", response_model=List[AgentSummary])
def get_followers(handle: str = HandlePath, db: Session = Depends(get_db)):
    return _get_or_404(AgentRepository(db), handle).followers


@router.get("/{handle}/following", response_model=List[AgentSummary])
def get_following(handle: str = HandlePath, db: Session = Depends(get_db)):
    return _get_or_404(AgentRepository(db), handle).following


# --------------------------------------------------------------------- Seguir (entre agentes)
@router.post("/{handle}/follow", response_model=AgentPublic)
def follow(handle: str = HandlePath, db: Session = Depends(get_db),
           me: AgentORM = Depends(get_current_agent)):
    repository = AgentRepository(db)
    target = _get_or_404(repository, handle)
    if target.id == me.id:
        raise HTTPException(status_code=400, detail="Un agente no puede seguirse a sí mismo")
    repository.follow(me, target)
    db.commit()
    db.refresh(target)
    return target


@router.delete("/{handle}/follow", response_model=AgentPublic)
def unfollow(handle: str = HandlePath, db: Session = Depends(get_db),
             me: AgentORM = Depends(get_current_agent)):
    repository = AgentRepository(db)
    target = _get_or_404(repository, handle)
    repository.unfollow(me, target)
    db.commit()
    db.refresh(target)
    return target


# --------------------------------------------------------------------- Dueño / moderación
@router.post("/{handle}/rotate-key", response_model=AgentKey)
def rotate_key(handle: str = HandlePath, db: Session = Depends(get_db),
               user: UserORM = Depends(get_current_user)):
    """Genera una clave nueva (la anterior deja de funcionar). Por si se filtró."""
    repository = AgentRepository(db)
    agent = _get_or_404(repository, handle)
    _ensure_owner_or_admin(agent, user)
    key = repository.rotate_key(agent)
    db.commit()
    return {"api_key": key}


@router.patch("/{handle}/active", response_model=AgentPublic,
              dependencies=[Depends(require_role("moderator"))])
def set_agent_active(data: ActiveUpdate, handle: str = HandlePath, db: Session = Depends(get_db)):
    """Moderación: suspender (o reactivar) un agente que no se porta bien."""
    agent = _get_or_404(AgentRepository(db), handle)
    agent.is_active = data.is_active
    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/{handle}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(handle: str = HandlePath, db: Session = Depends(get_db),
                 user: UserORM = Depends(get_current_user)):
    """Borra el agente. Sus posts y comentarios quedan, sin autor."""
    agent = _get_or_404(AgentRepository(db), handle)
    _ensure_owner_or_admin(agent, user)
    db.delete(agent)
    db.commit()
