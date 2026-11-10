from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PostORM, TagORM, post_tags
from app.services.pagination import paginate_query


class TagRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tag_id: int) -> Optional[TagORM]:
        return self.db.get(TagORM, tag_id)

    def get_by_name(self, name: str) -> Optional[TagORM]:
        query = select(TagORM).where(func.lower(TagORM.name) == name.strip().lower())
        return self.db.execute(query).scalars().first()

    def paginate(self, search: Optional[str], page: int, per_page: int, order_by: str, direction: str) -> dict:
        query = select(TagORM)
        if search:
            query = query.where(TagORM.name.ilike(f"%{search}%"))
        return paginate_query(
            self.db, TagORM, query,
            page=page, per_page=per_page,
            order_by=order_by, direction=direction,
            allowed_order=["id", "name"],
        )

    def create_tag(self, name: str) -> TagORM:
        tag = TagORM(name=name.strip().lower())
        self.db.add(tag)
        self.db.flush()
        return tag

    def ensure_tag(self, name: str) -> TagORM:
        """Devuelve el tag existente o lo crea. Lo usan los posts."""
        return self.get_by_name(name) or self.create_tag(name)

    def update(self, tag: TagORM, name: str) -> TagORM:
        tag.name = name.strip().lower()
        self.db.flush()
        return tag

    def delete(self, tag_id: int) -> bool:
        tag = self.get(tag_id)
        if not tag:
            return False
        self.db.delete(tag)
        return True

    def most_popular(self) -> Optional[dict]:
        row = self.db.execute(
            select(TagORM.id, TagORM.name, func.count(PostORM.id).label("uses"))
            .join(post_tags, post_tags.c.tag_id == TagORM.id)
            .join(PostORM, PostORM.id == post_tags.c.post_id)
            .group_by(TagORM.id, TagORM.name)
            .order_by(func.count(PostORM.id).desc(), TagORM.id.asc())
            .limit(1)
        ).mappings().first()
        return dict(row) if row else None

    def with_counts(self, limit: int = 10) -> list[dict]:
        """Ranking de tags por cantidad de posts (incluye los que tienen 0)."""
        rows = self.db.execute(
            select(TagORM.id, TagORM.name, func.count(post_tags.c.post_id).label("uses"))
            .outerjoin(post_tags, post_tags.c.tag_id == TagORM.id)
            .group_by(TagORM.id, TagORM.name)
            .order_by(func.count(post_tags.c.post_id).desc(), TagORM.name.asc())
            .limit(limit)
        ).mappings().all()
        return [dict(r) for r in rows]
