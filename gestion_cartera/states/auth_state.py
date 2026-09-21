from typing import TypedDict

import reflex as rx

from gestion_cartera.auth_db import (
    crear_usuario,
    email_existe,
    establecer_activo,
    establecer_nombre,
    establecer_password,
    establecer_password_temporal,
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

# Único usuario con permiso para acceder a la página de alta/gestión de
# usuarios (ver `es_admin` más abajo y `requiere_admin` en auth_guard.py).
ADMIN_EMAIL = "gasbis@hotmail.com"


class AuthState(rx.State):
    is_authenticated: bool = False
    # Si es True, la app debe mostrar la pantalla de cambio de contraseña
    # obligatorio en vez del contenido normal (ver components/auth_guard.py).
    must_change_password: bool = False
    current_user: UsuarioActual = USUARIO_VACIO

    @rx.var
    def es_admin(self) -> bool:
        """Solo ADMIN_EMAIL puede acceder a la página de Usuarios (ver
        `requiere_admin` en auth_guard.py) y ve su enlace en el menú."""
        return self.current_user["email"] == ADMIN_EMAIL

    usuarios: list[UsuarioDirectorio] = []

    email_error: str = ""
    password_error: str = ""
    auth_error: str = ""

    nuevo_usuario_open: bool = False
    nuevo_usuario_email_error: str = ""
    nuevo_usuario_error: str = ""

    # Diálogo "Restablecer contraseña" (página Usuarios, solo admin):
    # para cuando otro usuario ha olvidado la suya, ya que la app no
    # tiene servidor de correo para un flujo de recuperación por email.
    reset_password_open: bool = False
    reset_password_email: str = ""
    reset_password_nombre: str = ""
    reset_password_error: str = ""

    change_password_current_error: str = ""
    change_password_new_error: str = ""
    change_password_error: str = ""
    # Diálogo de cambio de contraseña VOLUNTARIO (menú de usuario del
    # header). No confundir con `must_change_password`, que es el
    # cambio OBLIGATORIO a pantalla completa tras el alta -- ambos usan
    # el mismo método `cambiar_password`.
    cambiar_password_dialog_open: bool = False

    nombre_error: str = ""
    cambiar_nombre_dialog_open: bool = False

    def set_nuevo_usuario_open(self, value: bool):
        self.nuevo_usuario_open = value

    def abrir_nuevo_usuario(self):
        self.nuevo_usuario_email_error = ""
        self.nuevo_usuario_error = ""
        self.nuevo_usuario_open = True

    def crear_usuario_nuevo(self, form_data: dict):
        self.nuevo_usuario_email_error = ""
        self.nuevo_usuario_error = ""

        # No basta con ocultar el botón/diálogo en la página: un event
        # handler se puede invocar igualmente desde el cliente, así que
        # la comprobación real de permiso va aquí también (ver
        # `requiere_admin` en auth_guard.py para el bloqueo de la
        # página en sí).
        if not self.is_authenticated or not self.es_admin:
            return

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
        if not self.is_authenticated or not self.es_admin:
            return
        self._recargar_usuarios()

    def _recargar_usuarios(self):
        self.usuarios = [
            UsuarioDirectorio(email=u.email, nombre=u.nombre, activo=u.activo)
            for u in listar_usuarios()
        ]

    def alternar_activo(self, email: str):
        if not self.is_authenticated or not self.es_admin:
            return
        if email == self.current_user["email"]:
            return  # no te puedes desactivar a ti mismo
        usuario = obtener_usuario_por_email(email)
        if usuario is None:
            return
        establecer_activo(email, not usuario.activo)
        self._recargar_usuarios()

    def abrir_reset_password(self, email: str, nombre: str):
        if not self.is_authenticated or not self.es_admin:
            return
        self.reset_password_email = email
        self.reset_password_nombre = nombre
        self.reset_password_error = ""
        self.reset_password_open = True

    def set_reset_password_open(self, value: bool):
        self.reset_password_open = value

    def restablecer_password_usuario(self, form_data: dict):
        self.reset_password_error = ""

        if not self.is_authenticated or not self.es_admin:
            return

        password_temporal = form_data.get("password", "")
        if len(password_temporal) < 8:
            self.reset_password_error = "La contraseña temporal debe tener al menos 8 caracteres."
            return

        if not establecer_password_temporal(self.reset_password_email, password_temporal):
            self.reset_password_error = "No se ha podido restablecer la contraseña."
            return

        self.reset_password_open = False

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

    def abrir_cambiar_password(self):
        self.change_password_current_error = ""
        self.change_password_new_error = ""
        self.change_password_error = ""
        self.cambiar_password_dialog_open = True

    def set_cambiar_password_dialog_open(self, value: bool):
        self.cambiar_password_dialog_open = value

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
        self.cambiar_password_dialog_open = False

    def abrir_cambiar_nombre(self):
        self.nombre_error = ""
        self.cambiar_nombre_dialog_open = True

    def set_cambiar_nombre_dialog_open(self, value: bool):
        self.cambiar_nombre_dialog_open = value

    def cambiar_nombre(self, form_data: dict):
        self.nombre_error = ""
        nuevo_nombre = form_data.get("nombre", "").strip()
        if not nuevo_nombre:
            self.nombre_error = "Introduce un nombre."
            return

        establecer_nombre(self.current_user["email"], nuevo_nombre)
        self.current_user = UsuarioActual(
            id=self.current_user["id"],
            email=self.current_user["email"],
            nombre=nuevo_nombre,
        )
        self.cambiar_nombre_dialog_open = False