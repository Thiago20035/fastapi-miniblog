"""Hace que los agentes del sitio (los que tienen `persona`) conversen entre ellos.

Cada "paso" elige un agente al azar y decide:
  - publicar un post nuevo (más probable si hay pocos posts), o
  - responder un post reciente de otro agente (a veces respondiendo a un comentario puntual),
  - y de paso, a veces da like o empieza a seguir al autor.

Lo usan el endpoint POST /simulation/step y el script `python -m app.scripts.run_agents`.
"""
from __future__ import annotations

import random
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.posts.repository import PostRepository
from app.core.config import settings
from app.models import AgentORM, CategoryORM, CommentORM, PostORM
from app.services.agent_brain import Brain, Line, get_brain
from app.services.moderation import is_family_friendly
from app.services.rate_limit import recent_actions
from app.services.slugs import slugify


def _site_agents(db: Session) -> list[AgentORM]:
    return list(db.execute(select(AgentORM).where(
        AgentORM.persona.is_not(None), AgentORM.is_active.is_(True)).order_by(AgentORM.id)).scalars())


def _recent_posts(db: Session, limit: int = 15) -> list[PostORM]:
    return list(db.execute(select(PostORM).where(PostORM.is_hidden.is_(False))
                           .order_by(PostORM.id.desc()).limit(limit)).scalars().unique())


def _find_community(db: Session, name: Optional[str]) -> Optional[CategoryORM]:
    if not name:
        return None
    return db.execute(select(CategoryORM).where(CategoryORM.slug == slugify(name))).scalars().first()


def _publish_post(db: Session, brain: Brain, agent: AgentORM, recent: list[PostORM]) -> dict:
    communities = [c.name for c in db.execute(select(CategoryORM).order_by(CategoryORM.name)).scalars()]
    draft = brain.write_post(agent, communities, [p.title for p in recent])
    if not draft:
        return {"action": "skipped", "agent": agent.handle, "reason": "el cerebro no devolvió un post"}
    if not is_family_friendly(draft.title, draft.content, *draft.tags):
        return {"action": "skipped", "agent": agent.handle, "reason": "no pasó el filtro family-friendly"}
    community = _find_community(db, draft.community)
    post = PostRepository(db).create_post(title=draft.title, content=draft.content, author=agent,
                                          tags=draft.tags, category_id=community.id if community else None)
    db.flush()
    return {"action": "post", "agent": agent.handle, "post_id": post.id, "title": post.title}


def _publish_comment(db: Session, brain: Brain, agent: AgentORM, post: PostORM, rng: random.Random) -> dict:
    visible = [c for c in post.comments if not c.is_hidden]
    others = [c for c in visible if c.agent_id != agent.id and c.author]
    parent: Optional[CommentORM] = rng.choice(others[-3:]) if others and rng.random() < 0.5 else None
    reply_to = parent.author.handle if parent else (post.author.handle if post.author else "todos")
    thread = [Line(c.author.handle if c.author else "anónimo", c.content) for c in visible]

    text = brain.write_reply(agent, post.title, post.author.handle if post.author else "anónimo",
                             post.content, thread, reply_to)
    if not text:
        return {"action": "skipped", "agent": agent.handle, "reason": "el cerebro no devolvió una respuesta"}
    if not is_family_friendly(text):
        return {"action": "skipped", "agent": agent.handle, "reason": "no pasó el filtro family-friendly"}

    comment = CommentORM(post=post, author=agent, content=text, parent_id=parent.id if parent else None)
    db.add(comment)
    db.flush()

    result = {"action": "comment", "agent": agent.handle, "post_id": post.id, "comment_id": comment.id}
    if rng.random() < 0.6 and agent not in post.liked_by:
        post.liked_by.append(agent)
        result["liked"] = True
    if post.author and post.author.id != agent.id and post.author not in agent.following and rng.random() < 0.3:
        agent.following.append(post.author)
        result["followed"] = post.author.handle
    return result


def run_step(db: Session, brain: Optional[Brain] = None, rng: Optional[random.Random] = None) -> dict:
    """Un turno de la conversación. Hace commit y devuelve qué pasó."""
    rng = rng or random.Random()
    brain = brain or get_brain()

    agents = [a for a in _site_agents(db) if recent_actions(db, a) < settings.AGENT_ACTIONS_PER_MINUTE]
    if not agents:
        return {"action": "skipped", "reason": "no hay agentes del sitio disponibles (¿corriste los seeds?)",
                "brain": brain.name}
    agent = rng.choice(agents)
    recent = _recent_posts(db)
    others_posts = [p for p in recent if p.agent_id != agent.id]

    wants_new_post = not others_posts or rng.random() < (0.5 if len(recent) < 5 else 0.25)
    if wants_new_post:
        result = _publish_post(db, brain, agent, recent)
    else:
        # Preferimos posts con poca charla, para que nadie quede sin respuesta
        weights = [1 / (1 + p.comments_count) for p in others_posts]
        post = rng.choices(others_posts, weights=weights, k=1)[0]
        result = _publish_comment(db, brain, agent, post, rng)

    db.commit()
    result["brain"] = brain.name
    return result
