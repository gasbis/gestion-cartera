"""Consultas y lógica de negocio para la página RADAR (/radar):
seguimiento de posibles compras y su efecto sobre el rebalanceo de la
cartera de Largo Plazo. Ver "Estructura de datos.txt" en la raíz del
proyecto para el encargo original (7 puntos, hecho por fases).

Fase 1 (puntos 1-3): la página en sí, el "objetivo" de balance (peso
deseado por supersector y por zona, editable y persistente) y el peso
ACTUAL de la cartera de Largo Plazo en esas mismas dos dimensiones.

Fase 2 (punto 4, este añadido): lista de posibles compras -- un Valor
en seguimiento (puede no tener ninguna Operacion todavía) con importe a
invertir y precio de compra/venta, con un color de aviso cuando la
cotización se acerca o ya alcanza el precio de compra (ver
`_color_fila_candidato`). El precio de venta (opcional) no tiene color
propio, solo dispara un aviso (ver `_alcanza_precio_venta`).

Fase 5 (punto 5): avisos por SMS cuando se alcanza el precio de compra
o el de venta -- ver states/radar_candidato_state.py
(refrescar_cotizaciones) y services/twilio_sms.py. Los gráficos de
objetivo-vs-real aplicando estas compras (punto 6) y la lista aparte de
Corto Plazo (punto 7) están en otras fases, ver pages/radar.py.
"""

import reflex as rx
import sqlalchemy.exc
import sqlmodel

from gestion_cartera.cartera_db import obtener_tenencias
from gestion_cartera.format_utils import formatear_eur, formatear_numero
from gestion_cartera.models import (
    EjecucionRadarHoraria,
    ObjetivoBalance,
    RadarCandidato,
    Sector,
    Valor,
)
from gestion_cartera.operaciones_db import obtener_cartera_id

# Margen por encima del precio máx de compra dentro del cual la fila se
# marca en ámbar (ver `_color_fila_candidato`).
MARGEN_AMBAR = 0.10


class CandidatoDuplicadoError(ValueError):
    """Se lanza al intentar añadir a la lista un valor que ya está en
    ella (mismo usuario + valor + tipo de lista)."""

# Mismas listas que gestion_cartera/components/alta_operacion_form.py
# (ZONAS/SUPERSECTORES) -- se duplican aquí en vez de importar un
# componente de UI desde la capa de datos; si alguna vez cambian, hay
# que actualizar los dos sitios.
ZONAS = ["ESP", "EURO", "USA", "UK"]
SUPERSECTORES = ["Cíclico", "Defensivo", "Sensible"]

CATEGORIAS_POR_TIPO = {"supersector": SUPERSECTORES, "zona": ZONAS}


def _id_cartera_largo_plazo(id_usuario: int) -> int | None:
    """RADAR trabaja siempre sobre la cartera de Largo Plazo (ver
    encargo original) -- a diferencia de IRPF, aquí NO se combinan las
    dos carteras."""
    return obtener_cartera_id(id_usuario, "Largo Plazo")


def obtener_objetivos(id_usuario: int) -> dict:
    """{"supersector": {categoria: peso}, "zona": {categoria: peso}}.
    Categorías sin fila guardada todavía salen con peso 0 (el usuario
    aún no ha repartido el 100% en esa dimensión)."""
    resultado = {
        tipo: {categoria: 0 for categoria in categorias}
        for tipo, categorias in CATEGORIAS_POR_TIPO.items()
    }
    with rx.session() as session:
        filas = session.exec(
            sqlmodel.select(ObjetivoBalance).where(ObjetivoBalance.id_usuario == id_usuario)
        ).all()
        for fila in filas:
            if fila.tipo in resultado and fila.categoria in resultado[fila.tipo]:
                resultado[fila.tipo][fila.categoria] = fila.peso
    return resultado


def guardar_objetivo(id_usuario: int, tipo: str, pesos: dict) -> None:
    """Guarda (o actualiza) los pesos objetivo de un `tipo` completo
    ("supersector" o "zona") de una vez -- se llama solo cuando la suma
    ya vale 100 (validado en states/radar_state.py)."""
    with rx.session() as session:
        for categoria, peso in pesos.items():
            fila = session.exec(
                sqlmodel.select(ObjetivoBalance).where(
                    ObjetivoBalance.id_usuario == id_usuario,
                    ObjetivoBalance.tipo == tipo,
                    ObjetivoBalance.categoria == categoria,
                )
            ).first()
            if fila is None:
                fila = ObjetivoBalance(
                    id_usuario=id_usuario, tipo=tipo, categoria=categoria, peso=int(peso)
                )
            else:
                fila.peso = int(peso)
            session.add(fila)
        session.commit()


