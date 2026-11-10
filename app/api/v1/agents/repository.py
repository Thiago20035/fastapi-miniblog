from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import new_agent_key
from app.models import AgentORM, UserORM
from app.services.pagination import paginate_query


class AgentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, agent_id: int) -> Optional[AgentORM]:
        return self.db.get(AgentORM, agent_id)

    def get_by_handle(self, handle: str) -> Optional[AgentORM]:
        query = select(AgentORM).where(AgentORM.handle == handle.strip().lower().lstrip("@"))
        return self.db.execute(query).scalars().first()

    def count_owned_by(self, user: UserORM) -> int:
        return self.db.scalar(
            select(func.count()).select_from(AgentORM).where(AgentORM.owner_id == user.id)) or 0

    def create(self, *, owner: Optional[UserORM], persona: Optional[str] = None, **fields) -> tuple[AgentORM, str]:
        """Crea el agente y devuelve (agente, clave_en_texto_plano)."""
        key, key_hash = new_agent_key()
        agent = AgentORM(owner=owner, persona=persona, api_key_hash=key_hash, **fields)
        self.db.add(agent)
        self.db.flush()
        return agent, key

    def rotate_key(self, agent: AgentORM) -> str:
        key, agent.api_key_hash = new_agent_key()
        self.db.flush()
        return key

    def paginate(self, search: Optional[str], page: int, per_page: int, order_by: str, direction: str) -> dict:
        query = select(AgentORM).where(AgentORM.is_active.is_(True))
        if search:
            like = f"%{search}%"
            query = query.where(or_(AgentORM.handle.ilike(like), AgentORM.display_name.ilike(like),
                                    AgentORM.interests.ilike(like)))
        return paginate_query(
            self.db, AgentORM, query,
            page=page, per_page=per_page, order_by=order_by, direction=direction,
            allowed_order=["id", "handle", "created_at"],
        )

    def follow(self, follower: AgentORM, target: AgentORM) -> None:
        if target not in follower.following:
            follower.following.append(target)

    def unfollow(self, follower: AgentORM, target: AgentORM) -> None:
        if target in follower.following:
            follower.following.remove(target)
