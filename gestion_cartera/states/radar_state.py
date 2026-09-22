"""Estado de la página RADAR (fase 1: objetivo de balance + peso actual
de la cartera de Largo Plazo por supersector y por zona -- ver
radar_db.py).

Los pesos objetivo se guardan en el state como texto sin parsear
(igual que `editando_num_titulos` en states/operaciones_state.py, para
no pelear con el campo mientras el usuario todavía está escribiendo);
solo se convierten a entero acotado [0, 100] al calcular la suma, los
datos del gráfico o al guardar (ver `_peso_valido`).
"""

import reflex as rx

from gestion_cartera.format_utils import formatear_pct
from gestion_cartera.radar_db import (
    guardar_objetivo,
    obtener_objetivos,
    obtener_pesos_actuales,
    obtener_pesos_con_candidatos,
)
from gestion_cartera.states.auth_state import AuthState


class RadarState(rx.State):
    objetivo_supersector: dict[str, str] = {}
    objetivo_zona: dict[str, str] = {}
    actual_supersector: dict[str, float] = {}
    actual_zona: dict[str, float] = {}
    # Peso proyectado si se ejecutaran TODAS las compras de la lista de
    # vigilancia (punto 6 del encargo) -- ver
    # radar_db.obtener_pesos_con_candidatos.
    proyectado_supersector: dict[str, float] = {}
    proyectado_zona: dict[str, float] = {}

    # A False en cuanto el usuario toca algo de esa dimensión, para que
    # el aviso de "guardado" no quede mintiendo tras un cambio sin
    # guardar todavía.
    guardado_supersector: bool = False
    guardado_zona: bool = False

    async def cargar_datos(self):
        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            return
        id_usuario = auth_state.current_user["id"]

        objetivos = obtener_objetivos(id_usuario)
        self.objetivo_supersector = {c: str(p) for c, p in objetivos["supersector"].items()}
        self.objetivo_zona = {c: str(p) for c, p in objetivos["zona"].items()}

        actuales = obtener_pesos_actuales(id_usuario)
        self.actual_supersector = actuales["supersector"]
        self.actual_zona = actuales["zona"]

        proyectados = obtener_pesos_con_candidatos(id_usuario)
        self.proyectado_supersector = proyectados["supersector"]
        self.proyectado_zona = proyectados["zona"]

        self.guardado_supersector = False
        self.guardado_zona = False

    async def recargar_proyeccion(self):
        """Solo recalcula el peso proyectado (obtener_pesos_con_candidatos)
        -- lo llama states/radar_candidato_state.py cada vez que se
        añade, edita o borra una fila de la lista de posibles compras,
        para que el gráfico de objetivo-vs-real-aplicando-compras se
        actualice sin tener que recargar toda la página."""
        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            return
        proyectados = obtener_pesos_con_candidatos(auth_state.current_user["id"])
        self.proyectado_supersector = proyectados["supersector"]
        self.proyectado_zona = proyectados["zona"]

    def set_objetivo_supersector(self, categoria: str, valor: str):
        nuevo = dict(self.objetivo_supersector)
        nuevo[categoria] = valor
        self.objetivo_supersector = nuevo
        self.guardado_supersector = False

    def set_objetivo_zona(self, categoria: str, valor: str):
        nuevo = dict(self.objetivo_zona)
        nuevo[categoria] = valor
        self.objetivo_zona = nuevo
        self.guardado_zona = False

    def _peso_valido(self, texto: str) -> int:
        """Entero acotado [0, 100]; un texto vacío o no numérico
        (mientras el usuario todavía está escribiendo) cuenta como 0."""
        try:
            return max(0, min(100, int(texto.strip())))
        except (ValueError, AttributeError):
            return 0

    async def guardar_supersector(self):
        if self.suma_objetivo_supersector != 100:
            return
        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            return
        pesos = {c: self._peso_valido(v) for c, v in self.objetivo_supersector.items()}
        guardar_objetivo(auth_state.current_user["id"], "supersector", pesos)
        self.guardado_supersector = True

    async def guardar_zona(self):
        if self.suma_objetivo_zona != 100:
            return
        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            return
        pesos = {c: self._peso_valido(v) for c, v in self.objetivo_zona.items()}
        guardar_objetivo(auth_state.current_user["id"], "zona", pesos)
        self.guardado_zona = True

    @rx.var
    def suma_objetivo_supersector(self) -> int:
        return sum(self._peso_valido(v) for v in self.objetivo_supersector.values())

    @rx.var
    def suma_objetivo_zona(self) -> int:
        return sum(self._peso_valido(v) for v in self.objetivo_zona.values())

    @rx.var
    def datos_grafico_supersector(self) -> list[dict]:
        return self._datos_grafico(self.objetivo_supersector, self.actual_supersector, "actual")

    @rx.var
    def datos_grafico_zona(self) -> list[dict]:
        return self._datos_grafico(self.objetivo_zona, self.actual_zona, "actual")

    @rx.var
    def datos_grafico_proyeccion_supersector(self) -> list[dict]:
        return self._datos_grafico_proyeccion(
            self.objetivo_supersector, self.actual_supersector, self.proyectado_supersector
        )

    @rx.var
    def datos_grafico_proyeccion_zona(self) -> list[dict]:
        return self._datos_grafico_proyeccion(
            self.objetivo_zona, self.actual_zona, self.proyectado_zona
        )

    def _datos_grafico(self, objetivo: dict, comparado: dict, campo: str) -> list[dict]:
        """`campo` es el prefijo de las claves del segundo valor de cada
        fila (de momento solo "actual", ver datos_grafico_supersector/zona
        -- el gráfico de proyección usa `_datos_grafico_proyeccion` en su
        lugar, porque necesita el desglose actual+cambio, no solo un
        segundo valor)."""
        filas = []
        for categoria, texto in objetivo.items():
            peso = self._peso_valido(texto)
            valor_comparado = comparado.get(categoria, 0.0)
            filas.append(
                {
                    "name": categoria,
                    "objetivo_pct": peso,
                    "objetivo_pct_mostrar": f"{peso} %",
                    f"{campo}_pct": valor_comparado,
                    f"{campo}_pct_mostrar": formatear_pct(valor_comparado, decimales=1),
                }
            )
        return filas

    def _datos_grafico_proyeccion(self, objetivo: dict, actual: dict, proyectado: dict) -> list[dict]:
        """Datos para la barra "Actual + cambio proyectado" (ver
        pages/radar.py, _grafico_proyeccion): una barra apilada con el
        peso ACTUAL como base (color neutro, longitud real) y encima un
        segundo tramo con el CAMBIO que introducirían las compras
        listadas (puede ser negativo: al crecer el total invertido,
        una categoría sin compras nuevas pierde peso relativo aunque no
        se haya tocado). Ese tramo se pinta en verde si acerca el peso
        al objetivo (o lo deja igual) y en rojo si lo aleja."""
        filas = []
        for categoria, texto in objetivo.items():
            peso_objetivo = self._peso_valido(texto)
            peso_actual = actual.get(categoria, 0.0)
            peso_proyectado = proyectado.get(categoria, 0.0)
            cambio = round(peso_proyectado - peso_actual, 1)

            desviacion_actual = abs(peso_actual - peso_objetivo)
            desviacion_proyectada = abs(peso_proyectado - peso_objetivo)
            acerca_al_objetivo = desviacion_proyectada <= desviacion_actual

            cambio_mostrar = formatear_pct(cambio, decimales=1)
            if cambio > 0:
                cambio_mostrar = f"+{cambio_mostrar}"
            actual_mostrar = formatear_pct(peso_actual, decimales=1)

            filas.append(
                {
                    "name": categoria,
                    "objetivo_pct": peso_objetivo,
                    "objetivo_pct_mostrar": f"{peso_objetivo} %",
                    "actual_pct": peso_actual,
                    "actual_pct_mostrar": actual_mostrar,
                    "cambio_pct": cambio,
                    "cambio_pct_mostrar": cambio_mostrar,
                    # Un único texto con el actual y el cambio juntos, para
                    # pintar una sola etiqueta por fila en vez de dos (ver
                    # pages/radar.py, _grafico_proyeccion) -- con dos
                    # etiquetas independientes se solapaban en las barras
                    # cortas, sobre todo cuando el tramo de cambio es
                    # pequeño o negativo.
                    "resumen_cambio_mostrar": f"{actual_mostrar}  {cambio_mostrar}",
                    "color_cambio": "var(--green-9)" if acerca_al_objetivo else "var(--red-9)",
                }
            )
        return filas
