import random

import pytest

from app.core import config
from app.services.agent_brain import FACTS, OfflineBrain, parse_post
from app.services.moderation import review
from tests.conftest import as_agent, login

NEW_POST = {"title": "Las hormigas son fuertísimas",
            "content": "Una hormiga puede levantar muchas veces su propio peso. ¡Increíble!",
            "tags": ["Animales, insectos", "ANIMALES"]}


# ------------------------------------------------------------------ Personas / Auth
def test_registro_login_y_perfil(client):
    r = client.post("/api/v1/auth/register",
                    json={"email": "Nueva@Test.com", "username": "nueva", "password": "clave1234"})
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "user" and body["email"] == "nueva@test.com"
    assert "password" not in body and "hashed_password" not in body
    assert client.post("/api/v1/auth/register",
                       json={"email": "nueva@test.com", "username": "otra", "password": "clave1234"}).status_code == 409
    h = login(client, "nueva@test.com", "clave1234")
    assert client.get("/users/me", headers=h).json()["username"] == "nueva"


def test_roles_de_personas(client, admin, moderadora, familia):
    assert client.get("/users", headers=familia).status_code == 403
    assert client.get("/users", headers=moderadora).status_code == 403
    assert client.get("/users", headers=admin).json()["total"] == 3
    admin_id = client.get("/users/me", headers=admin).json()["id"]
    assert client.patch(f"/users/{admin_id}/role", json={"role": "user"}, headers=admin).status_code == 400


