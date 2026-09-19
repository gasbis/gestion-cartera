"""Estado de la página OPERACIONES: listado (con buscador y orden por
columna) y el formulario de edición/eliminación de una operación
existente.

El alta de una operación nueva NO se gestiona aquí: se sigue haciendo con
`AltaOperacionState` (components/alta_operacion_form.py), que esta página
abre dentro de un diálogo. Al guardar con éxito, `AltaOperacionState`
refresca `operaciones_raw` de este State para que el listado se actualice
sin recargar la página (ver el lazy import en `guardar_operacion`).
"""

from datetime import date

import reflex as rx

from gestion_cartera.format_utils import formatear_numero
from gestion_cartera.operaciones_db import (
    actualizar_operacion,
    buscar_operacion_compensatoria,
    calcular_saldo,
    eliminar_operacion,
    obtener_broker_id_por_nombre,
    obtener_brokers,
    obtener_cartera_id,
    obtener_operaciones,
)
from gestion_cartera.states.auth_state import AuthState

CAMPOS_ORDENABLES = ("tipo_operacion", "fecha", "ticker", "empresa", "num_titulos", "broker")

# Igual que en AltaOperacionState: tipos cuyo nº de títulos se valida
# contra el SALDO calculado (ver operaciones_db.calcular_saldo).
TIPOS_QUE_VALIDAN_SALDO = ("Venta", "Dividendo", "Prima")


