"""Carga datos de ejemplo: usuarios con cada rol, categorías, tags y posts.

Uso:
    python -m app.seeds            # agrega lo que falte (se puede correr varias veces)
    python -m app.seeds --reset    # borra TODAS las tablas y las vuelve a crear con los datos

La contraseña de los usuarios de ejemplo se toma de SEED_PASSWORD (por defecto "miniblog123").
Son usuarios de desarrollo: no uses estos datos en producción.
"""
import os
import sys

from app import models  # noqa: F401  (registra todas las tablas)
from app.api.v1.categories.repository import CategoryRepository
from app.api.v1.posts.repository import PostRepository
from app.api.v1.users.repository import UserRepository
from app.core.db import Base, SessionLocal, engine
from app.models import PostORM
from app.services.slugs import slugify

SEED_PASSWORD = os.getenv("SEED_PASSWORD", "miniblog123")

USERS = [
    {"email": "admin@miniblog.com", "username": "admin", "role": "admin"},
    {"email": "editora@miniblog.com", "username": "editora", "role": "editor"},
    {"email": "editor@miniblog.com", "username": "editor", "role": "editor"},
    {"email": "lector@miniblog.com", "username": "lector", "role": "user"},
]

CATEGORIES = ["Programación", "Desarrollo Web", "Bases de Datos", "Seguridad", "Carrera"]

POSTS = [
    {
        "title": "Mi primer endpoint con FastAPI",
        "content": "Arrancamos con un GET que devuelve un saludo y vemos cómo FastAPI arma /docs solo.",
        "category": "Desarrollo Web", "tags": ["fastapi", "python", "principiantes"], "author": "editora",
    },
    {
        "title": "Validación de datos con Pydantic v2",
        "content": "Field, validadores y model_config: cómo evitar que entren datos inválidos a la API.",
        "category": "Programación", "tags": ["pydantic", "python", "fastapi"], "author": "editora",
    },
    {
        "title": "Relaciones en SQLAlchemy: 1 a N y N a M",
        "content": "Categorías con una ForeignKey y tags con una tabla pivote. Cuándo usar cada una.",
        "category": "Bases de Datos", "tags": ["sqlalchemy", "sql", "python"], "author": "editor",
    },
    {
        "title": "Contraseñas seguras con pwdlib y Argon2",
        "content": "Por qué nunca guardamos contraseñas en texto plano y cómo funciona el salt automático.",
        "category": "Seguridad", "tags": ["seguridad", "python"], "author": "editor",
    },
    {
        "title": "JWT explicado sin vueltas",
        "content": "Header, payload y firma. Qué va en sub y exp, y por qué el secreto vive en el .env.",
        "category": "Seguridad", "tags": ["jwt", "seguridad", "fastapi"], "author": "editora",
    },
    {
        "title": "Paginación reutilizable para cualquier tabla",
        "content": "Una sola función paginate_query para posts, tags, usuarios y categorías.",
        "category": "Desarrollo Web", "tags": ["fastapi", "sqlalchemy", "buenas-practicas"], "author": "editor",
    },
    {
        "title": "Slugs: URLs amigables para el blog",
        "content": "Pasamos de /posts/7 a /posts/slug/slugs-urls-amigables-para-el-blog y evitamos duplicados.",
        "category": "Desarrollo Web", "tags": ["seo", "fastapi"], "author": "editora",
    },
    {
        "title": "Qué aprendí armando una API REST completa",
        "content": "Repaso del miniblog: posts, usuarios con roles, tags, categorías, archivos y seeds.",
        "category": "Carrera", "tags": ["aprendizaje", "python", "fastapi"], "author": "admin",
    },
]


def seed() -> dict:
    created = {"users": 0, "categories": 0, "posts": 0}
    with SessionLocal() as db:
        users_repo = UserRepository(db)
        users = {}
        for data in USERS:
            user = users_repo.get_by_email(data["email"])
            if not user:
                user = users_repo.create(password=SEED_PASSWORD, **data)
                created["users"] += 1
            users[data["username"]] = user

        categories_repo = CategoryRepository(db)
        categories = {}
        for name in CATEGORIES:
            slug = slugify(name)
            category = categories_repo.get_by_slug(slug)
            if not category:
                category = categories_repo.create(name=name, slug=slug)
                created["categories"] += 1
            categories[name] = category

        posts_repo = PostRepository(db)
        for data in POSTS:
            exists = db.query(PostORM.id).filter(PostORM.title == data["title"]).first()
            if exists:
                continue
            posts_repo.create_post(
                title=data["title"],
                content=data["content"],
                user=users[data["author"]],
                tags=[{"name": t} for t in data["tags"]],
                image_url=None,
                category_id=categories[data["category"]].id,
            )
            created["posts"] += 1

        db.commit()
    return created


def main() -> None:
    if "--reset" in sys.argv:
        Base.metadata.drop_all(bind=engine)
        print("Tablas borradas.")
    Base.metadata.create_all(bind=engine)
    created = seed()
    print(f"Seeds cargados: {created['users']} usuarios, {created['categories']} categorías, "
          f"{created['posts']} posts nuevos.")
    print(f"Usuarios: {', '.join(u['email'] + ' (' + u['role'] + ')' for u in USERS)}")
    print("Contraseña: la de SEED_PASSWORD (por defecto miniblog123).")


if __name__ == "__main__":
    main()
