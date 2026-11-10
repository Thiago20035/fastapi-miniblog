from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role
from app.models import AgentORM
from app.services.agent_brain import get_brain
from app.services.simulation import run_step

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.get("/status")
def simulation_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Qué cerebro usan los agentes del sitio y cuántos hay."""
    site_agents = db.scalar(select(func.count()).select_from(AgentORM).where(
        AgentORM.persona.is_not(None), AgentORM.is_active.is_(True))) or 0
    return {"brain": get_brain().name, "site_agents": site_agents}


@router.post("/step", dependencies=[Depends(require_role("moderator"))])
def simulation_step(steps: int = Query(1, ge=1, le=10, description="Cuántos turnos correr"),
                    db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Moderadores: hace que los agentes del sitio conversen `steps` turnos.

    Con Claude cada turno es una llamada a la API (cuesta dinero): por eso está limitado a 10.
    """
    brain = get_brain()
    return [run_step(db, brain=brain) for _ in range(steps)]
