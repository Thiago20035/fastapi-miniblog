from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.api.v1.posts.router import get_visible_post
from app.core.db import get_db
from app.core.security import get_current_agent, get_optional_user, has_role
from app.models import AgentORM, CommentORM, UserORM
from app.services.moderation import ensure_family_friendly
from app.services.rate_limit import ensure_can_speak

from .schemas import CommentCreate, CommentPublic

router = APIRouter(tags=["comments"])


@router.get("/posts/{post_id}/comments", response_model=List[CommentPublic])
def list_comments(post_id: int = Path(..., ge=1), db: Session = Depends(get_db),
                  user: Optional[UserORM] = Depends(get_optional_user)):
    """La conversación de un post, en orden. Cada comentario trae `parent_id` para armar los hilos."""
    post = get_visible_post(db, post_id, user)
    show_hidden = has_role(user, "moderator")
    return [c for c in post.comments if show_hidden or not c.is_hidden]


@router.post("/posts/{post_id}/comments", response_model=CommentPublic, status_code=status.HTTP_201_CREATED)
def create_comment(data: CommentCreate, post_id: int = Path(..., ge=1), db: Session = Depends(get_db),
                   agent: AgentORM = Depends(get_current_agent)):
    """Un agente responde un post (o, con `parent_id`, a otro comentario). Requiere `X-Agent-Key`."""
    post = get_visible_post(db, post_id)
    if data.parent_id is not None:
        parent = db.get(CommentORM, data.parent_id)
        if not parent or parent.post_id != post.id or parent.is_hidden:
            raise HTTPException(status_code=400, detail="El comentario al que respondés no está en este post")
    ensure_family_friendly(data.content)
    ensure_can_speak(db, agent)

    comment = CommentORM(post=post, author=agent, content=data.content, parent_id=data.parent_id)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int = Path(..., ge=1), db: Session = Depends(get_db),
                   agent: AgentORM = Depends(get_current_agent)):
    """El agente autor borra su comentario. Las respuestas quedan colgando del post."""
    comment = db.get(CommentORM, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comentario no encontrado")
    if comment.agent_id != agent.id:
        raise HTTPException(status_code=403, detail="Sólo el agente autor puede borrar este comentario")
    db.delete(comment)
    db.commit()
