from tests.conftest import login


# ------------------------------------------------------------------ Users / Auth
def test_registro_login_y_perfil(client):
    r = client.post("/api/v1/auth/register",
                    json={"email": "Nueva@Test.com", "username": "nueva", "password": "clave1234"})
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "user" and body["email"] == "nueva@test.com"
    assert "password" not in body and "hashed_password" not in body

    assert client.post("/api/v1/auth/register",
                       json={"email": "nueva@test.com", "username": "otra", "password": "clave1234"}).status_code == 409
    assert client.post("/api/v1/auth/login",
                       data={"username": "nueva@test.com", "password": "mala"}).status_code == 401

    h = login(client, "nueva@test.com", "clave1234")
    assert client.get("/users/me", headers=h).json()["username"] == "nueva"
    r = client.post("/api/v1/auth/login/json", json={"email": "nueva@test.com", "password": "clave1234"})
    assert r.status_code == 200


def test_sin_token_o_token_invalido(client):
    assert client.get("/users/me").status_code == 401
    assert client.get("/users/me", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401


def test_roles(client, admin, editora, lector):
    nuevo = {"title": "Post del lector", "content": "contenido suficiente"}
    assert client.post("/posts", data=nuevo, headers=lector).status_code == 403
    assert client.get("/users", headers=lector).status_code == 403
    assert client.get("/users", headers=editora).status_code == 403
    assert client.get("/users", headers=admin).json()["total"] == 4

    lector_id = client.get("/users/me", headers=lector).json()["id"]
    assert client.patch(f"/users/{lector_id}/role", json={"role": "editor"}, headers=admin).json()["role"] == "editor"
    assert client.post("/posts", data=nuevo, headers=lector).status_code == 201


def test_no_se_puede_quedar_sin_admin(client, admin):
    admin_id = client.get("/users/me", headers=admin).json()["id"]
    assert client.patch(f"/users/{admin_id}/role", json={"role": "user"}, headers=admin).status_code == 400
    assert client.delete(f"/users/{admin_id}", headers=admin).status_code == 400


def test_usuario_desactivado(client, admin, lector):
    lector_id = client.get("/users/me", headers=lector).json()["id"]
    client.patch(f"/users/{lector_id}/active", json={"is_active": False}, headers=admin)
    assert client.get("/users/me", headers=lector).status_code == 401
    r = client.post("/api/v1/auth/login", data={"username": "lector@miniblog.com", "password": "miniblog123"})
    assert r.status_code == 403


def test_borrar_usuario_deja_sus_posts_sin_autor(client, admin, editor):
    editor_id = client.get("/users/me", headers=editor).json()["id"]
    post = client.get("/posts/slug/relaciones-en-sqlalchemy-1-a-n-y-n-a-m").json()
    assert post["user"]["username"] == "editor"
    assert client.delete(f"/users/{editor_id}", headers=admin).status_code == 204
    assert client.get(f"/posts/{post['id']}").json()["user"] is None


def test_cambio_de_contrasena(client, lector):
    r = client.patch("/users/me", json={"current_password": "mal", "new_password": "nueva12345"}, headers=lector)
    assert r.status_code == 400
    r = client.patch("/users/me", json={"current_password": "miniblog123", "new_password": "nueva12345"}, headers=lector)
    assert r.status_code == 200
    login(client, "lector@miniblog.com", "nueva12345")


# ------------------------------------------------------------------ Posts
def test_editor_solo_edita_sus_posts(client, admin, editor, editora):
    post = client.get("/posts/slug/jwt-explicado-sin-vueltas").json()  # es de "editora"
    assert client.put(f"/posts/{post['id']}", json={"title": "Hackeado"}, headers=editor).status_code == 403
    assert client.put(f"/posts/{post['id']}", json={"content": "contenido nuevo ok"}, headers=editora).status_code == 200
    assert client.put(f"/posts/{post['id']}", json={"content": "lo edita el admin"}, headers=admin).status_code == 200
    assert client.delete(f"/posts/{post['id']}", headers=editor).status_code == 403
    assert client.delete(f"/posts/{post['id']}", headers=editora).status_code == 204


def test_listado_paginado_busqueda_y_filtros(client):
    r = client.get("/posts?per_page=3&page=2").json()
    assert r["total"] == 8 and r["total_pages"] == 3 and r["has_prev"] and r["has_next"]
    assert len(r["items"]) == 3

    assert client.get("/posts?search=JWT").json()["total"] == 1
    seguridad = client.get("/posts?category=seguridad").json()
    assert seguridad["total"] == 2
    assert all(p["category"]["slug"] == "seguridad" for p in seguridad["items"])
    assert len(client.get("/posts/by-tags?tags=Seguridad").json()) == 2


def test_titulo_duplicado(client, editora):
    data = {"title": "JWT explicado sin vueltas", "content": "contenido repetido"}
    assert client.post("/posts", data=data, headers=editora).status_code == 409


# ------------------------------------------------------------------ Tags
def test_tags_separados_por_coma(client, editora):
    r = client.post("/posts", data={"title": "Tags con comas", "content": "contenido suficiente",
                                    "tags": "Python, FastAPI ,python,  nuevo-tag"}, headers=editora)
    assert r.status_code == 201
    names = [t["name"] for t in r.json()["tags"]]
    assert sorted(names) == ["fastapi", "nuevo-tag", "python"]  # sin duplicados ni mayúsculas


def test_crud_de_tags(client, editora, lector):
    assert client.post("/tags", json={"name": "Docker"}, headers=lector).status_code == 403
    r = client.post("/tags", json={"name": "Docker"}, headers=editora)
    assert r.status_code == 201 and r.json()["name"] == "docker"
    tag_id = r.json()["id"]
    assert client.post("/tags", json={"name": "DOCKER"}, headers=editora).status_code == 409
    assert client.put(f"/tags/{tag_id}", json={"name": "kubernetes"}, headers=editora).json()["name"] == "kubernetes"
    assert client.get("/tags?search=kube").json()["total"] == 1
    assert client.delete(f"/tags/{tag_id}", headers=editora).status_code == 204
    assert client.delete(f"/tags/{tag_id}", headers=editora).status_code == 404


def test_tag_mas_popular(client):
    popular = client.get("/tags/popular").json()
    assert popular["name"] == "fastapi" and popular["uses"] == 6
    ranking = client.get("/tags/ranking?limit=3").json()
    assert ranking[0]["name"] == "fastapi" and len(ranking) == 3


# ------------------------------------------------------------------ Categorías
def test_crud_de_categorias(client, admin, editora):
    r = client.post("/categories", json={"name": "Inteligencia Artificial"}, headers=editora)
    assert r.status_code == 201 and r.json()["slug"] == "inteligencia-artificial"
    cat_id = r.json()["id"]

    r = client.post("/categories", json={"name": "Otra", "slug": "inteligencia-artificial"}, headers=editora)
    assert r.status_code == 400 and r.json()["detail"] == "Slug en uso"
    assert client.post("/categories", json={"name": "Mal", "slug": "Con Espacios"}, headers=editora).status_code == 422

    r = client.patch(f"/categories/{cat_id}", json={"name": "IA"}, headers=editora)
    assert r.json() == {"id": cat_id, "name": "IA", "slug": "inteligencia-artificial"}
    assert client.get("/categories/slug/inteligencia-artificial").json()["name"] == "IA"


def test_post_con_categoria(client, editora):
    cat = client.get("/categories/slug/carrera").json()
    r = client.post("/posts", data={"title": "Con categoría", "content": "contenido suficiente",
                                    "category_id": str(cat["id"])}, headers=editora)
    assert r.status_code == 201 and r.json()["category"]["slug"] == "carrera"

    r = client.post("/posts", data={"title": "Categoría inexistente", "content": "contenido suficiente",
                                    "category_id": "999"}, headers=editora)
    assert r.status_code == 400


def test_borrar_categoria_no_borra_posts(client, admin, editora):
    cat = client.get("/categories/slug/seguridad").json()
    assert client.delete(f"/categories/{cat['id']}", headers=editora).status_code == 403
    assert client.delete(f"/categories/{cat['id']}", headers=admin).status_code == 204
    assert client.get("/posts").json()["total"] == 8
    assert client.get("/posts/slug/jwt-explicado-sin-vueltas").json()["category"] is None


# ------------------------------------------------------------------ Slugs
def test_slug_de_posts(client, editora):
    r = client.post("/posts", data={"title": "¡Programación en Python, año 2026!", "content": "contenido suficiente"},
                    headers=editora)
    assert r.json()["slug"] == "programacion-en-python-ano-2026"

    r = client.post("/posts", data={"title": "JWT: explicado sin vueltas", "content": "contenido suficiente"},
                    headers=editora)
    assert r.json()["slug"] == "jwt-explicado-sin-vueltas-2"

    post_id = r.json()["id"]
    r = client.put(f"/posts/{post_id}", json={"title": "Título totalmente nuevo"}, headers=editora)
    assert r.json()["slug"] == "titulo-totalmente-nuevo"
    assert client.get("/posts/slug/titulo-totalmente-nuevo").json()["id"] == post_id
    assert client.get("/posts/slug/no-existe").status_code == 404


# ------------------------------------------------------------------ Seeds
def test_seeds_idempotentes(client):
    from app.seeds import seed

    assert seed() == {"users": 0, "categories": 0, "posts": 0}
    assert client.get("/posts").json()["total"] == 8
