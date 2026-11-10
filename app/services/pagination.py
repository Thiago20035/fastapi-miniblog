from math import ceil
from typing import Any, Iterable, Optional

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


def paginate_query(
    db: Session,
    model,
    base_query: Optional[Select] = None,
    page: int = 1,
    per_page: int = 10,
    order_by: Optional[str] = None,
    direction: str = "asc",
    allowed_order: Optional[Iterable[str]] = None,
) -> dict[str, Any]:
    """Pagina cualquier consulta (Posts, Tags, Usuarios, Categorías).

    - `base_query`: consulta ya filtrada; si no se pasa, se usa `select(model)`.
    - `order_by`: nombre de la columna; sólo se acepta si está en `allowed_order`.
    - El total se calcula sobre la consulta filtrada, no sobre toda la tabla.
    """
    query = base_query if base_query is not None else select(model)

    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    total_pages = ceil(total / per_page) if total else 0
    current_page = 1 if total_pages == 0 else min(max(page, 1), total_pages)

    allowed = set(allowed_order or ["id"])
    column_name = order_by if order_by in allowed else "id"
    column = getattr(model, column_name)
    if column_name in {"title", "name", "email", "username"}:
        column = func.lower(column)
    query = query.order_by(column.desc() if direction == "desc" else column.asc())

    items = (
        db.execute(query.offset((current_page - 1) * per_page).limit(per_page))
        .scalars()
        .unique()
        .all()
    )

    return {
        "page": current_page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": current_page > 1,
        "has_next": current_page < total_pages,
        "order_by": column_name,
        "direction": direction,
        "items": items,
    }
