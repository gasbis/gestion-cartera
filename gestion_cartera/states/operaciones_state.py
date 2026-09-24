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
    validar_saldo_nunca_negativo,
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
    # Bróker con el que se abrió la edición, para detectar si se cambia
    # (ver _validar_timeline_edicion).
    editando_broker_original: str = ""
    editando_ticker: str = ""
    editando_empresa: str = ""
    editando_num_titulos: str = ""
    editando_importe: str = ""
    editando_retencion_origen: str = ""
    editando_retencion_destino: str = ""
    editando_tipo_derecho_script: str = "Compra"
    # Solo para Split/Contrasplit -- edición "en crudo" de los campos ya
    # resueltos que se guardaron al dar de alta (no se repite aquí el
    # asistente basado en resolver_split de AltaOperacionState: el ratio
    # y el nº de títulos resultante ya están calculados, y si hace falta
    # corregirlos se editan directamente, igual que con cualquier otro
    # tipo). "" en editando_tipo_ajuste_fraccion == sin ajuste (None en
    # BD); "Venta" == fracción cobrada en efectivo; "Compra" == fracción
    # completada a título entero.
    editando_ratio: str = ""
    editando_tipo_ajuste_fraccion: str = ""
    editando_observaciones: str = ""
    editar_error: str = ""
    eliminar_error: str = ""

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
        self.eliminar_error = ""
        self.editando_id = item["id"]
        self.editando_id_valor = item["id_valor"]
        self.editando_tipo_operacion = item["tipo_operacion"]
        self.editando_fecha = item["fecha"]
        self.editando_broker = item["broker"]
        self.editando_broker_original = item["broker"]
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
        self.editando_ratio = str(item["ratio"]) if item.get("ratio") is not None else ""
        self.editando_tipo_ajuste_fraccion = item.get("tipo_ajuste_fraccion") or ""
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

    def set_editando_ratio(self, value: str):
        self.editando_ratio = value

    def set_editando_tipo_ajuste_fraccion(self, value: str | list[str]):
        self.editando_tipo_ajuste_fraccion = (
            value if isinstance(value, str) else (value[0] if value else "")
        )

    def set_editando_observaciones(self, value: str):
        self.editando_observaciones = value

    @rx.var
    def editando_importe_unitario(self) -> str:
        if self.editando_tipo_operacion in ("Script", "Split", "Contrasplit"):
            return ""
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
        """Combina dos comprobaciones sobre la edición en curso:

        1. `_validar_punto_saldo`: para Venta/Dividendo/Prima, el número
           de títulos contra el saldo EN LA FECHA de esta operación
           (mensajes concretos, con sugerencia de compensación para
           Dividendo).
        2. `_validar_timeline_edicion`: para Compra/Venta/Script, que el
           cambio (fecha, bróker o nº de títulos) no deje el saldo en
           negativo en NINGÚN punto posterior de la línea temporal --
           p. ej. reducir o borrar una Compra de la que una Venta
           posterior ya disponía, algo que (1) no puede detectar porque
           solo mira la fecha de la propia operación.

        Se devuelve el primer mensaje no vacío que aparezca (si ambas
        aplican, se prioriza la que primero encuentre un problema)."""
        if self.editando_tipo_operacion in TIPOS_QUE_VALIDAN_SALDO:
            mensaje, bloqueo = self._validar_punto_saldo()
            if mensaje:
                return mensaje, bloqueo

        if self.editando_tipo_operacion in ("Compra", "Venta", "Script", "Split", "Contrasplit"):
            mensaje, bloqueo = self._validar_timeline_edicion()
            if mensaje:
                return mensaje, bloqueo

        return "", False

    def _validar_punto_saldo(self) -> tuple[str, bool]:
        """Igual que AltaOperacionState._calcular_validacion_saldo, pero
        sobre los campos 'editando_*' y excluyendo la propia operación de
        su cálculo de saldo (se está editando, no duplicando)."""
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

    def _validar_timeline_edicion(self) -> tuple[str, bool]:
        """Para Compra/Venta/Script: recalcula toda la línea temporal de
        saldo del valor+bróker afectado con el cambio ya aplicado, para
        detectar que no deja el saldo en negativo en ningún punto
        posterior (no solo en la fecha de esta operación)."""
        if not self.editando_num_titulos or not self.editando_broker or not self.editando_fecha:
            return "", False
        try:
            num = float(self.editando_num_titulos)
            fecha = date.fromisoformat(self.editando_fecha)
        except ValueError:
            return "", False
        id_broker_nuevo = obtener_broker_id_por_nombre(self.editando_broker)
        if id_broker_nuevo is None:
            return "", False

        broker_cambiado = self.editando_broker != self.editando_broker_original
        simulada = {
            "fecha": fecha,
            "tipo_operacion": self.editando_tipo_operacion,
            "num_titulos": num,
        }

        # Bróker de destino (donde queda la operación tras guardar): si el
        # resultado deja el saldo en negativo en algún punto, se bloquea.
        error_destino = validar_saldo_nunca_negativo(
            self.id_cartera,
            self.editando_id_valor,
            id_broker_nuevo,
            excluir_id_operacion=self.editando_id if not broker_cambiado else None,
            operacion_simulada=simulada,
        )
        if error_destino:
            return error_destino, True

        # Bróker de origen (si se ha movido la operación a otro bróker):
        # solo se avisa, no se bloquea -- mover una operación de bróker
        # es una corrección legítima aunque deje aparentemente huérfana
        # una operación posterior en el bróker de origen.
        if broker_cambiado:
            id_broker_original = obtener_broker_id_por_nombre(self.editando_broker_original)
            if id_broker_original is not None:
                error_origen = validar_saldo_nunca_negativo(
                    self.id_cartera,
                    self.editando_id_valor,
                    id_broker_original,
                    excluir_id_operacion=self.editando_id,
                )
                if error_origen:
                    return (
                        f"Al mover esta operación, el bróker de origen "
                        f"({self.editando_broker_original}) queda con el saldo incoherente: "
                        f"{error_origen}",
                        False,
                    )

        return "", False

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

        mensaje, bloqueo = self._calcular_validacion_saldo()
        if bloqueo:
            self.editar_error = mensaje
            return

        es_split = self.editando_tipo_operacion in ("Split", "Contrasplit")

        importe_unitario = None
        if self.editando_tipo_operacion not in ("Script", "Split", "Contrasplit") and num_titulos:
            importe_unitario = importe / num_titulos

        retencion_origen = None
        retencion_destino = None
        tipo_derecho_script = None
        ratio = None
        tipo_ajuste_fraccion = None
        if self.editando_tipo_operacion == "Dividendo":
            retencion_origen = float(self.editando_retencion_origen or 0)
            retencion_destino = float(self.editando_retencion_destino or 0)
        elif self.editando_tipo_operacion == "Script":
            tipo_derecho_script = self.editando_tipo_derecho_script
            if tipo_derecho_script == "Venta":
                retencion_origen = float(self.editando_retencion_origen or 0)
                retencion_destino = float(self.editando_retencion_destino or 0)
        elif es_split:
            if not self.editando_ratio:
                self.editar_error = "Indica el ratio (nuevo/antiguo)."
                return
            try:
                ratio = float(self.editando_ratio)
            except ValueError:
                self.editar_error = "Revisa el ratio."
                return
            tipo_ajuste_fraccion = self.editando_tipo_ajuste_fraccion or None
            if tipo_ajuste_fraccion == "Venta":
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
            ratio=ratio,
            tipo_ajuste_fraccion=tipo_ajuste_fraccion,
        )
        await self.cargar_datos()
        self.editar_open = False

    # --- Eliminación (con confirmación) ---
    def abrir_confirmar_eliminar(self):
        self.eliminar_error = ""
        self.confirmar_eliminar_open = True

    def set_confirmar_eliminar_open(self, value: bool):
        self.confirmar_eliminar_open = value

    async def eliminar_operacion_actual(self):
        self.eliminar_error = ""
        if self.editando_tipo_operacion in ("Compra", "Script", "Split"):
            # Venta/Contrasplit nunca hace falta bloquearlos al borrar:
            # borrarlos solo LIBERA saldo hacia adelante, nunca lo
            # reduce. Split, al igual que Compra/Script, sí puede dejar
            # sin saldo suficiente a una operación posterior.
            id_broker = obtener_broker_id_por_nombre(self.editando_broker)
            if id_broker is not None:
                error = validar_saldo_nunca_negativo(
                    self.id_cartera,
                    self.editando_id_valor,
                    id_broker,
                    excluir_id_operacion=self.editando_id,
                )
                if error:
                    self.eliminar_error = (
                        f"No se puede eliminar: {error} Edita o elimina antes esa operación "
                        "posterior."
                    )
                    return

        eliminar_operacion(self.editando_id)
        await self.cargar_datos()
        self.confirmar_eliminar_open = False
        self.editar_open = False
