from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CategoryORM, PostORM
from app.services.pagination import paginate_query


class CategoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, category_id: int) -> Optional[CategoryORM]:
        return self.db.get(CategoryORM, category_id)

    def get_by_slug(self, slug: str) -> Optional[CategoryORM]:
        query = select(CategoryORM).where(CategoryORM.slug == slug)
        return self.db.execute(query).scalars().first()

    def get_by_name(self, name: str) -> Optional[CategoryORM]:
        query = select(CategoryORM).where(func.lower(CategoryORM.name) == name.strip().lower())
        return self.db.execute(query).scalars().first()

    def paginate(self, search: Optional[str], page: int, per_page: int, order_by: str, direction: str) -> dict:
        query = select(CategoryORM)
        if search:
            query = query.where(CategoryORM.name.ilike(f"%{search}%"))
        return paginate_query(
            self.db, CategoryORM, query,
            page=page, per_page=per_page,
            order_by=order_by, direction=direction,
            allowed_order=["id", "name"],
        )

    def with_counts(self) -> list[dict]:
        rows = self.db.execute(
            select(CategoryORM.id, CategoryORM.name, CategoryORM.slug,
                   func.count(PostORM.id).label("posts"))
            .outerjoin(PostORM, PostORM.category_id == CategoryORM.id)
            .group_by(CategoryORM.id, CategoryORM.name, CategoryORM.slug)
            .order_by(func.count(PostORM.id).desc(), CategoryORM.name.asc())
        ).mappings().all()
        return [dict(r) for r in rows]

    def create(self, *, name: str, slug: str) -> CategoryORM:
        category = CategoryORM(name=name, slug=slug)
        self.db.add(category)
        self.db.flush()
        return category

    def update(self, category: CategoryORM, updates: dict) -> CategoryORM:
        for key, value in updates.items():
            setattr(category, key, value)
        self.db.flush()
        return category

    def delete(self, category: CategoryORM) -> None:
        self.db.delete(category)
