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


def obtener_telefono_avisos(id_usuario: int) -> str | None:
    """Como `establecer_telefono_avisos`, pero de lectura y por id (no
    por email) -- lo usa el chequeo automático de RADAR en segundo
    plano (services/radar_scheduler.py), que recorre usuarios sin
    pasar por AuthState ni tener ninguna sesión de navegador abierta."""
    with rx.session() as session:
        usuario = session.get(Usuario, id_usuario)
        return usuario.telefono_avisos if usuario else None


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


def establecer_password_temporal(email: str, password_temporal: str) -> bool:
    """Para cuando el ADMIN restablece la contraseña de otro usuario que
    ha olvidado la suya (ver `AuthState.restablecer_password_usuario`,
    página Usuarios): a diferencia de `establecer_password` (que la usa
    el propio usuario para cambiar su contraseña de forma voluntaria o
    tras el alta), aquí se deja marcado `debe_cambiar_password=True` --
    la persona entra con esta contraseña temporal pero se ve obligada a
    ponerse una propia antes de poder usar el resto de la app, igual
    que ocurre con la contraseña inicial de un usuario nuevo.
    """
    with rx.session() as session:
        usuario = session.exec(
            sqlmodel.select(Usuario).where(Usuario.email == email)
        ).first()
        if usuario is None:
            return False
        usuario.password_hash = hash_password(password_temporal)
        usuario.debe_cambiar_password = True
        session.add(usuario)
        session.commit()
    return True


def establecer_nombre(email: str, nuevo_nombre: str) -> bool:
    with rx.session() as session:
        usuario = session.exec(
            sqlmodel.select(Usuario).where(Usuario.email == email)
        ).first()
        if usuario is None:
            return False
        usuario.nombre = nuevo_nombre
        session.add(usuario)
        session.commit()
    return True


def establecer_telefono_avisos(email: str, telefono: str | None) -> bool:
    """`telefono` ya validado/normalizado por quien llame (ver
    AuthState.cambiar_telefono_avisos) -- aquí solo se guarda. `None`
    o cadena vacía lo borra (el usuario deja de recibir avisos)."""
    with rx.session() as session:
        usuario = session.exec(
            sqlmodel.select(Usuario).where(Usuario.email == email)
        ).first()
        if usuario is None:
            return False
        usuario.telefono_avisos = telefono or None
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