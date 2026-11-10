# FastAPI Mini Blog

API REST para un blog, hecha con FastAPI y SQLAlchemy. Es el proyecto que se arma a lo largo de la materia **Desarrollo de Sistemas Web (3.º año, IDRA)**, y este repo llega hasta el **Módulo 16: Seeds y Slug para post**.

## Qué hace

- **Posts**: crear (con imagen opcional), listar con búsqueda, paginación y orden, filtrar por categoría o por tags, consultar por id o por **slug**, editar y borrar.
- **Usuarios reales** guardados en la base, con contraseñas hasheadas (Argon2, usando `pwdlib`) y login con **JWT**.
- **Roles** `user` < `editor` < `admin`. Cada rol tiene los permisos del anterior.
- **Tags** (relación N a M): CRUD, búsqueda, el tag más popular y un ranking de uso. Si llegan como `"python, fastapi"` se separan por la coma.
- **Categorías** (relación 1 a N) con slug: CRUD y cantidad de posts por categoría. Borrar una categoría **no borra** sus posts.
- **Slugs** automáticos y únicos para los posts (`mi-primer-post`, `mi-primer-post-2`, ...).
- **Seeds**: usuarios de cada rol, categorías y posts de ejemplo para arrancar.
- Paginación compartida (`services/pagination.py`) y tests con `pytest`.

## Permisos

| Acción | user | editor | admin |
|---|:-:|:-:|:-:|
| Leer posts, tags y categorías | ✔ | ✔ | ✔ |
| Ver y editar su propio perfil | ✔ | ✔ | ✔ |
| Crear posts, tags y categorías; subir imágenes | | ✔ | ✔ |
| Editar o borrar **sus** posts | | ✔ | ✔ |
| Editar o borrar posts **de otros** | | | ✔ |
| Borrar categorías | | | ✔ |
| Listar usuarios, cambiar roles, desactivar o borrar usuarios | | | ✔ |

Todo el que se registra arranca como `user`, y un admin puede ascenderlo. La API no deja quitar ni borrar al último admin activo.

## Estructura

```text
app/
├── main.py
├── seeds.py                 # datos de ejemplo
├── core/
│   ├── config.py            # lee el .env (se carga primero)
│   ├── db.py
│   └── security.py          # pwdlib, JWT, get_current_user, require_role
├── models/                  # user, post, tag, category
├── services/
│   ├── file_storage.py
│   ├── pagination.py        # paginate_query reutilizable
│   └── slugs.py
├── scripts/create_admin.py
└── api/v1/
    ├── auth/  users/  posts/  tags/  categories/  uploads/
    └── common/schemas.py    # Page[T] para todos los listados
tests/
```

## Instalación (Windows, PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env      # y cambiá JWT_SECRET por una clave larga
```

Para generar una clave nueva:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

> **Si ya tenías un `blog.db` de módulos anteriores, borralo.** Las tablas cambiaron (users, categories, slug) y por ahora se crean con `create_all`, que no modifica tablas que ya existen. Alembic queda para más adelante.

## Cargar datos y ejecutar

```powershell
python -m app.seeds          # o: python -m app.seeds --reset para empezar de cero
fastapi dev app/main.py
```

Abrí `http://127.0.0.1:8000/docs`. Con el botón **Authorize** te logueás: en *username* va el **email**.

Usuarios de los seeds (contraseña `miniblog123`, o la que pongas en `SEED_PASSWORD`):

| Email | Rol |
|---|---|
| admin@miniblog.com | admin |
| editora@miniblog.com | editor |
| editor@miniblog.com | editor |
| lector@miniblog.com | user |

Para crear un admin propio sin usar los seeds: `python -m app.scripts.create_admin vos@mail.com tuusuario` (la contraseña te la pide por consola).

## Endpoints

| Método | Ruta | Quién | Para qué |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | público | Registrarse (rol `user`) |
| `POST` | `/api/v1/auth/login` | público | Login con formulario (`username` = email) |
| `POST` | `/api/v1/auth/login/json` | público | Login con JSON `{email, password}` |
| `GET` | `/api/v1/auth/me` | logueado | Usuario actual |
| `GET` / `PATCH` | `/users/me` | logueado | Ver perfil / cambiar usuario o contraseña |
| `GET` | `/users` | admin | Listar usuarios (búsqueda, rol, paginación) |
| `GET` / `DELETE` | `/users/{id}` | admin | Ver o borrar un usuario |
| `PATCH` | `/users/{id}/role` · `/users/{id}/active` | admin | Cambiar rol / activar o desactivar |
| `GET` | `/posts` | público | Listar (`search`, `category`, `page`, `per_page`, `order_by`, `direction`) |
| `GET` | `/posts/by-tags?tags=python&tags=fastapi` | público | Filtrar por tags |
| `GET` | `/posts/{id}` · `/posts/slug/{slug}` | público | Un post |
| `POST` | `/posts` | editor | Crear (multipart: `title`, `content`, `tags`, `category_id`, `image`) |
| `PUT` / `DELETE` | `/posts/{id}` | autor o admin | Editar (`title`, `content`, `category_id`, `tags`) / borrar |
| `GET` | `/tags` · `/tags/{id}` | público | Listar (con búsqueda) / ver uno |
| `GET` | `/tags/popular` · `/tags/ranking` | público | Tag más usado / ranking |
| `POST` / `PUT` / `DELETE` | `/tags` · `/tags/{id}` | editor | CRUD de tags |
| `GET` | `/categories` · `/categories/{id}` · `/categories/slug/{slug}` | público | Listar / ver |
| `GET` | `/categories/stats` | público | Posts por categoría |
| `POST` / `PATCH` | `/categories` · `/categories/{id}` | editor | Crear / editar (el slug sale del nombre si no lo mandás) |
| `DELETE` | `/categories/{id}` | admin | Borrar (los posts quedan sin categoría) |
| `POST` | `/upload/save` | editor | Subir una imagen PNG o JPEG |

## Tests

```powershell
pip install pytest
python -m pytest
```

Usan una base SQLite temporal y los seeds. Cubren permisos por rol, tags, categorías, slugs, paginación y seeds.

## Pendiente

Migraciones con Alembic, PostgreSQL, refresh tokens y despliegue.

## Autor

Base del proyecto: César Gimenez Lascano ([@cgldev](https://github.com/cgldev)). Módulos 13 a 16: Thiago Tarricone.
