"""Hash de contraseñas y operaciones de base de datos sobre USUARIOS.

Separado de models.py a propósito: models.py son solo las tablas, esto
es lógica de negocio sobre ellas.
"""

import bcrypt
import reflex as rx
import sqlmodel

from gestion_cartera.models import Cartera, Usuario


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Hash corrupto o con un formato que no es el esperado.
        return False


def email_existe(email: str) -> bool:
    with rx.session() as session:
        return (
            session.exec(
                sqlmodel.select(Usuario).where(Usuario.email == email)
            ).first()
            is not None
        )


def obtener_usuario_por_email(email: str) -> Usuario | None:
    with rx.session() as session:
        return session.exec(
            sqlmodel.select(Usuario).where(Usuario.email == email)
        ).first()


def crear_usuario(email: str, nombre: str, password_inicial: str) -> bool:
    """Da de alta un usuario con una contraseña inicial (que deberá
    cambiar en su primer inicio de sesión) y le crea automáticamente sus
    dos carteras (Largo Plazo y Corto Plazo).
    """
    if email_existe(email):
        return False
    with rx.session() as session:
        usuario = Usuario(
            email=email,
            nombre=nombre,
            password_hash=hash_password(password_inicial),
            debe_cambiar_password=True,
            activo=True,
        )
        session.add(usuario)
        session.commit()
        session.refresh(usuario)

        session.add(Cartera(id_usuario=usuario.id, tipo_cartera="Largo Plazo"))
        session.add(Cartera(id_usuario=usuario.id, tipo_cartera="Corto Plazo"))
        session.commit()
    return True


def listar_usuarios() -> list[Usuario]:
    with rx.session() as session:
        return list(session.exec(sqlmodel.select(Usuario)).all())


def establecer_password(email: str, nueva_password: str) -> bool:
    with rx.session() as session:
        usuario = session.exec(
            sqlmodel.select(Usuario).where(Usuario.email == email)
        ).first()
        if usuario is None:
            return False
        usuario.password_hash = hash_password(nueva_password)
        usuario.debe_cambiar_password = False
        session.add(usuario)
        session.commit()
    return True


def establecer_activo(email: str, activo: bool) -> bool:
    with rx.session() as session:
        usuario = session.exec(
            sqlmodel.select(Usuario).where(Usuario.email == email)
        ).first()
        if usuario is None:
            return False
        usuario.activo = activo
        session.add(usuario)
        session.commit()
    return True