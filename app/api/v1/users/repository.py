from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import UserORM
from app.services.pagination import paginate_query


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int) -> Optional[UserORM]:
        return self.db.get(UserORM, user_id)

    def get_by_email(self, email: str) -> Optional[UserORM]:
        query = select(UserORM).where(func.lower(UserORM.email) == email.strip().lower())
        return self.db.execute(query).scalars().first()

    def get_by_username(self, username: str) -> Optional[UserORM]:
        query = select(UserORM).where(func.lower(UserORM.username) == username.strip().lower())
        return self.db.execute(query).scalars().first()

    def create(self, *, email: str, username: str, password: str, role: str = "user") -> UserORM:
        user = UserORM(
            email=email.strip().lower(),
            username=username.strip(),
            hashed_password=hash_password(password),
            role=role,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def authenticate(self, email: str, password: str) -> Optional[UserORM]:
        user = self.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            return None
        return user

    def paginate(self, search: Optional[str], role: Optional[str], page: int, per_page: int,
                 order_by: str, direction: str) -> dict:
        query = select(UserORM)
        if search:
            like = f"%{search}%"
            query = query.where(or_(UserORM.email.ilike(like), UserORM.username.ilike(like)))
        if role:
            query = query.where(UserORM.role == role)
        return paginate_query(
            self.db, UserORM, query,
            page=page, per_page=per_page,
            order_by=order_by, direction=direction,
            allowed_order=["id", "email", "username", "created_at"],
        )

    def count_admins(self) -> int:
        return self.db.scalar(
            select(func.count()).select_from(UserORM).where(
                UserORM.role == "admin", UserORM.is_active.is_(True))
        ) or 0

    def delete(self, user: UserORM) -> None:
        self.db.delete(user)
