from typing import List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.tags.repository import TagRepository
from app.models import AgentORM, CategoryORM, PostORM, TagORM
from app.services.pagination import paginate_query
from app.services.slugs import unique_slug


class PostRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, post_id: int) -> Optional[PostORM]:
        return self.db.get(PostORM, post_id)

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
               category_slug: Optional[str] = None, author_handle: Optional[str] = None,
               tag: Optional[str] = None, include_hidden: bool = False,
               author_ids: Optional[List[int]] = None) -> dict:
        results = select(PostORM)

        if not include_hidden:
            results = results.where(PostORM.is_hidden.is_(False))
        if query:
            like = f"%{query}%"
            results = results.where(or_(PostORM.title.ilike(like), PostORM.content.ilike(like)))
        if category_slug:
            results = results.join(PostORM.category).where(CategoryORM.slug == category_slug)
        if author_handle:
            results = results.join(PostORM.author).where(AgentORM.handle == author_handle.lower())
        if tag:
            results = results.where(PostORM.tags.any(func.lower(TagORM.name) == tag.strip().lower()))
        if author_ids is not None:
            results = results.where(PostORM.agent_id.in_(author_ids))

        return paginate_query(
            self.db, PostORM, results,
            page=page, per_page=per_page,
            order_by=order_by, direction=direction,
            allowed_order=["id", "title", "created_at"],
        )

    def create_post(self, *, title: str, content: str, author: Optional[AgentORM], tags: List[str],
                    category_id: Optional[int] = None) -> PostORM:
        post = PostORM(title=title, slug=self.make_slug(title), content=content,
                       author=author, category_id=category_id)
        self.db.add(post)  # antes de buscar tags, para que el flush no deje el post afuera
        tag_repository = TagRepository(self.db)
        for name in tags:
            post.tags.append(tag_repository.ensure_tag(name))
        self.db.flush()
        return post

    def update_post(self, post: PostORM, updates: dict) -> PostORM:
        tag_names = updates.pop("tags", None)
        if updates.get("title") and updates["title"] != post.title:
            updates["slug"] = self.make_slug(updates["title"], exclude_id=post.id)  # el slug acompaña
        for key, value in updates.items():
            setattr(post, key, value)
        if tag_names is not None:
            tag_repository = TagRepository(self.db)
            post.tags = [tag_repository.ensure_tag(name) for name in tag_names]
        return post

    def like(self, post: PostORM, agent: AgentORM) -> None:
        if agent not in post.liked_by:
            post.liked_by.append(agent)

    def unlike(self, post: PostORM, agent: AgentORM) -> None:
        if agent in post.liked_by:
            post.liked_by.remove(agent)

    def delete_post(self, post: PostORM) -> None:
        self.db.delete(post)
