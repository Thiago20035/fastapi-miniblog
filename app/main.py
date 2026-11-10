import os
from fastapi import FastAPI
from app.core.config import settings  # noqa: F401  (carga el .env primero)
from app.core.db import Base, engine
from app.api.v1.posts.router import router as post_router
from app.api.v1.auth.router import router as auth_router
from app.api.v1.uploads.router import router as upload_router
from app.api.v1.tags.router import router as tag_router
from app.api.v1.users.router import router as user_router
from app import models  # noqa: F401  (registra todas las tablas)
from fastapi.staticfiles import StaticFiles

MEDIA_DIR = "app/media"


def create_app() -> FastAPI:
    app = FastAPI(title="Mini Blog")
    Base.metadata.create_all(bind=engine)  # dev

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(post_router)
    app.include_router(tag_router)
    app.include_router(user_router)
    app.include_router(upload_router)  # Add the upload router

    os.makedirs(MEDIA_DIR, exist_ok=True)  # Ensure media directory exists
    app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

    return app


app = create_app()
