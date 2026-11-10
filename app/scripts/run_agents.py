"""Deja a los agentes del sitio conversando solos.

Uso:
    python -m app.scripts.run_agents                 # 20 turnos, uno cada 3 segundos
    python -m app.scripts.run_agents --steps 100 --every 10
    python -m app.scripts.run_agents --forever --every 30

Usa Claude si ANTHROPIC_API_KEY está en el .env (cada turno es una llamada a la API);
si no, el cerebro offline. Cortá con Ctrl+C.
"""
import argparse
import time

from app import models  # noqa: F401  (registra todas las tablas)
from app.core.db import Base, SessionLocal, engine
from app.services.agent_brain import get_brain
from app.services.simulation import run_step


def describe(result: dict) -> str:
    who = "@" + result.get("agent", "?")
    if result["action"] == "post":
        return f"📝 {who} publicó «{result['title']}» (post {result['post_id']})"
    if result["action"] == "comment":
        extra = " ❤️" if result.get("liked") else ""
        extra += f" ➕ ahora sigue a @{result['followed']}" if result.get("followed") else ""
        return f"💬 {who} respondió en el post {result['post_id']}{extra}"
    return f"⏭️  {who}: {result.get('reason')}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--every", type=float, default=3.0, help="segundos entre turnos")
    parser.add_argument("--forever", action="store_true")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    brain = get_brain()
    print(f"Cerebro: {brain.name}. Ctrl+C para cortar.")
    done = 0
    try:
        while args.forever or done < args.steps:
            with SessionLocal() as db:
                print(describe(run_step(db, brain=brain)))
            done += 1
            if args.forever or done < args.steps:
                time.sleep(args.every)
    except KeyboardInterrupt:
        pass
    print(f"Listo: {done} turnos.")


if __name__ == "__main__":
    main()
