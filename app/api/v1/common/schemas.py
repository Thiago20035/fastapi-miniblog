from typing import Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Respuesta paginada genérica, compartida por todos los listados."""

    page: int
    per_page: int
    total: int
    total_pages: int
    has_prev: bool
    has_next: bool
    order_by: str
    direction: Literal["asc", "desc"]
    search: Optional[str] = None
    items: List[T]
