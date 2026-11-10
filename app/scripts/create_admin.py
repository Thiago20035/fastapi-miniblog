"""Crea (o asciende) un usuario administrador.

Uso:
    python -m app.scripts.create_admin admin@miniblog.com admin
La contraseña se pide por consola (no queda en el historial).
"""
import getpass
import sys

from app.api.v1.users.repository import UserRepository
from app.core.db import Base, SessionLocal, engine
from app import models  # noqa: F401


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    email, username = sys.argv[1], sys.argv[2]

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        repository = UserRepository(db)
        user = repository.get_by_email(email)
        if user:
            user.role = "admin"
            print(f"{email} ya existía: ahora es admin.")
        else:
            password = getpass.getpass("Contraseña (mínimo 8 caracteres): ")
            if len(password) < 8:
                sys.exit("La contraseña es demasiado corta.")
            repository.create(email=email, username=username, password=password, role="admin")
            print(f"Admin {email} creado.")
        db.commit()


if __name__ == "__main__":
    main()
