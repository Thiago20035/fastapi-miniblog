from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.api.v1.common.schemas import Page
from app.core.db import get_db
from app.core.security import require_role
from app.models import CategoryORM

from .repository import CategoryRepository
from .schemas import CategoryCreate, CategoryPublic, CategoryUpdate, CategoryWithCount

router = APIRouter(prefix="/categories", tags=["categories"])

editor = require_role("editor")


def _get_or_404(repository: CategoryRepository, category_id: int) -> CategoryORM:
    category = repository.get(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return category


@router.get("", response_model=Page[CategoryPublic])
def list_categories(
    search: Optional[str] = Query(None, min_length=1, max_length=60),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    order_by: Literal["id", "name"] = Query("name"),
    direction: Literal["asc", "desc"] = Query("asc"),
    db: Session = Depends(get_db),
):
    result = CategoryRepository(db).paginate(search, page, per_page, order_by, direction)
    return {**result, "search": search}


@router.get("/stats", response_model=List[CategoryWithCount])
def categories_with_count(db: Session = Depends(get_db)):
    """Cada categoría con la cantidad de posts que tiene."""
    return CategoryRepository(db).with_counts()


@router.get("/slug/{slug}", response_model=CategoryPublic)
def get_category_by_slug(slug: str, db: Session = Depends(get_db)):
    category = CategoryRepository(db).get_by_slug(slug)
    if not category:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return category


@router.get("/{category_id}", response_model=CategoryPublic)
def get_category(category_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    return _get_or_404(CategoryRepository(db), category_id)


@router.post("", response_model=CategoryPublic, status_code=status.HTTP_201_CREATED, dependencies=[Depends(editor)])
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    repository = CategoryRepository(db)
    if repository.get_by_slug(data.slug):
        raise HTTPException(status_code=400, detail="Slug en uso")
    if repository.get_by_name(data.name):
        raise HTTPException(status_code=400, detail="Ya existe una categoría con ese nombre")

    category = repository.create(name=data.name, slug=data.slug)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/{category_id}", response_model=CategoryPublic, dependencies=[Depends(editor)])
def update_category(data: CategoryUpdate, category_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    repository = CategoryRepository(db)
    category = _get_or_404(repository, category_id)
    updates = data.model_dump(exclude_unset=True, exclude_none=True)

    if "slug" in updates:
        other = repository.get_by_slug(updates["slug"])
        if other and other.id != category_id:
            raise HTTPException(status_code=400, detail="Slug en uso")
    if "name" in updates:
        updates["name"] = updates["name"].strip()
        other = repository.get_by_name(updates["name"])
        if other and other.id != category_id:
            raise HTTPException(status_code=400, detail="Ya existe una categoría con ese nombre")

    repository.update(category, updates)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_role("admin"))])
def delete_category(category_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    """Sólo admin. Los posts de la categoría quedan sin categoría (no se borran)."""
    repository = CategoryRepository(db)
    repository.delete(_get_or_404(repository, category_id))
    db.commit()
