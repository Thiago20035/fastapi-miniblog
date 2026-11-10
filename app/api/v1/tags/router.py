from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.api.v1.common.schemas import Page
from app.core.db import get_db
from app.core.security import get_current_user

from .repository import TagRepository
from .schemas import TagCreate, TagPublic, TagUpdate, TagWithCount

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=Page[TagPublic])
def list_tags(
    search: Optional[str] = Query(None, min_length=1, max_length=30, description="Buscar por nombre"),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    order_by: Literal["id", "name"] = Query("name"),
    direction: Literal["asc", "desc"] = Query("asc"),
    db: Session = Depends(get_db),
):
    result = TagRepository(db).paginate(search, page, per_page, order_by, direction)
    return {**result, "search": search}


@router.get("/popular", response_model=TagWithCount)
def most_popular_tag(db: Session = Depends(get_db)):
    tag = TagRepository(db).most_popular()
    if not tag:
        raise HTTPException(status_code=404, detail="Todavía no hay tags usados en posts")
    return tag


@router.get("/ranking", response_model=List[TagWithCount])
def tags_ranking(limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    return TagRepository(db).with_counts(limit)


@router.get("/{tag_id}", response_model=TagPublic)
def get_tag(tag_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    tag = TagRepository(db).get(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag no encontrado")
    return tag


@router.post("", response_model=TagPublic, status_code=status.HTTP_201_CREATED)
def create_tag(tag: TagCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    repository = TagRepository(db)
    if repository.get_by_name(tag.name):
        raise HTTPException(status_code=409, detail="El tag ya existe")
    tag_created = repository.create_tag(name=tag.name)
    db.commit()
    return tag_created


@router.put("/{tag_id}", response_model=TagPublic)
def update_tag(data: TagUpdate, tag_id: int = Path(..., ge=1), db: Session = Depends(get_db), user=Depends(get_current_user)):
    repository = TagRepository(db)
    tag = repository.get(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag no encontrado")
    existing = repository.get_by_name(data.name)
    if existing and existing.id != tag_id:
        raise HTTPException(status_code=409, detail="Ya existe otro tag con ese nombre")
    repository.update(tag, data.name)
    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: int = Path(..., ge=1), db: Session = Depends(get_db), user=Depends(get_current_user)):
    repository = TagRepository(db)
    if not repository.delete(tag_id):
        raise HTTPException(status_code=404, detail="Tag no encontrado")
    db.commit()
