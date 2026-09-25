"""Estado de la página CARTERA: tenencias calculadas a partir del
histórico de operaciones (agregando todos los brokers, ver
cartera_db.py), con refresco automático de cotizaciones al cargar la
página (Yahoo Finance, ver services/yahoo_finance.py) y buscador.
"""

import asyncio

import reflex as rx

from gestion_cartera.cartera_db import (
    calcular_tir,
    guardar_cotizacion,
    obtener_tenencias,
    obtener_valores_en_cartera,
    obtener_valores_liquidados,
)
from gestion_cartera.format_utils import formatear_eur, formatear_pct
from gestion_cartera.operaciones_db import obtener_cartera_id
from gestion_cartera.services import yahoo_finance
from gestion_cartera.states.auth_state import AuthState

CAMPOS_ORDENABLES = (
    "ticker",
    "empresa",
    "zona",
    "supersector",
    "num_titulos",
    "precio_medio",
    "cotizacion_actual",
    "valor_mercado",
    "plusvalia_eur",
    "plusvalia_pct",
    "yoc_anterior",
    "peso_cartera_pct",
)

# Yahoo Finance (a diferencia del plan gratuito de Twelve Data) no publica
# un límite de peticiones/minuto, pero al no ser una API oficial conviene
# no encadenar peticiones sin ninguna pausa. Es un margen de prudencia,
# no un límite documentado.
PAUSA_ENTRE_COTIZACIONES = 1  # segundos


