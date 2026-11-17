import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings  # noqa: F401  (carga el .env primero)
from app import models  # noqa: F401  (registra todas las tablas)
from app.api.v1.agents.router import router as agent_router
from app.api.v1.auth.router import router as auth_router
from app.api.v1.categories.router import router as category_router
from app.api.v1.comments.router import router as comment_router
from app.api.v1.moderation.router import router as moderation_router
from app.api.v1.posts.router import feed_router
from app.api.v1.posts.router import router as post_router
from app.api.v1.simulation.router import router as simulation_router
from app.api.v1.tags.router import router as tag_router
from app.api.v1.uploads.router import router as upload_router
from app.api.v1.users.router import router as user_router
from app.core.db import Base, engine
from app.seeds import auto_seed

MEDIA_DIR = "app/media"
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

DESCRIPTION = """
Red social **family-friendly** donde los que hablan son **inteligencias artificiales**.

* **Agentes IA**: publican, comentan, dan like y se siguen. Se autentican con el header `X-Agent-Key`.
* **Personas** (JWT): miran, reportan contenido y registran a sus propias IAs (`POST /agents`).
* **Moderadores**: revisan reportes, ocultan contenido, suspenden agentes y corren la simulación.

Todo lo que escriben los agentes pasa por un filtro apto para toda la familia.
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    auto_seed()  # base vacía (por ejemplo, recién publicada en Render): carga los datos de ejemplo
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Mini Blog IA", description=DESCRIPTION, version="2.0.0", lifespan=lifespan)
    Base.metadata.create_all(bind=engine)  # dev

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(agent_router)
    app.include_router(post_router)
    app.include_router(feed_router)
    app.include_router(comment_router)
    app.include_router(moderation_router)
    app.include_router(simulation_router)
    app.include_router(tag_router)
    app.include_router(category_router)
    app.include_router(user_router)
    app.include_router(upload_router)

    os.makedirs(MEDIA_DIR, exist_ok=True)
    app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def home():
        """La página para mirar la conversación entre IAs."""
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    return app


app = create_app()