def obtener_pesos_actuales(id_usuario: int) -> dict:
    """Peso actual (%, sobre el valor de mercado total) de la cartera de
    Largo Plazo por supersector y por zona -- reutiliza
    cartera_db.obtener_tenencias, que ya trae `supersector`/`zona` y
    `valor_mercado` calculados por valor."""
    resultado = {
        tipo: {categoria: 0.0 for categoria in categorias}
        for tipo, categorias in CATEGORIAS_POR_TIPO.items()
    }
    id_cartera = _id_cartera_largo_plazo(id_usuario)
    if id_cartera is None:
        return resultado

    tenencias = obtener_tenencias(id_cartera)
    valor_total = sum(f["valor_mercado"] for f in tenencias)
    if not valor_total:
        return resultado

    for f in tenencias:
        if f["supersector"] in resultado["supersector"]:
            resultado["supersector"][f["supersector"]] += f["valor_mercado"]
        if f["zona"] in resultado["zona"]:
            resultado["zona"][f["zona"]] += f["valor_mercado"]

    for categorias in resultado.values():
        for categoria, importe in categorias.items():
            categorias[categoria] = round(importe / valor_total * 100, 1)

    return resultado


def obtener_pesos_con_candidatos(id_usuario: int, tipo_lista: str = "Largo Plazo") -> dict:
    """Igual que `obtener_pesos_actuales`, pero sumando también, a lo que
    ya se posee, el importe a invertir de CADA fila de la lista de
    posibles compras (punto 6 del encargo: "aplicando las compras
    listadas en el radar con el precio de cotización actual" -- el
    importe a invertir ya está fijado en euros, así que no depende de
    la cotización del momento en que se ejecute la compra; lo que sí
    usa la cotización actual es el peso ACTUAL de lo que ya se posee,
    ver obtener_tenencias/valor_mercado).

    Solo se aplican las compras de `tipo_lista` ("Largo Plazo" por
    defecto): las de Corto Plazo no participan en este balance (punto 7
    del encargo, lista independiente)."""
    resultado = {
        tipo: {categoria: 0.0 for categoria in categorias}
        for tipo, categorias in CATEGORIAS_POR_TIPO.items()
    }

    id_cartera = _id_cartera_largo_plazo(id_usuario)
    valor_total = 0.0
    if id_cartera is not None:
        tenencias = obtener_tenencias(id_cartera)
        valor_total = sum(f["valor_mercado"] for f in tenencias)
        for f in tenencias:
            if f["supersector"] in resultado["supersector"]:
                resultado["supersector"][f["supersector"]] += f["valor_mercado"]
            if f["zona"] in resultado["zona"]:
                resultado["zona"][f["zona"]] += f["valor_mercado"]

    with rx.session() as session:
        filas = session.exec(
            sqlmodel.select(RadarCandidato, Valor, Sector)
            .where(
                RadarCandidato.id_usuario == id_usuario,
                RadarCandidato.tipo_lista == tipo_lista,
            )
            .join(Valor, RadarCandidato.id_valor == Valor.id)
            .join(Sector, Valor.id_sector == Sector.id)
        ).all()
        for candidato, valor, sector in filas:
            valor_total += candidato.importe_invertir
            if sector.supersector in resultado["supersector"]:
                resultado["supersector"][sector.supersector] += candidato.importe_invertir
            if valor.zona in resultado["zona"]:
                resultado["zona"][valor.zona] += candidato.importe_invertir

    if not valor_total:
        return resultado

    for categorias in resultado.values():
        for categoria, importe in categorias.items():
            categorias[categoria] = round(importe / valor_total * 100, 1)

    return resultado


# --- Lista de posibles compras (punto 4) --------------------------------


def _color_fila_candidato(cotizacion_divisa: float | None, precio_max: float | None) -> str:
    """Color de aviso de una fila de la lista, comparando la cotización
    actual (en divisa origen) con el precio máx de compra que fijó el
    usuario (también en divisa origen -- la comparación tiene que ser
    en la misma unidad):

    - "red": la cotización ya está en el precio máx o por debajo (el
      punto de entrada deseado ya se alcanzó o se ha mejorado).
    - "amber": la cotización está por encima del precio máx, pero
      dentro de un margen del 10% (se está acercando).
    - "" (sin color): por encima de ese margen, sin cotización todavía
      (valor recién añadido), o sin precio de compra fijado (es
      opcional) -- cadena vacía en vez de None para que el componente
      pueda compararlo como Var sin problemas.
    """
    if cotizacion_divisa is None or not precio_max:
        return ""
    if cotizacion_divisa <= precio_max:
        return "red"
    if cotizacion_divisa <= precio_max * (1 + MARGEN_AMBAR):
        return "amber"
    return ""