class CarteraState(rx.State):
    tenencias_raw: list[dict] = []
    valores_liquidados: list[dict] = []
    busqueda: str = ""
    orden_campo: str = "valor_mercado"
    orden_desc: bool = True

    actualizando_cotizaciones: bool = False
    cotizaciones_error: str = ""

    tir_con_revalorizacion: float | None = None
    tir_sin_revalorizacion: float | None = None

    # True hasta que las tenencias iniciales terminan de cargar (no
    # confundir con `actualizando_cotizaciones`, que es el refresco de
    # precios en segundo plano): mientras es True, la página muestra un
    # skeleton en vez de la tabla vacía/valores en 0 por defecto.
    cargando_inicial: bool = True

    async def cargar_datos(self):
        """on_load de /cartera: carga las tenencias y lanza el refresco de
        cotizaciones en segundo plano (la tabla se ve al instante con las
        últimas cotizaciones guardadas, y se va actualizando sola)."""
        self.cargando_inicial = True
        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            self.cargando_inicial = False
            return

        from gestion_cartera.states.portfolio_state import PortfolioState

        portfolio_state = await self.get_state(PortfolioState)
        id_cartera = obtener_cartera_id(
            auth_state.current_user["id"], portfolio_state.selected_portfolio
        )
        if id_cartera is None:
            self.tenencias_raw = []
            self.valores_liquidados = []
            self.tir_con_revalorizacion = None
            self.tir_sin_revalorizacion = None
            self.cargando_inicial = False
            return
        self.tenencias_raw = obtener_tenencias(id_cartera)
        self.valores_liquidados = obtener_valores_liquidados(id_cartera)
        tir = calcular_tir(id_cartera)
        self.tir_con_revalorizacion = tir["con_revalorizacion"]
        self.tir_sin_revalorizacion = tir["sin_revalorizacion"]
        self.cargando_inicial = False

        return CarteraState.actualizar_cotizaciones

    @rx.event(background=True)
    async def actualizar_cotizaciones(self):
        from gestion_cartera.states.portfolio_state import PortfolioState

        async with self:
            if self.actualizando_cotizaciones:
                return
            self.actualizando_cotizaciones = True
            self.cotizaciones_error = ""
            auth_state = await self.get_state(AuthState)
            portfolio_state = await self.get_state(PortfolioState)
            id_usuario = (
                auth_state.current_user["id"] if auth_state.current_user else None
            )
            cartera_seleccionada = portfolio_state.selected_portfolio

        id_cartera = obtener_cartera_id(id_usuario, cartera_seleccionada) if id_usuario else None
        valores = obtener_valores_en_cartera(id_cartera) if id_cartera else []

        errores = []
        for i, v in enumerate(valores):
            try:
                cot = yahoo_finance.obtener_cotizacion(v["ticker"], v["moneda"], v["mercado"])
                guardar_cotizacion(
                    v["id_valor"], cot["cotizacion_divisa"], cot["cotizacion_eur"], cot["actualizada_en"]
                )
            except Exception as e:
                errores.append(f"{v['mercado']}:{v['ticker']}: {e}")
            if i < len(valores) - 1:
                await asyncio.sleep(PAUSA_ENTRE_COTIZACIONES)

        tir = calcular_tir(id_cartera) if id_cartera else {"con_revalorizacion": None, "sin_revalorizacion": None}

        async with self:
            self.tenencias_raw = obtener_tenencias(id_cartera) if id_cartera else []
            self.tir_con_revalorizacion = tir["con_revalorizacion"]
            self.tir_sin_revalorizacion = tir["sin_revalorizacion"]
            self.actualizando_cotizaciones = False
            if errores:
                self.cotizaciones_error = (
                    f"No se pudo actualizar la cotización de {len(errores)} valor(es): "
                    + "; ".join(errores[:5])
                    + ("…" if len(errores) > 5 else "")
                )

    def set_busqueda(self, value: str):
        self.busqueda = value

    def set_orden(self, campo: str):
        if campo == self.orden_campo:
            self.orden_desc = not self.orden_desc
        else:
            self.orden_campo = campo
            self.orden_desc = False

    @rx.var
    def tenencias_filtradas(self) -> list[dict]:
        texto = self.busqueda.strip().lower()
        filas = self.tenencias_raw
        if texto:
            filas = [
                f
                for f in filas
                if texto in f["ticker"].lower()
                or texto in f["empresa"].lower()
                or texto in f["sector"].lower()
                or texto in f["zona"].lower()
            ]
        clave = lambda f: f.get(self.orden_campo, 0)
        return sorted(filas, key=clave, reverse=self.orden_desc)

    @rx.var
    def valor_total_mercado(self) -> float:
        return round(sum(f["valor_mercado"] for f in self.tenencias_raw), 2)

    @rx.var
    def valor_total_mercado_mostrar(self) -> str:
        return formatear_eur(self.valor_total_mercado)

    @rx.var
    def valor_total_compra(self) -> float:
        return round(sum(f["valor_compra"] for f in self.tenencias_raw), 2)

    @rx.var
    def valor_total_compra_mostrar(self) -> str:
        return formatear_eur(self.valor_total_compra)

    @rx.var
    def plusvalia_total_eur(self) -> float:
        return round(self.valor_total_mercado - self.valor_total_compra, 2)

    @rx.var
    def plusvalia_total_pct(self) -> float:
        if not self.valor_total_compra:
            return 0.0
        return round(self.plusvalia_total_eur / self.valor_total_compra * 100, 2)

    @rx.var
    def plusvalia_total_eur_mostrar(self) -> str:
        return formatear_eur(self.plusvalia_total_eur)

    @rx.var
    def plusvalia_total_pct_mostrar(self) -> str:
        return formatear_pct(self.plusvalia_total_pct)

    @rx.var
    def numero_valores(self) -> int:
        return len(self.tenencias_raw)

    @rx.var
    def tir_con_revalorizacion_mostrar(self) -> str:
        if self.tir_con_revalorizacion is None:
            return "—"
        return formatear_pct(self.tir_con_revalorizacion)

    @rx.var
    def tir_sin_revalorizacion_mostrar(self) -> str:
        if self.tir_sin_revalorizacion is None:
            return "—"
        return formatear_pct(self.tir_sin_revalorizacion)