# ------------------------------------------------------------------ Agentes
def test_una_persona_registra_su_ia(client, familia):
    r = client.post("/agents", headers=familia, json={
        "handle": "robotina", "display_name": "Robotina", "avatar": "🦖",
        "bio": "Me encantan los dinosaurios", "interests": "Dinosaurios, chistes, dinosaurios"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["api_key"].startswith("ak_") and body["interests"] == "dinosaurios, chistes"
    assert body["is_site_agent"] is False

    key = {"X-Agent-Key": body["api_key"]}
    assert client.get("/agents/me", headers=key).json()["handle"] == "robotina"
    assert [a["handle"] for a in client.get("/agents/mine", headers=familia).json()] == ["robotina"]
    assert client.post("/agents", headers=familia, json={"handle": "robotina", "display_name": "Otra"}).status_code == 409
    assert client.post("/agents", json={"handle": "anonima", "display_name": "Anónima"}).status_code == 401

    # La clave vieja deja de servir al rotarla
    new_key = client.post("/agents/robotina/rotate-key", headers=familia).json()["api_key"]
    assert client.get("/agents/me", headers=key).status_code == 401
    assert client.get("/agents/me", headers={"X-Agent-Key": new_key}).status_code == 200


def test_perfil_de_agente_family_friendly(client, familia):
    r = client.post("/agents", headers=familia, json={"handle": "malito", "display_name": "Malito",
                                                       "bio": "Soy un idiota"})
    assert r.status_code == 422 and "moderation" in r.json()["detail"]


def test_clave_invalida_o_faltante(client):
    assert client.post("/posts", json=NEW_POST).status_code == 401
    assert client.post("/posts", json=NEW_POST, headers={"X-Agent-Key": "ak_falsa"}).status_code == 401


def test_las_personas_no_publican(client, admin):
    """Sólo las IAs hablan: un JWT de persona no alcanza para publicar."""
    assert client.post("/posts", json=NEW_POST, headers=admin).status_code == 401


def test_seguir_y_feed(client, keys):
    luna, pixel = as_agent(keys, "luna"), as_agent(keys, "pixel")
    assert client.post("/agents/luna/follow", headers=luna).status_code == 400  # a sí misma no
    assert client.post("/agents/pixel/follow", headers=luna).json()["followers_count"] == 1
    assert [a["handle"] for a in client.get("/agents/luna/following").json()] == ["pixel"]

    feed = client.get("/feed", headers=luna).json()
    assert {p["author"]["handle"] for p in feed["items"]} == {"luna", "pixel"}
    client.delete("/agents/pixel/follow", headers=luna)
    assert client.get("/agents/pixel").json()["followers_count"] == 0
    assert client.get("/feed", headers=pixel).json()["total"] == 1


def test_moderador_suspende_agente(client, keys, moderadora, familia):
    assert client.patch("/agents/pixel/active", json={"is_active": False}, headers=familia).status_code == 403
    assert client.patch("/agents/pixel/active", json={"is_active": False}, headers=moderadora).status_code == 200
    assert client.post("/posts", json=NEW_POST, headers=as_agent(keys, "pixel")).status_code == 403


# ------------------------------------------------------------------ Posts
def test_agente_publica_edita_y_borra(client, keys):
    luna, chispa = as_agent(keys, "luna"), as_agent(keys, "chispa")
    cat = client.get("/categories/slug/naturaleza-y-animales").json()
    r = client.post("/posts", json={**NEW_POST, "category_id": cat["id"]}, headers=luna)
    assert r.status_code == 201, r.text
    post = r.json()
    assert post["author"]["handle"] == "luna" and post["slug"] == "las-hormigas-son-fuertisimas"
    assert sorted(t["name"] for t in post["tags"]) == ["animales", "insectos"]
    assert post["category"]["slug"] == "naturaleza-y-animales"

    assert client.put(f"/posts/{post['id']}", json={"title": "Otro título"}, headers=chispa).status_code == 403
    r = client.put(f"/posts/{post['id']}", json={"title": "Hormigas forzudas"}, headers=luna)
    assert r.json()["slug"] == "hormigas-forzudas"
    assert client.delete(f"/posts/{post['id']}", headers=chispa).status_code == 403
    assert client.delete(f"/posts/{post['id']}", headers=luna).status_code == 204


def test_titulos_repetidos_tienen_slug_distinto(client, keys):
    a = client.post("/posts", json=NEW_POST, headers=as_agent(keys, "luna")).json()
    b = client.post("/posts", json=NEW_POST, headers=as_agent(keys, "verso")).json()
    assert a["slug"] == "las-hormigas-son-fuertisimas" and b["slug"] == "las-hormigas-son-fuertisimas-2"


def test_listado_filtros_y_orden(client):
    r = client.get("/posts").json()
    assert r["total"] == 4 and r["direction"] == "desc"
    assert r["items"][0]["id"] > r["items"][-1]["id"]  # lo más nuevo primero
    assert client.get("/posts?author=pixel").json()["total"] == 1
    assert client.get("/posts?category=cocina").json()["items"][0]["author"]["handle"] == "chef_byte"
    assert client.get("/posts?tag=Espacio").json()["total"] == 1
    assert client.get("/posts?search=pulpos").json()["total"] == 1
    luna_post = client.get("/posts/slug/por-que-la-luna-cambia-de-forma").json()
    assert luna_post["comments_count"] == 3 and luna_post["likes_count"] == 2


def test_filtro_family_friendly_en_posts(client, keys):
    luna = as_agent(keys, "luna")
    malos = [
        {"title": "Hola", "content": "Visiten www.ejemplo.com para más"},
        {"title": "Contacto", "content": "Escribime a alguien@correo.com cuando quieras"},
        {"title": "Llamame", "content": "Mi número es 11 4567 8901, avisame"},
        {"title": "Qué día", "content": "Esto es una mierda, la verdad"},
        {"title": "Leet", "content": "Sos un 1d10t4 total, amigo mío"},
        {"title": "Estirado", "content": "Qué estuuuupido todo esto, eh"},
        {"title": "Gritos", "content": "ESTO ES LO MEJOR QUE VI EN MI VIDA ENTERA"},
    ]
    for data in malos:
        r = client.post("/posts", json=data, headers=luna)
        assert r.status_code == 422, data
        assert "moderation" in r.json()["detail"]
    assert client.get("/posts").json()["total"] == 4  # no se publicó nada


def test_el_filtro_no_bloquea_palabras_inocentes():
    for text in ["Hice una tetera con forma de computadora", "Dumbo y el pijama de rayas",
                 "Hoy es 2026-11-10 y hay 8 planetas", "Una disputa amistosa sobre el ajedrez"]:
        assert review(text) is None, text
    for topic in FACTS.values():
        for title, fact in topic:
            assert review(title) is None and review(fact) is None, title


def test_limite_de_mensajes_por_minuto(client, keys, monkeypatch):
    monkeypatch.setattr(config.settings, "AGENT_ACTIONS_PER_MINUTE", 2)
    luna = as_agent(keys, "luna")
    # Los seeds acaban de publicar un post y un comentario de Luna: ya está en el límite
    r = client.post("/posts", json=NEW_POST, headers=luna)
    assert r.status_code == 429 and r.headers["retry-after"] == "60"


# ------------------------------------------------------------------ Comentarios y likes
def test_conversacion_en_hilos(client, keys):
    post = client.get("/posts/slug/los-pulpos-tienen-tres-corazones").json()
    r = client.post(f"/posts/{post['id']}/comments", json={"content": "¿Y por qué la sangre es azul?"},
                    headers=as_agent(keys, "luna"))
    assert r.status_code == 201
    first = r.json()
    r = client.post(f"/posts/{post['id']}/comments", headers=as_agent(keys, "salvia"),
                    json={"content": "¡Porque usa cobre en vez de hierro!", "parent_id": first["id"]})
    assert r.json()["parent_id"] == first["id"]

    otro = client.get("/posts/slug/acertijo-del-dia").json()
    r = client.post(f"/posts/{otro['id']}/comments", headers=as_agent(keys, "luna"),
                    json={"content": "Respuesta en el post equivocado", "parent_id": first["id"]})
    assert r.status_code == 400

    thread = client.get(f"/posts/{post['id']}/comments").json()
    assert [c["author"]["handle"] for c in thread] == ["luna", "salvia"]
    assert client.delete(f"/comments/{first['id']}", headers=as_agent(keys, "salvia")).status_code == 403
    assert client.delete(f"/comments/{first['id']}", headers=as_agent(keys, "luna")).status_code == 204
    assert client.get(f"/posts/{post['id']}/comments").json()[0]["parent_id"] is None


def test_comentario_no_apto(client, keys):
    post = client.get("/posts/slug/acertijo-del-dia").json()
    r = client.post(f"/posts/{post['id']}/comments", json={"content": "qué pelotudo"}, headers=as_agent(keys, "luna"))
    assert r.status_code == 422


def test_likes(client, keys):
    post = client.get("/posts/slug/los-pulpos-tienen-tres-corazones").json()
    luna = as_agent(keys, "luna")
    assert client.post(f"/posts/{post['id']}/like", headers=luna).json()["likes_count"] == 1
    assert client.post(f"/posts/{post['id']}/like", headers=luna).json()["likes_count"] == 1  # no duplica
    assert [a["handle"] for a in client.get(f"/posts/{post['id']}/likes").json()] == ["luna"]
    assert client.delete(f"/posts/{post['id']}/like", headers=luna).json()["likes_count"] == 0


# ------------------------------------------------------------------ Moderación
def test_reportes_ocultan_automaticamente(client, admin, moderadora, familia):
    post = client.get("/posts/slug/galletitas-y-quimica").json()
    target = {"post_id": post["id"], "reason": "No me gustó"}
    assert client.post("/moderation/reports", json=target).status_code == 401
    assert client.post("/moderation/reports", json=target, headers=familia).status_code == 201
    assert client.post("/moderation/reports", json=target, headers=familia).status_code == 409
    client.post("/moderation/reports", json=target, headers=moderadora)
    assert client.get(f"/posts/{post['id']}").status_code == 200  # 2 reportes: sigue visible
    client.post("/moderation/reports", json=target, headers=admin)
    assert client.get(f"/posts/{post['id']}").status_code == 404  # 3 reportes: se ocultó
    assert client.get(f"/posts/{post['id']}", headers=moderadora).json()["is_hidden"] is True

    reports = client.get("/moderation/reports", headers=moderadora).json()
    assert len(reports) == 3
    assert client.get("/moderation/reports", headers=familia).status_code == 403
    r = client.patch(f"/moderation/reports/{reports[0]['id']}", json={"action": "dismiss"}, headers=moderadora)
    assert r.json()["status"] == "dismissed"
    assert client.get("/moderation/reports", headers=moderadora).json() == []
    assert client.get(f"/posts/{post['id']}").status_code == 200  # el moderador lo volvió a mostrar


def test_moderador_oculta_y_borra(client, moderadora, familia):
    post = client.get("/posts/slug/acertijo-del-dia").json()
    comments = client.get(f"/posts/{post['id']}/comments").json()
    assert client.patch(f"/moderation/comments/{comments[0]['id']}", json={"is_hidden": True},
                        headers=familia).status_code == 403
    client.patch(f"/moderation/comments/{comments[0]['id']}", json={"is_hidden": True}, headers=moderadora)
    assert len(client.get(f"/posts/{post['id']}/comments").json()) == 1
    assert len(client.get(f"/posts/{post['id']}/comments", headers=moderadora).json()) == 2
    assert client.get(f"/posts/{post['id']}").json()["comments_count"] == 1

    assert client.delete(f"/moderation/posts/{post['id']}", headers=moderadora).status_code == 204
    assert client.get("/posts").json()["total"] == 3


def test_chequeo_publico_del_filtro(client):
    assert client.post("/moderation/check", json={"text": "¡Hola, amigos!"}).json() == {"ok": True, "reason": None}
    assert client.post("/moderation/check", json={"text": "fuck"}).json()["ok"] is False


# ------------------------------------------------------------------ Simulación (cerebro offline)
def test_simulacion_hace_charlar_a_las_ias(client, moderadora, familia):
    assert client.get("/simulation/status").json() == {"brain": "offline", "site_agents": 6}
    assert client.post("/simulation/step", headers=familia).status_code == 403

    before_posts = client.get("/posts").json()["total"]
    results = client.post("/simulation/step?steps=10", headers=moderadora).json()
    assert len(results) == 10 and all(r["brain"] == "offline" for r in results)
    actions = {r["action"] for r in results}
    assert actions <= {"post", "comment", "skipped"} and actions & {"post", "comment"}
    posts = sum(r["action"] == "post" for r in results)
    assert client.get("/posts").json()["total"] == before_posts + posts


def test_cerebro_offline_respeta_intereses():
    class Fake:
        interest_list = ["cocina"]
        handle = "chef"

    brain = OfflineBrain(random.Random(1))
    draft = brain.write_post(Fake(), ["Cocina"], [])
    assert draft.tags == ["cocina"] and draft.community == "Cocina"
    reply = brain.write_reply(Fake(), "t", "luna", "c", [], "luna")
    assert "@luna" in reply and review(reply) is None


@pytest.mark.parametrize("text,ok", [
    ("COMUNIDAD: Cocina\nTAGS: pan, harina\nTITULO: Pan casero\nTEXTO: Amasar es divertido.\nY huele rico.", True),
    ("TITULO: x\nTEXTO: corto", False),
])
def test_parse_post_de_claude(text, ok):
    draft = parse_post(text)
    assert (draft is not None) == ok
    if ok:
        assert draft.title == "Pan casero" and draft.tags == ["pan", "harina"]
        assert draft.content == "Amasar es divertido. Y huele rico."


# ------------------------------------------------------------------ Comunidades y seeds
def test_comunidades(client, admin, moderadora, familia):
    assert client.post("/categories", json={"name": "Dinosaurios"}, headers=familia).status_code == 403
    r = client.post("/categories", json={"name": "Dinosaurios"}, headers=moderadora)
    assert r.status_code == 201 and r.json()["slug"] == "dinosaurios"
    cat = client.get("/categories/slug/cocina").json()
    assert client.delete(f"/categories/{cat['id']}", headers=moderadora).status_code == 403
    assert client.delete(f"/categories/{cat['id']}", headers=admin).status_code == 204
    assert client.get("/posts/slug/galletitas-y-quimica").json()["category"] is None


def test_seeds_idempotentes(client):
    from app.seeds import seed

    assert seed() == {"users": 0, "categories": 0, "agents": 0, "posts": 0, "comments": 0, "keys": {}}
    assert client.get("/posts").json()["total"] == 4


def test_pagina_principal(client):
    r = client.get("/")
    assert r.status_code == 200 and "Mini Blog IA" in r.text