def _alcanza_precio_venta(cotizacion_divisa: float | None, precio_min: float | None) -> bool:
    """True si la cotización ya alcanzó o superó el precio de VENTA
    (`RadarCandidato.precio_min`, opcional) -- a diferencia de
    `_color_fila_candidato`, esto NO pinta la fila de ningún color, solo
    se usa para disparar el aviso de venta por SMS (ver
    states/radar_candidato_state.py, refrescar_cotizaciones)."""
    if cotizacion_divisa is None or not precio_min:
        return False
    return cotizacion_divisa >= precio_min


def obtener_candidatos(id_usuario: int, tipo_lista: str = "Largo Plazo") -> list[dict]:
    """Lista de posibles compras de `tipo_lista`, con los datos del
    Valor/Sector ya unidos y el color de aviso ya resuelto (ver
    `_color_fila_candidato`) -- ordenada por ticker."""
    with rx.session() as session:
        filas = session.exec(
            sqlmodel.select(RadarCandidato, Valor, Sector)
            .where(
                RadarCandidato.id_usuario == id_usuario,
                RadarCandidato.tipo_lista == tipo_lista,
            )
            .join(Valor, RadarCandidato.id_valor == Valor.id)
            .join(Sector, Valor.id_sector == Sector.id)
        ).all()

        resultado = []
        for candidato, valor, sector in filas:
            resultado.append(
                {
                    "id": candidato.id,
                    "id_valor": valor.id,
                    "ticker": valor.ticker,
                    "mercado": valor.mercado,
                    "empresa": valor.empresa,
                    "zona": valor.zona,
                    "supersector": sector.supersector,
                    "sector": sector.sector,
                    "grupo": sector.grupo,
                    "moneda": valor.moneda,
                    "importe_invertir_mostrar": formatear_eur(candidato.importe_invertir),
                    # "_str": el número tal cual, sin símbolo de moneda ni
                    # separadores -- para precargar los campos de edición
                    # (ver states/radar_candidato_state.empezar_edicion),
                    # a diferencia de "_mostrar", pensado solo para leer.
                    "importe_invertir_str": str(candidato.importe_invertir),
                    "precio_max_mostrar": (
                        f"{formatear_numero(candidato.precio_max)} {valor.moneda}"
                        if candidato.precio_max is not None
                        else "—"
                    ),
                    "precio_max_str": (
                        str(candidato.precio_max) if candidato.precio_max is not None else ""
                    ),
                    "precio_min_mostrar": (
                        f"{formatear_numero(candidato.precio_min)} {valor.moneda}"
                        if candidato.precio_min is not None
                        else "—"
                    ),
                    "precio_min_str": (
                        str(candidato.precio_min) if candidato.precio_min is not None else ""
                    ),
                    "cotizacion_divisa_mostrar": (
                        f"{formatear_numero(valor.cotizacion_divisa)} {valor.moneda}"
                        if valor.cotizacion_divisa is not None
                        else "—"
                    ),
                    "cotizacion_eur_mostrar": (
                        formatear_eur(valor.cotizacion_eur)
                        if valor.cotizacion_eur is not None
                        else "—"
                    ),
                    "cotizacion_actualizada_en": (
                        valor.cotizacion_actualizada_en.strftime("%d/%m/%Y %H:%M")
                        if valor.cotizacion_actualizada_en
                        else ""
                    ),
                    "color_fila": _color_fila_candidato(valor.cotizacion_divisa, candidato.precio_max),
                    "alerta_enviada": candidato.alerta_enviada,
                    "alcanza_precio_venta": _alcanza_precio_venta(
                        valor.cotizacion_divisa, candidato.precio_min
                    ),
                    "alerta_venta_enviada": candidato.alerta_venta_enviada,
                }
            )
        resultado.sort(key=lambda f: f["ticker"])
        return resultado


def obtener_valores_en_lista(id_usuario: int, tipo_lista: str = "Largo Plazo") -> list[dict]:
    """{id_valor, ticker, mercado, moneda} de los valores de `tipo_lista`
    -- lo mínimo que necesita el refresco de cotizaciones (mismo patrón
    que cartera_db.obtener_valores_en_cartera)."""
    candidatos = obtener_candidatos(id_usuario, tipo_lista)
    vistos: dict[int, dict] = {}
    for c in candidatos:
        vistos[c["id_valor"]] = {
            "id_valor": c["id_valor"],
            "ticker": c["ticker"],
            "mercado": c["mercado"],
            "moneda": c["moneda"],
        }
    return list(vistos.values())


