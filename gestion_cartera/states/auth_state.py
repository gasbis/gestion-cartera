from typing import TypedDict

import reflex as rx

from gestion_cartera.auth_db import (
    crear_usuario,
    email_existe,
    establecer_activo,
    establecer_password,
    listar_usuarios,
    obtener_usuario_por_email,
    verify_password,
)


class UsuarioActual(TypedDict):
    id: int
    email: str
    nombre: str


class UsuarioDirectorio(TypedDict):
    email: str
    nombre: str
    activo: bool


USUARIO_VACIO: UsuarioActual = UsuarioActual(id=0, email="", nombre="")


class AuthState(rx.State):
    is_authenticated: bool = False
    # Si es True, la app debe mostrar la pantalla de cambio de contraseña
    # obligatorio en vez del contenido normal (ver components/auth_guard.py).
    must_change_password: bool = False
    current_user: UsuarioActual = USUARIO_VACIO

    usuarios: list[UsuarioDirectorio] = []

    email_error: str = ""
    password_error: str = ""
    auth_error: str = ""

    nuevo_usuario_open: bool = False
    nuevo_usuario_email_error: str = ""
    nuevo_usuario_error: str = ""

    change_password_current_error: str = ""
    change_password_new_error: str = ""
    change_password_error: str = ""

    def set_nuevo_usuario_open(self, value: bool):
        self.nuevo_usuario_open = value

    def abrir_nuevo_usuario(self):
        self.nuevo_usuario_email_error = ""
        self.nuevo_usuario_error = ""
        self.nuevo_usuario_open = True

    def crear_usuario_nuevo(self, form_data: dict):
        self.nuevo_usuario_email_error = ""
        self.nuevo_usuario_error = ""

        email = form_data.get("email", "").strip().lower()
        nombre = form_data.get("nombre", "").strip()
        password = form_data.get("password", "")

        if not email or "@" not in email:
            self.nuevo_usuario_email_error = "Introduce un correo válido."
            return
        if email_existe(email):
            self.nuevo_usuario_email_error = "Ya existe un usuario con ese correo."
            return
        if len(password) < 8:
            self.nuevo_usuario_error = (
                "La contraseña inicial debe tener al menos 8 caracteres."
            )
            return

        if not crear_usuario(email, nombre, password):
            self.nuevo_usuario_error = "No se ha podido crear el usuario."
            return

        self._recargar_usuarios()
        self.nuevo_usuario_open = False

    def cargar_usuarios(self):
        if not self.is_authenticated:
            return
        self._recargar_usuarios()

    def _recargar_usuarios(self):
        self.usuarios = [
            UsuarioDirectorio(email=u.email, nombre=u.nombre, activo=u.activo)
            for u in listar_usuarios()
        ]

    def alternar_activo(self, email: str):
        if email == self.current_user["email"]:
            return  # no te puedes desactivar a ti mismo
        usuario = obtener_usuario_por_email(email)
        if usuario is None:
            return
        establecer_activo(email, not usuario.activo)
        self._recargar_usuarios()

    def sign_in(self, form_data: dict):
        self.email_error = ""
        self.password_error = ""
        self.auth_error = ""

        email = form_data.get("email", "").strip().lower()
        password = form_data.get("password", "")

        if not email:
            self.email_error = "Introduce tu correo electrónico."
        if not password:
            self.password_error = "Introduce tu contraseña."
        if self.email_error or self.password_error:
            return

        usuario = obtener_usuario_por_email(email)
        if (
            usuario is None
            or not usuario.activo
            or not verify_password(password, usuario.password_hash)
        ):
            self.auth_error = "No hemos podido verificar tus credenciales."
            return

        self.is_authenticated = True
        self.must_change_password = usuario.debe_cambiar_password
        self.current_user = UsuarioActual(
            id=usuario.id, email=usuario.email, nombre=usuario.nombre
        )

        # El login se hace "in situ": `requiere_login` sustituye la
        # pantalla de login por el contenido real de la MISMA página, sin
        # navegar a ninguna URL nueva. Como el `on_load` de cada página
        # (donde cada state carga sus datos reales) solo se dispara en una
        # navegación, y aquí no ha habido ninguna, el contenido aparece
        # vacío hasta que el usuario cambia de página y vuelve. Forzar un
        # redirect a la MISMA ruta cuenta como una navegación nueva para
        # Reflex, así que vuelve a disparar el `on_load` de esa página con
        # el usuario ya autenticado.
        #
        # OJO: `self.router.page.path` (API antigua, deprecada) da la
        # RUTA INTERNA compilada (p.ej. "/index" para la home), no la URL
        # real que ve el navegador -- redirigir ahí daba "página no
        # encontrada". `self.router.url.path` sí es la ruta tal cual está
        # en la barra de direcciones (incluye los parámetros dinámicos ya
        # resueltos, p.ej. "/valor/27").
        return rx.redirect(self.router.url.path)

    def logout(self):
        self.is_authenticated = False
        self.must_change_password = False
        self.current_user = USUARIO_VACIO

    def cambiar_password(self, form_data: dict):
        self.change_password_current_error = ""
        self.change_password_new_error = ""
        self.change_password_error = ""

        actual = obtener_usuario_por_email(self.current_user["email"])
        if actual is None or not verify_password(
            form_data.get("current_password", ""), actual.password_hash
        ):
            self.change_password_current_error = "La contraseña actual no es correcta."
            return

        nueva = form_data.get("new_password", "")
        confirmar = form_data.get("confirm_password", "")
        if len(nueva) < 8:
            self.change_password_new_error = (
                "La nueva contraseña debe tener al menos 8 caracteres."
            )
            return
        if nueva != confirmar:
            self.change_password_new_error = "Las contraseñas no coinciden."
            return

        establecer_password(self.current_user["email"], nueva)
        self.must_change_password = False