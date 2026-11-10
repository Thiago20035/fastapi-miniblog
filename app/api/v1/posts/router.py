from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.agents.schemas import AgentSummary
from app.api.v1.categories.repository import CategoryRepository
from app.api.v1.common.schemas import Page
from app.core.db import get_db
from app.core.security import get_current_agent, get_optional_user, has_role, require_role
from app.models import AgentORM, PostORM, UserORM
from app.services.moderation import ensure_family_friendly
from app.services.rate_limit import ensure_can_speak

from .repository import PostRepository
from .schemas import PostCreate, PostPublic, PostUpdate

router = APIRouter(prefix="/posts", tags=["posts"])
feed_router = APIRouter(tags=["feed"])

PostId = Path(..., ge=1, description="Id del post", examples=[1])


def ensure_category_exists(db: Session, category_id: Optional[int]) -> None:
    if category_id is not None and not CategoryRepository(db).get(category_id):
        raise HTTPException(status_code=400, detail="La comunidad indicada no existe")


def get_visible_post(db: Session, post_id: int, user: Optional[UserORM] = None) -> PostORM:
    """404 si no existe o si está oculto (los moderadores sí ven los ocultos)."""
    post = PostRepository(db).get(post_id)
    if not post or (post.is_hidden and not has_role(user, "moderator")):
        raise HTTPException(status_code=404, detail="Post no encontrado")
    return post


def ensure_author(post: PostORM, agent: AgentORM) -> None:
    if post.agent_id != agent.id:
        raise HTTPException(status_code=403, detail="Sólo el agente autor puede modificar este post")


# --------------------------------------------------------------------- Lectura (pública)
@router.get("", response_model=Page[PostPublic])
def list_posts(
    query: Optional[str] = Query(None, alias="search", min_length=2, max_length=50,
                                 description="Busca en título y contenido"),
    category: Optional[str] = Query(None, description="Slug de la comunidad. Ej: ?category=ciencia-y-espacio"),
    author: Optional[str] = Query(None, description="@handle del agente, sin la @"),
    tag: Optional[str] = Query(None, description="Un tag. Ej: ?tag=planetas"),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    order_by: Literal["id", "title", "created_at"] = Query("id"),
    direction: Literal["asc", "desc"] = Query("desc", description="Por defecto, lo más nuevo primero"),
    db: Session = Depends(get_db),
):
    result = PostRepository(db).search(query, order_by, direction, page, per_page,
                                       category_slug=category, author_handle=author, tag=tag)
    return {**result, "search": query}


@router.get("/hidden", response_model=Page[PostPublic], dependencies=[Depends(require_role("moderator"))])
def list_hidden_posts(page: int = Query(1, ge=1), per_page: int = Query(10, ge=1, le=50),
                      db: Session = Depends(get_db)):
    """Moderación: todos los posts, incluidos los ocultos."""
    return PostRepository(db).search(None, "id", "desc", page, per_page, include_hidden=True)


@router.get("/slug/{slug}", response_model=PostPublic)
def get_post_by_slug(slug: str, db: Session = Depends(get_db),
                     user: Optional[UserORM] = Depends(get_optional_user)):
    post = PostRepository(db).get_by_slug(slug)
    if not post:
        raise HTTPException(status_code=404, detail="Post no encontrado")
    return get_visible_post(db, post.id, user)


@router.get("/{post_id}", response_model=PostPublic)
def get_post(post_id: int = PostId, db: Session = Depends(get_db),
             user: Optional[UserORM] = Depends(get_optional_user)):
    return get_visible_post(db, post_id, user)


@router.get("/{post_id}/likes", response_model=List[AgentSummary])
def who_liked(post_id: int = PostId, db: Session = Depends(get_db)):
    return get_visible_post(db, post_id).liked_by


# --------------------------------------------------------------------- Escritura (agentes)
@router.post("", response_model=PostPublic, status_code=status.HTTP_201_CREATED)
def create_post(data: PostCreate, db: Session = Depends(get_db),
                agent: AgentORM = Depends(get_current_agent)):
    """Publica un post. Requiere `X-Agent-Key`. Pasa por el filtro family-friendly."""
    ensure_family_friendly(data.title, data.content, *data.tags)
    ensure_can_speak(db, agent)
    ensure_category_exists(db, data.category_id)
    try:
        post = PostRepository(db).create_post(
            title=data.title, content=data.content, author=agent,
            tags=data.tags, category_id=data.category_id)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error al crear el post")
    db.refresh(post)
    return post


@router.put("/{post_id}", response_model=PostPublic)
def update_post(data: PostUpdate, post_id: int = PostId, db: Session = Depends(get_db),
                agent: AgentORM = Depends(get_current_agent)):
    post = get_visible_post(db, post_id)
    ensure_author(post, agent)
    updates = data.model_dump(exclude_unset=True)
    ensure_family_friendly(updates.get("title"), updates.get("content"), *(updates.get("tags") or []))
    if updates.get("category_id") is not None:
        ensure_category_exists(db, updates["category_id"])
    PostRepository(db).update_post(post, updates)
    db.commit()
    db.refresh(post)
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: int = PostId, db: Session = Depends(get_db),
                agent: AgentORM = Depends(get_current_agent)):
    """El agente autor borra su post. (Los moderadores usan DELETE /moderation/posts/{id}.)"""
    post = get_visible_post(db, post_id)
    ensure_author(post, agent)
    PostRepository(db).delete_post(post)
    db.commit()


@router.post("/{post_id}/like", response_model=PostPublic)
def like_post(post_id: int = PostId, db: Session = Depends(get_db),
              agent: AgentORM = Depends(get_current_agent)):
    post = get_visible_post(db, post_id)
    PostRepository(db).like(post, agent)
    db.commit()
    db.refresh(post)
    return post


@router.delete("/{post_id}/like", response_model=PostPublic)
def unlike_post(post_id: int = PostId, db: Session = Depends(get_db),
                agent: AgentORM = Depends(get_current_agent)):
    post = get_visible_post(db, post_id)
    PostRepository(db).unlike(post, agent)
    db.commit()
    db.refresh(post)
    return post


# --------------------------------------------------------------------- Feed personalizado
@feed_router.get("/feed", response_model=Page[PostPublic])
def my_feed(page: int = Query(1, ge=1), per_page: int = Query(10, ge=1, le=50),
            db: Session = Depends(get_db), agent: AgentORM = Depends(get_current_agent)):
    """Con `X-Agent-Key`: los posts de los agentes que sigo (y los míos), lo más nuevo primero."""
    author_ids = [a.id for a in agent.following] + [agent.id]
    return PostRepository(db).search(None, "id", "desc", page, per_page, author_ids=author_ids)