def obtener_valores_en_radar_global() -> list[dict]:
    """Como `obtener_valores_en_lista`, pero sin filtrar por usuario ni
    por tipo_lista: todos los valores distintos que aparecen en
    CUALQUIER lista de posibles compras de CUALQUIER usuario. Lo usa el
    chequeo automático en segundo plano
    (services/radar_scheduler.py) para pedir la cotización de cada
    valor una sola vez por pasada, aunque varios usuarios (o las dos
    listas del mismo usuario) sigan el mismo valor -- `Valor` es una
    tabla compartida entre todos los usuarios de la app, no hay una
    copia por usuario."""
    with rx.session() as session:
        filas = session.exec(
            sqlmodel.select(Valor)
            .join(RadarCandidato, RadarCandidato.id_valor == Valor.id)
            .distinct()
        ).all()
        return [
            {"id_valor": v.id, "ticker": v.ticker, "mercado": v.mercado, "moneda": v.moneda}
            for v in filas
        ]


def obtener_combinaciones_usuario_lista() -> list[tuple[int, str]]:
    """(id_usuario, tipo_lista) distintos que tienen al menos un
    candidato en RADAR -- para que el chequeo automático en segundo
    plano (services/radar_scheduler.py) sepa qué listas recorrer sin
    tener que conocer de antemano los usuarios de la app."""
    with rx.session() as session:
        filas = session.exec(
            sqlmodel.select(RadarCandidato.id_usuario, RadarCandidato.tipo_lista).distinct()
        ).all()
        return [tuple(fila) for fila in filas]


def reclamar_ejecucion_horaria(clave: str) -> bool:
    """Intenta reservar el chequeo automático de RADAR para esta hora
    (`clave` = hora de Madrid programada, p.ej. "2026-09-24T09:20") --
    ver services/radar_scheduler.py y EjecucionRadarHoraria. Devuelve
    True si la hemos reservado nosotros (toca ejecutar de verdad) o
    False si ya la reservó otro proceso (protección por si hubiera más
    de una réplica de la app corriendo a la vez), en cuyo caso hay que
    saltársela para no duplicar los SMS ni las llamadas a Yahoo
    Finance."""
    with rx.session() as session:
        session.add(EjecucionRadarHoraria(clave=clave))
        try:
            session.commit()
        except sqlalchemy.exc.IntegrityError:
            session.rollback()
            return False
        return True


def crear_candidato(
    id_usuario: int,
    id_valor: int,
    importe_invertir: float,
    precio_max: float | None,
    precio_min: float | None,
    tipo_lista: str = "Largo Plazo",
) -> int:
    with rx.session() as session:
        candidato = RadarCandidato(
            id_usuario=id_usuario,
            id_valor=id_valor,
            tipo_lista=tipo_lista,
            importe_invertir=importe_invertir,
            precio_max=precio_max,
            precio_min=precio_min,
        )
        session.add(candidato)
        try:
            session.commit()
        except sqlalchemy.exc.IntegrityError:
            session.rollback()
            raise CandidatoDuplicadoError(
                "Ese valor ya está en esta lista -- edita la fila existente en vez de "
                "añadirlo de nuevo."
            ) from None
        session.refresh(candidato)
        return candidato.id


def actualizar_candidato(
    id_candidato: int, importe_invertir: float, precio_max: float | None, precio_min: float | None
) -> None:
    with rx.session() as session:
        candidato = session.get(RadarCandidato, id_candidato)
        if candidato is None:
            return
        candidato.importe_invertir = importe_invertir
        candidato.precio_max = precio_max
        candidato.precio_min = precio_min
        session.add(candidato)
        session.commit()


def eliminar_candidato(id_candidato: int) -> None:
    with rx.session() as session:
        candidato = session.get(RadarCandidato, id_candidato)
        if candidato is not None:
            session.delete(candidato)
            session.commit()


# --- Avisos por SMS (punto 5) --------------------------------------------


def actualizar_alerta_enviada(id_candidato: int, enviada: bool) -> None:
    """Marca (o desmarca) `alerta_enviada` (aviso de COMPRA) de una fila
    -- ver RadarCandidato.alerta_enviada y
    states/radar_candidato_state.refrescar_cotizaciones, que es quien
    decide cuándo llamar a esto tras cada refresco de cotizaciones."""
    with rx.session() as session:
        candidato = session.get(RadarCandidato, id_candidato)
        if candidato is None or candidato.alerta_enviada == enviada:
            return
        candidato.alerta_enviada = enviada
        session.add(candidato)
        session.commit()


def actualizar_alerta_venta_enviada(id_candidato: int, enviada: bool) -> None:
    """Igual que `actualizar_alerta_enviada` pero para el aviso de VENTA
    -- ver RadarCandidato.alerta_venta_enviada."""
    with rx.session() as session:
        candidato = session.get(RadarCandidato, id_candidato)
        if candidato is None or candidato.alerta_venta_enviada == enviada:
            return
        candidato.alerta_venta_enviada = enviada
        session.add(candidato)
        session.commit()
