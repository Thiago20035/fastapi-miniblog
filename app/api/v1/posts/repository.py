from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload, joinedload
from app.models import CategoryORM, PostORM, TagORM, UserORM
from app.api.v1.tags.repository import TagRepository
from app.services.pagination import paginate_query
from app.services.slugs import unique_slug


class PostRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, post_id: int) -> Optional[PostORM]:
        post_find = select(PostORM).where(PostORM.id == post_id)
        return self.db.execute(post_find).scalar_one_or_none()

    def get_by_slug(self, slug: str) -> Optional[PostORM]:
        return self.db.execute(select(PostORM).where(PostORM.slug == slug)).scalar_one_or_none()

    def slug_taken(self, slug: str, exclude_id: Optional[int] = None) -> bool:
        query = select(PostORM.id).where(PostORM.slug == slug)
        if exclude_id is not None:
            query = query.where(PostORM.id != exclude_id)
        return self.db.execute(query).first() is not None

    def make_slug(self, title: str, exclude_id: Optional[int] = None) -> str:
        return unique_slug(title, lambda s: self.slug_taken(s, exclude_id), max_length=120)

    def search(self, query: Optional[str], order_by: str, direction: str, page: int, per_page: int,
               category_slug: Optional[str] = None) -> dict:
        results = select(PostORM)

        if query:
            results = results.where(PostORM.title.ilike(f"%{query}%"))
        if category_slug:
            results = results.join(PostORM.category).where(CategoryORM.slug == category_slug)

        return paginate_query(
            self.db, PostORM, results,
            page=page, per_page=per_page,
            order_by=order_by, direction=direction,
            allowed_order=["id", "title"],
        )

    def by_tags(self, tags: List[str]) -> List[PostORM]:
        normalized_tag_names = [tag.strip().lower()
                                for tag in tags if tag.strip()]

        if not normalized_tag_names:
            return []

        post_list = (
            select(PostORM)
            .options(
                selectinload(PostORM.tags),
                joinedload(PostORM.user),
            ).where(PostORM.tags.any(func.lower(TagORM.name).in_(normalized_tag_names)))
            .order_by(PostORM.id.asc())
        )

        return self.db.execute(post_list).scalars().all()

    def ensure_tag(self, name: str) -> TagORM:
        return TagRepository(self.db).ensure_tag(name)

    def create_post(self, title: str, content: str, user: Optional[UserORM], tags: List[dict],
                    image_url: Optional[str], category_id: Optional[int] = None) -> PostORM:
        post = PostORM(title=title, slug=self.make_slug(title), content=content,
                       image_url=image_url, user=user, category_id=category_id)
        self.db.add(post)  # antes de buscar tags, para que el flush no deje el post afuera
        for tag in tags:
            tag_obj = self.ensure_tag(tag["name"])
            post.tags.append(tag_obj)

        self.db.flush()
        self.db.refresh(post)
        return post

    def update_post(self, post: PostORM, updates: dict) -> PostORM:
        tag_names = updates.pop("tags", None)
        if updates.get("title") and updates["title"] != post.title:
            # Si cambia el título, el slug acompaña
            updates["slug"] = self.make_slug(updates["title"], exclude_id=post.id)
        for key, value in updates.items():
            setattr(post, key, value)
        if tag_names is not None:
            post.tags = [self.ensure_tag(name) for name in tag_names]

        return post

    def delete_post(self, post: PostORM) -> None:
        self.db.delete(post)
