from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.comments.schemas import CommentPublic
from app.api.v1.posts.schemas import PostPublic
from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user, require_role
from app.models import CommentORM, PostORM, ReportORM, UserORM
from app.models.report import ReportStatus
from app.services.moderation import review

from .schemas import (ReportCreate, ReportPublic, ReportResolve, TextCheck, TextCheckResult,
                      VisibilityUpdate)

router = APIRouter(prefix="/moderation", tags=["moderation"])
moderator = require_role("moderator")


def _target(db: Session, post_id: Optional[int], comment_id: Optional[int]):
    target = db.get(PostORM, post_id) if post_id else db.get(CommentORM, comment_id)
    if not target:
        raise HTTPException(status_code=404, detail="No existe el contenido reportado")
    return target


def _open_reports_for(db: Session, report: ReportORM) -> int:
    column = ReportORM.post_id if report.post_id else ReportORM.comment_id
    value = report.post_id or report.comment_id
    return db.scalar(select(func.count()).select_from(ReportORM).where(
        column == value, ReportORM.status == "open")) or 0


# --------------------------------------------------------------------- Cualquier persona
@router.post("/check", response_model=TextCheckResult)
def check_text(data: TextCheck):
    """Probá un texto contra el filtro family-friendly antes de publicarlo (público)."""
    reason = review(data.text)
    return {"ok": reason is None, "reason": reason}


@router.post("/reports", response_model=ReportPublic, status_code=status.HTTP_201_CREATED)
def create_report(data: ReportCreate, db: Session = Depends(get_db),
                  user: UserORM = Depends(get_current_user)):
    """Cualquier persona logueada reporta un post o comentario.

    Al juntar `AUTO_HIDE_REPORTS` reportes abiertos (3 por defecto) se oculta solo,
    hasta que un moderador lo revise.
    """
    target = _target(db, data.post_id, data.comment_id)
    same_target = (ReportORM.post_id == data.post_id) if data.post_id else (ReportORM.comment_id == data.comment_id)
    already = db.scalar(select(ReportORM.id).where(ReportORM.reporter_id == user.id, same_target))
    if already:
        raise HTTPException(status_code=409, detail="Ya reportaste este contenido")

    report = ReportORM(reporter_id=user.id, **data.model_dump())
    db.add(report)
    db.flush()
    if _open_reports_for(db, report) >= settings.AUTO_HIDE_REPORTS:
        target.is_hidden = True
    db.commit()
    db.refresh(report)
    return report


# --------------------------------------------------------------------- Moderadores
@router.get("/reports", response_model=List[ReportPublic], dependencies=[Depends(moderator)])
def list_reports(status_filter: Optional[ReportStatus] = Query("open", alias="status"),
                 db: Session = Depends(get_db)):
    query = select(ReportORM).order_by(ReportORM.id.desc())
    if status_filter:
        query = query.where(ReportORM.status == status_filter)
    return db.execute(query).scalars().all()


@router.patch("/reports/{report_id}", response_model=ReportPublic, dependencies=[Depends(moderator)])
def resolve_report(data: ReportResolve, report_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    """Resuelve el reporte y todos los abiertos sobre el mismo contenido."""
    report = db.get(ReportORM, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    target = _target(db, report.post_id, report.comment_id)
    target.is_hidden = data.action == "hide"
    new_status = "hidden" if data.action == "hide" else "dismissed"

    column = ReportORM.post_id if report.post_id else ReportORM.comment_id
    siblings = db.execute(select(ReportORM).where(
        column == (report.post_id or report.comment_id), ReportORM.status == "open")).scalars().all()
    for item in {*siblings, report}:
        item.status = new_status
    db.commit()
    db.refresh(report)
    return report


@router.patch("/posts/{post_id}", response_model=PostPublic, dependencies=[Depends(moderator)])
def set_post_visibility(data: VisibilityUpdate, post_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    post = _target(db, post_id, None)
    post.is_hidden = data.is_hidden
    db.commit()
    db.refresh(post)
    return post


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(moderator)])
def delete_post(post_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    db.delete(_target(db, post_id, None))
    db.commit()


@router.patch("/comments/{comment_id}", response_model=CommentPublic, dependencies=[Depends(moderator)])
def set_comment_visibility(data: VisibilityUpdate, comment_id: int = Path(..., ge=1),
                           db: Session = Depends(get_db)):
    comment = _target(db, None, comment_id)
    comment.is_hidden = data.is_hidden
    db.commit()
    db.refresh(comment)
    return comment


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(moderator)])
def delete_comment(comment_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    db.delete(_target(db, None, comment_id))
    db.commit()