class OperacionesState(rx.State):
    # --- Listado ---
    operaciones_raw: list[dict] = []
    brokers_disponibles: list[str] = []
    busqueda: str = ""
    orden_campo: str = "fecha"
    orden_desc: bool = True
    id_cartera: int = 0

    # --- Diálogo "Alta Operación" (solo controla si está abierto) ---
    alta_open: bool = False

    # --- Diálogo de edición ---
    editar_open: bool = False
    confirmar_eliminar_open: bool = False
    editando_id: int = 0
    editando_id_valor: int = 0
    editando_tipo_operacion: str = ""
    editando_fecha: str = ""
    editando_broker: str = ""
    editando_ticker: str = ""
    editando_empresa: str = ""
    editando_num_titulos: str = ""
    editando_importe: str = ""
    editando_retencion_origen: str = ""
    editando_retencion_destino: str = ""
    editando_tipo_derecho_script: str = "Compra"
    editando_observaciones: str = ""
    editar_error: str = ""

    async def cargar_datos(self):
        """on_load de /operaciones."""
        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            return

        from gestion_cartera.states.portfolio_state import PortfolioState

        portfolio_state = await self.get_state(PortfolioState)
        id_cartera = obtener_cartera_id(
            auth_state.current_user["id"], portfolio_state.selected_portfolio
        )
        self.id_cartera = id_cartera or 0
        self.operaciones_raw = obtener_operaciones(id_cartera) if id_cartera else []
        self.brokers_disponibles = obtener_brokers()

    def set_busqueda(self, value: str):
        self.busqueda = value

    def set_orden(self, campo: str):
        if campo == self.orden_campo:
            self.orden_desc = not self.orden_desc
        else:
            self.orden_campo = campo
            self.orden_desc = False

    @rx.var
    def operaciones_filtradas(self) -> list[dict]:
        texto = self.busqueda.strip().lower()
        filas = self.operaciones_raw
        if texto:
            filas = [
                f
                for f in filas
                if texto in f["tipo_operacion"].lower()
                or texto in f["ticker"].lower()
                or texto in f["empresa"].lower()
                or texto in f["broker"].lower()
            ]
        if self.orden_campo == "num_titulos":
            clave = lambda f: f["num_titulos"]
        else:
            clave = lambda f: str(f.get(self.orden_campo, "")).lower()
        return sorted(filas, key=clave, reverse=self.orden_desc)

    # --- Diálogo "Alta Operación" ---
    def abrir_alta(self):
        self.alta_open = True

    def set_alta_open(self, value: bool):
        self.alta_open = value

    def cerrar_alta(self):
        self.alta_open = False

    # --- Edición ---
    def abrir_edicion(self, item: dict):
        self.editar_error = ""
        self.editando_id = item["id"]
        self.editando_id_valor = item["id_valor"]
        self.editando_tipo_operacion = item["tipo_operacion"]
        self.editando_fecha = item["fecha"]
        self.editando_broker = item["broker"]
        self.editando_ticker = item["ticker"]
        self.editando_empresa = item["empresa"]
        self.editando_num_titulos = str(item["num_titulos"])
        self.editando_importe = str(item["importe"])
        self.editando_retencion_origen = (
            str(item["retencion_origen"]) if item["retencion_origen"] is not None else ""
        )
        self.editando_retencion_destino = (
            str(item["retencion_destino"]) if item["retencion_destino"] is not None else ""
        )
        self.editando_tipo_derecho_script = item["tipo_derecho_script"] or "Compra"
        self.editando_observaciones = item["observaciones"] or ""
        self.editar_open = True

    def set_editar_open(self, value: bool):
        self.editar_open = value

    def set_editando_fecha(self, value: str):
        self.editando_fecha = value

    def set_editando_broker(self, value: str):
        self.editando_broker = value

    def set_editando_num_titulos(self, value: str):
        self.editando_num_titulos = value

    def set_editando_importe(self, value: str):
        self.editando_importe = value

    def set_editando_retencion_origen(self, value: str):
        self.editando_retencion_origen = value

    def set_editando_retencion_destino(self, value: str):
        self.editando_retencion_destino = value

    def set_editando_tipo_derecho_script(self, value: str | list[str]):
        self.editando_tipo_derecho_script = (
            value if isinstance(value, str) else (value[0] if value else "Compra")
        )

    def set_editando_observaciones(self, value: str):
        self.editando_observaciones = value

    @rx.var
    def editando_importe_unitario(self) -> str:
        try:
            num = float(self.editando_num_titulos)
            imp = float(self.editando_importe)
            if num == 0:
                return ""
            return formatear_numero(imp / num)
        except ValueError:
            return ""

    @rx.var
    def editando_importe_neto(self) -> str:
        try:
            imp = float(self.editando_importe or 0)
            ret_o = float(self.editando_retencion_origen or 0)
            ret_d = float(self.editando_retencion_destino or 0)
            return formatear_numero(imp - ret_o - ret_d)
        except ValueError:
            return ""

    def _calcular_validacion_saldo(self) -> tuple[str, bool]:
        """Igual que AltaOperacionState._calcular_validacion_saldo, pero
        sobre los campos 'editando_*' y excluyendo la propia operación de
        su cálculo de saldo (se está editando, no duplicando)."""
        if self.editando_tipo_operacion not in TIPOS_QUE_VALIDAN_SALDO:
            return "", False
        if (
            not self.editando_num_titulos
            or not self.editando_id_valor
            or not self.editando_broker
            or not self.editando_fecha
        ):
            return "", False
        try:
            num = float(self.editando_num_titulos)
            fecha = date.fromisoformat(self.editando_fecha)
        except ValueError:
            return "", False
        id_broker = obtener_broker_id_por_nombre(self.editando_broker)
        if id_broker is None:
            return "", False
        saldo = calcular_saldo(
            self.id_cartera,
            self.editando_id_valor,
            id_broker,
            fecha,
            excluir_id_operacion=self.editando_id,
        )

        if self.editando_tipo_operacion == "Venta":
            if num > saldo:
                return (
                    f"No puedes vender {num:g} títulos: el saldo disponible en este bróker "
                    f"a esta fecha es {saldo:g}.",
                    True,
                )
            return "", False

        if self.editando_tipo_operacion == "Prima":
            if num > saldo:
                return (
                    f"No puedes cobrar una prima por {num:g} títulos: el saldo disponible en "
                    f"este bróker a esta fecha es {saldo:g}.",
                    True,
                )
            if num < saldo:
                return (
                    f"Cobras la prima por menos títulos ({num:g}) de los que tienes en saldo "
                    f"({saldo:g}).",
                    False,
                )
            return "", False

        # Dividendo
        if num == saldo:
            return "", False
        diferencia = abs(num - saldo)
        compensacion = buscar_operacion_compensatoria(
            self.id_cartera,
            self.editando_id_valor,
            id_broker,
            diferencia,
            fecha,
            excluir_id_operacion=self.editando_id,
        )
        if compensacion:
            return (
                f"El nº de títulos ({num:g}) no coincide con el saldo ({saldo:g}), pero la "
                f"diferencia coincide con una {compensacion['tipo_operacion']} de "
                f"{compensacion['num_titulos']:g} títulos el {compensacion['fecha_mostrar']}.",
                False,
            )
        return (
            f"El nº de títulos ({num:g}) no coincide con el saldo ({saldo:g}) y no hay "
            "ninguna Compra/Venta reciente (últimos 30 días) que lo explique. Anula la "
            "operación y revisa el número de títulos.",
            True,
        )

    @rx.var
    def aviso_saldo_edicion(self) -> str:
        mensaje, _ = self._calcular_validacion_saldo()
        return mensaje

    @rx.var
    def bloqueo_saldo_edicion(self) -> bool:
        _, bloqueo = self._calcular_validacion_saldo()
        return bloqueo

    async def guardar_edicion(self):
        self.editar_error = ""
        try:
            num_titulos = float(self.editando_num_titulos)
            importe = float(self.editando_importe)
        except ValueError:
            self.editar_error = "Revisa los importes numéricos."
            return

        id_broker = obtener_broker_id_por_nombre(self.editando_broker)
        if id_broker is None:
            self.editar_error = "Bróker no válido."
            return

        if self.editando_tipo_operacion in TIPOS_QUE_VALIDAN_SALDO:
            mensaje, bloqueo = self._calcular_validacion_saldo()
            if bloqueo:
                self.editar_error = mensaje
                return

        importe_unitario = None
        if self.editando_tipo_operacion != "Script" and num_titulos:
            importe_unitario = importe / num_titulos

        retencion_origen = None
        retencion_destino = None
        tipo_derecho_script = None
        if self.editando_tipo_operacion == "Dividendo":
            retencion_origen = float(self.editando_retencion_origen or 0)
            retencion_destino = float(self.editando_retencion_destino or 0)
        elif self.editando_tipo_operacion == "Script":
            tipo_derecho_script = self.editando_tipo_derecho_script
            if tipo_derecho_script == "Venta":
                retencion_origen = float(self.editando_retencion_origen or 0)
                retencion_destino = float(self.editando_retencion_destino or 0)

        actualizar_operacion(
            self.editando_id,
            fecha=date.fromisoformat(self.editando_fecha),
            id_broker=id_broker,
            num_titulos=num_titulos,
            importe=importe,
            importe_unitario=importe_unitario,
            retencion_origen=retencion_origen,
            retencion_destino=retencion_destino,
            tipo_derecho_script=tipo_derecho_script,
            observaciones=self.editando_observaciones or None,
        )
        await self.cargar_datos()
        self.editar_open = False

    # --- Eliminación (con confirmación) ---
    def set_confirmar_eliminar_open(self, value: bool):
        self.confirmar_eliminar_open = value

    async def eliminar_operacion_actual(self):
        eliminar_operacion(self.editando_id)
        await self.cargar_datos()
        self.confirmar_eliminar_open = False
        self.editar_open = False
