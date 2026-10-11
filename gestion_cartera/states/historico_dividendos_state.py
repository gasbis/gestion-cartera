"""Estado del informe de histórico de dividendos de la página RADAR
(ver historico_dividendos_db.py).

El cálculo pide a Yahoo Finance el histórico de cada valor (la primera
vez puede tardar casi un minuto con 40-50 valores; luego tira de la
caché), así que va en un evento en segundo plano: el resto de la página
se puede usar mientras tanto, y se va mostrando el progreso.
"""

import asyncio

import reflex as rx

from gestion_cartera.historico_dividendos_db import (
    calcular_fila,
    obtener_datos_yahoo,
    obtener_dpa_propio,
    obtener_universo,
)
from gestion_cartera.states.auth_state import AuthState

# Peticiones a Yahoo a la vez, y pausa entre una y la siguiente de cada
# hilo -- mismo margen de prudencia que en el resto de la app (Yahoo no
# publica un límite).
PETICIONES_SIMULTANEAS = 3
PAUSA_ENTRE_PETICIONES = 0.5  # segundos

# Columnas por las que se puede ordenar: clave del dict -> orden por
# defecto descendente (True) o ascendente (False) al pulsar la primera vez.
COLUMNAS_ORDEN = {
    "ticker": False,
    "puntuacion": True,
    "rent_actual": True,
    "vs_media": True,
    "cagr": True,
    "sin_recortes": True,
    "recortes": False,
    "regularidad": True,
    "yoc": True,
}


class HistoricoDividendosState(rx.State):
    filas: list[dict] = []
    cargando: bool = False
    progreso: str = ""
    error: str = ""
    forzar_recalculo: bool = False

    filtro: str = "todos"  # "todos" | "cartera" | "radar"
    orden: str = "puntuacion"
    orden_desc: bool = True

    # Ficha abierta (id_valor; -1 = ninguna) y sus datos, copiados a
    # variables con tipo para poder usarlos en el gráfico y en rx.foreach.
    expandido: int = -1
    detalle: dict[str, str] = {}
    detalle_grafico: list[dict] = []
    detalle_datos: list[dict[str, str]] = []

    def cargar_datos(self):
        self.forzar_recalculo = False
        return HistoricoDividendosState.calcular

    def recalcular(self):
        self.forzar_recalculo = True
        return HistoricoDividendosState.calcular

    @rx.event(background=True)
    async def calcular(self):
        async with self:
            if self.cargando:
                return
            auth_state = await self.get_state(AuthState)
            if not auth_state.is_authenticated:
                return
            id_usuario = auth_state.current_user["id"]
            forzar = self.forzar_recalculo
            self.cargando = True
            self.error = ""
            self.progreso = "Preparando…"

        try:
            universo = await asyncio.to_thread(obtener_universo, id_usuario)
            propios = await asyncio.to_thread(obtener_dpa_propio, id_usuario)
        except Exception as e:
            async with self:
                self.cargando = False
                self.progreso = ""
                self.error = f"No se pudo preparar el informe: {e}"
            return

        total = len(universo)
        hechos = 0
        filas: list[dict] = []
        errores: list[str] = []
        semaforo = asyncio.Semaphore(PETICIONES_SIMULTANEAS)

        async def _procesar(info: dict):
            nonlocal hechos
            async with semaforo:
                error = ""
                try:
                    yahoo = await asyncio.to_thread(obtener_datos_yahoo, info, forzar)
                except Exception as e:
                    yahoo = None
                    error = str(e)[:120]
                    errores.append(info["ticker"])
                fila = calcular_fila(
                    info, yahoo, propios.get(info["id_valor"]), error_yahoo=error
                )
                filas.append(fila)
                hechos += 1
                async with self:
                    self.progreso = f"Calculando histórico de dividendos… {hechos} de {total}"
                await asyncio.sleep(PAUSA_ENTRE_PETICIONES)

        await asyncio.gather(*[_procesar(info) for info in universo])

        async with self:
            self.filas = filas
            self.cargando = False
            self.progreso = ""
            if errores:
                self.error = (
                    "Yahoo Finance no devolvió datos de: " + ", ".join(sorted(errores)) + "."
                )
            if self.expandido != -1:
                self._copiar_detalle(self.expandido)

    def set_filtro(self, valor: str | list[str]):
        self.filtro = valor if isinstance(valor, str) else (valor[0] if valor else "todos")

    def ordenar_por(self, columna: str):
        if columna not in COLUMNAS_ORDEN:
            return
        if self.orden == columna:
            self.orden_desc = not self.orden_desc
        else:
            self.orden = columna
            self.orden_desc = COLUMNAS_ORDEN[columna]

    def abrir_ficha(self, id_valor: int):
        self.expandido = id_valor
        self._copiar_detalle(id_valor)

    def cambiar_ficha_abierta(self, abierta: bool):
        if not abierta:
            self.expandido = -1

    def _copiar_detalle(self, id_valor: int):
        fila = next((f for f in self.filas if f["id_valor"] == id_valor), None)
        if fila is None:
            self.expandido = -1
            self.detalle, self.detalle_grafico, self.detalle_datos = {}, [], []
            return
        self.detalle = {
            k: str(fila[k])
            for k in (
                "ticker",
                "empresa",
                "origen_mostrar",
                "puntuacion_mostrar",
                "color_puntuacion",
                "conclusion",
                "notas",
            )
        }
        self.detalle_grafico = fila["grafico"]
        self.detalle_datos = fila["datos_ficha"]

    @rx.var
    def filas_visibles(self) -> list[dict]:
        filas = self.filas
        if self.filtro == "cartera":
            filas = [f for f in filas if f["en_cartera"]]
        elif self.filtro == "radar":
            filas = [f for f in filas if f["en_radar"]]

        clave = self.orden
        if clave == "ticker":
            return sorted(filas, key=lambda f: f["ticker"], reverse=self.orden_desc)
        # Los valores sin dato van siempre al final, sea cual sea el sentido.
        con_dato = [f for f in filas if f.get(clave) is not None]
        sin_dato = sorted((f for f in filas if f.get(clave) is None), key=lambda f: f["ticker"])
        con_dato.sort(key=lambda f: f[clave], reverse=self.orden_desc)
        return con_dato + sin_dato

    @rx.var
    def num_en_cartera(self) -> int:
        return sum(1 for f in self.filas if f["en_cartera"])

    @rx.var
    def num_en_radar(self) -> int:
        return sum(1 for f in self.filas if f["en_radar"])
