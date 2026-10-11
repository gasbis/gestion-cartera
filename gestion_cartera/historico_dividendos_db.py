"""Informe de histórico de dividendos para la página RADAR: un ranking
de todos los valores en cartera (Largo y Corto Plazo) y en las listas
de posibles compras (las dos), con métricas sintetizadas del
comportamiento del dividendo en los últimos 10 años completos y una
puntuación global para ordenarlos. Complementa a los avisos de
dividendo de Inicio (avisos_dividendo_db.py), que solo miran el último
año.

De dónde salen los datos:
  - Yahoo Finance (services/yahoo_finance.obtener_historico_dividendos):
    dividendo por acción de cada año y cotización media, en la divisa
    origen del valor -- así ni el crecimiento ni la rentabilidad se
    mezclan con el tipo de cambio. Cubre también los valores del radar
    que todavía no se tienen.
  - Los cobros registrados en la app (Dividendo y Script, con la
    valoración del scrip, ver dividendos_scrip.py): Yahoo a veces no
    recoge bien los scrips españoles, así que en los valores que cotizan
    en euros, un año que se tuvo entero y en el que lo cobrado por
    acción supera lo que da Yahoo en más de un `MARGEN_COMPLETAR`, y
    Yahoo tiene ese año menos pagos de los habituales (el síntoma de un
    scrip que falta), se completa con lo cobrado (y se marca en el
    gráfico).

Métricas (años = los 10 últimos años naturales completos):
  - Rentabilidad actual: dividendo de los últimos 12 meses / último
    cierre.
  - Frente a su media: rentabilidad actual menos la media de los 5
    últimos años (dividendo de cada año / cotización media de ese año),
    en puntos. Positivo = paga más de lo habitual (más barata respecto a
    su propia historia).
  - Crecimiento: tasa anual compuesta del dividendo en 5 años.
  - Años sin recorte: años seguidos, hacia atrás desde el último, sin
    bajar más de un UMBRAL_BAJADA (el mismo de los avisos de Inicio).
  - Recortes: nº de años de los 10 con una bajada mayor que ese umbral.
  - Regularidad: años con pago y estabilidad de las variaciones.
  - YoC: rentabilidad de los últimos 12 meses sobre tu precio medio de
    compra (solo valores en cartera).
La puntuación (0-100) y la frase de conclusión se explican en
`_puntuacion` y `_conclusion`, y en la propia página.

Yahoo se consulta como mucho una vez cada `CACHE_HORAS` por valor (caché
en memoria del proceso): el dividendo histórico apenas cambia y son
bastantes peticiones.
"""

import math
import threading
from collections import defaultdict
from datetime import date, datetime, timedelta

import reflex as rx
import sqlmodel

from gestion_cartera.avisos_dividendo_db import UMBRAL_BAJADA
from gestion_cartera.cartera_db import (
    _PRIORIDAD_MISMO_DIA,
    PosicionFIFO,
    _aporta_coste,
    _aporta_titulos,
    aplicar_split_y_fraccion,
    aplicar_spinoff,
    obtener_tenencias,
)
from gestion_cartera.dividendos_scrip import valor_neto_scrip
from gestion_cartera.format_utils import formatear_numero, formatear_pct
from gestion_cartera.models import Operacion, RadarCandidato, Valor
from gestion_cartera.operaciones_db import obtener_cartera_id
from gestion_cartera.services import yahoo_finance

ANIOS = 10
CACHE_HORAS = 12
# Un año propio sustituye al de Yahoo si lo supera en más de esto.
MARGEN_COMPLETAR = 0.05

# Pesos de la puntuación (suman 100).
PESO_RENTABILIDAD = 25
PESO_VALORACION = 15
PESO_CRECIMIENTO = 20
PESO_FIABILIDAD = 25
PESO_REGULARIDAD = 15

# Topes de cada componente: por encima (o por debajo) puntúa el máximo
# (o cero).
RENTABILIDAD_MAX = 6.0  # %
VALORACION_RANGO = 1.5  # puntos por encima/debajo de la media
CRECIMIENTO_MIN, CRECIMIENTO_MAX = -5.0, 10.0  # % anual

UMBRAL_VERDE = 65
UMBRAL_AMBAR = 45

_cache: dict[tuple, tuple[datetime, dict]] = {}
_cache_lock = threading.Lock()


# --------------------------------------------------------------------
# Universo de valores
# --------------------------------------------------------------------


def obtener_universo(id_usuario: int) -> list[dict]:
    """Valores en cartera (Largo y Corto Plazo) y en las dos listas del
    radar, sin repetir: {id_valor, ticker, empresa, mercado, moneda,
    cotizacion_divisa, cotizacion_eur, origenes: [..], titulos,
    valor_compra}. `titulos`/`valor_compra` suman las dos carteras."""
    universo: dict[int, dict] = {}

    def _entrada(id_valor: int) -> dict:
        return universo.setdefault(
            id_valor, {"id_valor": id_valor, "origenes": [], "titulos": 0.0, "valor_compra": 0.0}
        )

    for tipo, etiqueta in (("Largo Plazo", "Cartera LP"), ("Corto Plazo", "Cartera CP")):
        id_cartera = obtener_cartera_id(id_usuario, tipo)
        if id_cartera is None:
            continue
        for t in obtener_tenencias(id_cartera):
            e = _entrada(t["id_valor"])
            e["origenes"].append(etiqueta)
            e["titulos"] += t["num_titulos"]
            e["valor_compra"] += t["valor_compra"]

    with rx.session() as session:
        candidatos = session.exec(
            sqlmodel.select(RadarCandidato).where(RadarCandidato.id_usuario == id_usuario)
        ).all()
        for c in candidatos:
            etiqueta = "Radar LP" if c.tipo_lista == "Largo Plazo" else "Radar CP"
            e = _entrada(c.id_valor)
            if etiqueta not in e["origenes"]:
                e["origenes"].append(etiqueta)

        for id_valor, e in list(universo.items()):
            valor = session.get(Valor, id_valor)
            if valor is None:
                del universo[id_valor]
                continue
            e.update(
                ticker=valor.ticker,
                empresa=valor.empresa,
                mercado=valor.mercado,
                moneda=(valor.moneda or "").upper(),
                cotizacion_divisa=valor.cotizacion_divisa,
                cotizacion_eur=valor.cotizacion_eur,
            )
    return sorted(universo.values(), key=lambda e: e["ticker"])


# --------------------------------------------------------------------
# Dividendo por acción según los cobros registrados
# --------------------------------------------------------------------


def obtener_dpa_propio(id_usuario: int, hoy: date | None = None) -> dict[int, dict]:
    """{id_valor: {"anual": {año: dpa}, "ttm": dpa | None}} con el
    dividendo por acción cobrado (efectivo + scrip valorado), en euros
    y en acciones de ESE momento. Solo los años en que se tuvo el valor
    del 1 de enero al 31 de diciembre (y "ttm" solo si se tiene desde
    hace un año); con las dos carteras, se queda la cifra mayor. Mismo
    cálculo por pago que avisos_dividendo_db.py."""
    hoy = hoy or date.today()
    hace_un_anio = hoy - timedelta(days=365)
    carteras = [
        c
        for c in (
            obtener_cartera_id(id_usuario, "Largo Plazo"),
            obtener_cartera_id(id_usuario, "Corto Plazo"),
        )
        if c is not None
    ]
    if not carteras:
        return {}
    with rx.session() as session:
        operaciones = session.exec(
            sqlmodel.select(Operacion).where(Operacion.id_cartera.in_(carteras))
        ).all()

    grupos: dict[tuple[int, int], list[Operacion]] = defaultdict(list)
    for op in operaciones:
        grupos[(op.id_cartera, op.id_valor)].append(op)

    resultado: dict[int, dict] = {}
    for (_, id_valor), ops in grupos.items():
        ops.sort(key=lambda op: (op.fecha, _PRIORIDAD_MISMO_DIA.get(op.tipo_operacion, 1)))
        posicion = PosicionFIFO()
        titulos_1_enero: dict[int, float] = {}
        siguiente_anio = ops[0].fecha.year + 1
        titulos_hace_un_anio = None
        dpa: dict[int, float] = defaultdict(float)
        ttm = 0.0

        for op in ops:
            while siguiente_anio <= op.fecha.year:
                titulos_1_enero[siguiente_anio] = posicion.titulos
                siguiente_anio += 1
            if titulos_hace_un_anio is None and op.fecha > hace_un_anio:
                titulos_hace_un_anio = posicion.titulos
            titulos_antes = posicion.titulos

            por_accion = 0.0
            if op.tipo_operacion == "Dividendo":
                base = op.num_titulos or titulos_antes
                if base > 0:
                    por_accion = op.importe / base
            elif op.tipo_operacion == "Script" and titulos_antes > 0:
                cobrado = op.importe if op.tipo_derecho_script == "Venta" else 0.0
                por_accion = (cobrado + valor_neto_scrip(op)) / titulos_antes
            if por_accion:
                dpa[op.fecha.year] += por_accion
                if op.fecha > hace_un_anio:
                    ttm += por_accion

            if op.tipo_operacion == "Venta":
                posicion.vender(op.num_titulos)
            elif op.tipo_operacion == "Prima":
                posicion.aplicar_prima(op.importe)
            elif op.tipo_operacion in ("Split", "Contrasplit"):
                aplicar_split_y_fraccion(posicion, op)
            elif op.tipo_operacion == "Spinoff":
                aplicar_spinoff(posicion, op)
            elif _aporta_titulos(op):
                coste_unitario = (
                    (op.importe / op.num_titulos) if _aporta_coste(op) and op.num_titulos else 0.0
                )
                posicion.comprar(op.num_titulos, coste_unitario)

        while siguiente_anio <= hoy.year:
            titulos_1_enero[siguiente_anio] = posicion.titulos
            siguiente_anio += 1
        if titulos_hace_un_anio is None:
            titulos_hace_un_anio = posicion.titulos

        anual = {
            a: v
            for a, v in dpa.items()
            if a < hoy.year
            and titulos_1_enero.get(a, 0) > 1e-9
            and titulos_1_enero.get(a + 1, 0) > 1e-9
        }
        ttm_valido = ttm if titulos_hace_un_anio > 1e-9 and posicion.titulos > 1e-9 else None

        r = resultado.setdefault(id_valor, {"anual": {}, "ttm": None})
        for a, v in anual.items():
            r["anual"][a] = max(r["anual"].get(a, 0.0), v)
        if ttm_valido is not None:
            r["ttm"] = max(r["ttm"] or 0.0, ttm_valido)
    return resultado


# --------------------------------------------------------------------
# Yahoo (con caché)
# --------------------------------------------------------------------


def obtener_datos_yahoo(info: dict, forzar: bool = False, hoy: date | None = None) -> dict:
    """Histórico de Yahoo para un valor del universo, cacheado
    CACHE_HORAS. Lanza la excepción de Yahoo si falla (no se cachea)."""
    hoy = hoy or date.today()
    clave = (info["ticker"], info["mercado"], info["moneda"])
    with _cache_lock:
        guardado = _cache.get(clave)
    if (
        not forzar
        and guardado is not None
        and datetime.now() - guardado[0] < timedelta(hours=CACHE_HORAS)
    ):
        return guardado[1]
    datos = yahoo_finance.obtener_historico_dividendos(
        info["ticker"], info["moneda"], info["mercado"], date(hoy.year - ANIOS - 1, 1, 1)
    )
    with _cache_lock:
        _cache[clave] = (datetime.now(), datos)
    return datos


# --------------------------------------------------------------------
# Cálculo de una fila
# --------------------------------------------------------------------


def _limitar(x: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, x))


def _escala(x: float, minimo: float, maximo: float) -> float:
    """0 en `minimo`, 1 en `maximo`, lineal y acotado."""
    return _limitar((x - minimo) / (maximo - minimo), 0.0, 1.0)


def _puntuacion(m: dict) -> float:
    """Suma de cinco componentes (ver PESO_*):
      - Rentabilidad actual: proporcional hasta RENTABILIDAD_MAX.
      - Frente a su media: de -VALORACION_RANGO (0) a +VALORACION_RANGO
        (máximo); sin media, la mitad.
      - Crecimiento a 5 años: de CRECIMIENTO_MIN a CRECIMIENTO_MAX.
      - Fiabilidad: años sin recorte sobre 10.
      - Regularidad: ver `_regularidad`."""
    rent = PESO_RENTABILIDAD * _escala(m["rent_actual"] or 0.0, 0.0, RENTABILIDAD_MAX)
    if m["vs_media"] is None:
        valoracion = PESO_VALORACION / 2
    else:
        valoracion = PESO_VALORACION * _escala(m["vs_media"], -VALORACION_RANGO, VALORACION_RANGO)
    crec = PESO_CRECIMIENTO * _escala(
        m["cagr"] if m["cagr"] is not None else 0.0, CRECIMIENTO_MIN, CRECIMIENTO_MAX
    )
    fiab = PESO_FIABILIDAD * m["sin_recortes"] / m["anios_evaluados"]
    reg = PESO_REGULARIDAD * m["regularidad"]
    return round(rent + valoracion + crec + fiab + reg, 1)


def _regularidad(serie: list[float]) -> float:
    """0-1: mitad por la proporción de años con pago, mitad por lo
    estables que son las variaciones anuales (desviación típica de las
    variaciones: 0 % puntúa 1, 50 % o más puntúa 0)."""
    if not serie:
        return 0.0
    con_pago = sum(1 for d in serie if d > 0) / len(serie)
    variaciones = [b / a - 1 for a, b in zip(serie, serie[1:]) if a > 0 and b > 0]
    if len(variaciones) >= 2:
        media = sum(variaciones) / len(variaciones)
        desv = math.sqrt(sum((v - media) ** 2 for v in variaciones) / len(variaciones))
    elif variaciones:
        desv = abs(variaciones[0])
    else:
        desv = 0.5
    return round(0.5 * con_pago + 0.5 * max(0.0, 1 - desv / 0.5), 3)


def _conclusion(m: dict) -> str:
    """Frase corta: lo más relevante del histórico y, al final, una
    lectura orientativa (no una recomendación)."""
    partes = []
    if m["recortes"] == 0:
        partes.append(f"Sin recortes en {m['anios_evaluados']} años")
    else:
        partes.append(
            f"{m['recortes']} recorte{'s' if m['recortes'] > 1 else ''} en {m['anios_evaluados']} años"
        )
    if m["subidas_seguidas"] >= 3:
        partes.append(f"{m['subidas_seguidas']} años seguidos subiendo")
    if m["cagr"] is not None:
        signo = "+" if m["cagr"] > 0 else ""
        partes.append(f"dividendo {signo}{formatear_numero(m['cagr'], 1)} %/año ({m['anios_cagr']} años)")
    if m["vs_media"] is not None:
        d = m["vs_media"]
        if abs(d) < 0.05:
            partes.append("rentabilidad igual a su media de 5 años")
        else:
            partes.append(
                f"rentabilidad {formatear_numero(abs(d), 1)} puntos "
                f"{'por encima' if d > 0 else 'por debajo'} de su media de 5 años"
            )
    texto = "; ".join(partes) + "."
    texto = texto[0].upper() + texto[1:]

    if m["recortes"] >= 2 or m["sin_recortes"] < 3:
        lectura = "Dividendo poco fiable: revísalo antes de reforzar."
    elif m["vs_media"] is not None and m["vs_media"] >= 0.75:
        lectura = "Paga más que su media: posible punto de compra."
    elif m["vs_media"] is not None and m["vs_media"] <= -0.75:
        lectura = "Paga menos que su media: cara respecto a su propia historia."
    else:
        lectura = "Rentabilidad en línea con su historia."
    return f"{texto} {lectura}"


def _color(puntuacion: float | None) -> str:
    if puntuacion is None:
        return "gray"
    if puntuacion >= UMBRAL_VERDE:
        return "green"
    if puntuacion >= UMBRAL_AMBAR:
        return "amber"
    return "red"


def _factor_splits_posteriores(splits: list[tuple[date, float]], anio: int) -> float:
    factor = 1.0
    for f, s in splits:
        if f > date(anio, 12, 31):
            factor *= s
    return factor


def calcular_fila(
    info: dict,
    yahoo: dict | None,
    propio: dict | None,
    hoy: date | None = None,
    error_yahoo: str = "",
) -> dict:
    """Una fila del ranking para un valor del universo. `yahoo` es la
    salida de obtener_datos_yahoo (None si falló), `propio` la de
    obtener_dpa_propio para ese valor (None si no hay cobros)."""
    hoy = hoy or date.today()
    yahoo = yahoo or {
        "dividendos": [],
        "splits": [],
        "cierre_medio_anual": {},
        "ultimo_cierre": None,
        "primera_fecha": None,
    }
    propio = propio or {"anual": {}, "ttm": None}
    moneda = info["moneda"]
    en_euros = moneda == "EUR"
    notas = []
    if error_yahoo:
        notas.append(f"Yahoo Finance no respondió ({error_yahoo}).")

    ultimo = hoy.year - 1
    anios_rango = list(range(ultimo - ANIOS, ultimo + 1))  # 11 años: 10 comparaciones

    # Primer año completo con datos de Yahoo (años anteriores a que
    # cotizara no cuentan como "no pagó").
    primera = yahoo["primera_fecha"]
    if primera is not None:
        primer_anio = primera.year if primera <= date(primera.year, 1, 15) else primera.year + 1
    else:
        primer_anio = None

    dpa_yahoo: dict[int, float] = defaultdict(float)
    pagos_yahoo: dict[int, int] = defaultdict(int)
    ttm_yahoo = 0.0
    pagos_ttm = 0
    for f, d in yahoo["dividendos"]:
        dpa_yahoo[f.year] += d
        pagos_yahoo[f.year] += 1
        if f > hoy - timedelta(days=365):
            ttm_yahoo += d
            pagos_ttm += 1

    # Pagos "normales" al año según Yahoo (el nº más repetido): un año
    # con menos pagos es el síntoma de un scrip que Yahoo no recogió.
    conteos = [pagos_yahoo[a] for a in anios_rango if pagos_yahoo.get(a)]
    pagos_habituales = max(set(conteos), key=conteos.count) if conteos else 0

    def _completar(valor_yahoo: float | None, pagos: int, propio_valor: float) -> bool:
        """Solo se sustituye lo de Yahoo por lo cobrado si Yahoo no tiene
        dato, o si le faltan pagos ese año Y lo cobrado es mayor. Así un
        extraordinario o un cobro mal registrado no altera un año que
        Yahoo ya tiene completo."""
        if valor_yahoo is None or valor_yahoo == 0:
            return propio_valor > 0
        return pagos < pagos_habituales and propio_valor > valor_yahoo * (1 + MARGEN_COMPLETAR)

    # Completar con los cobros propios (solo valores en euros: los
    # propios van en euros y los de Yahoo en la divisa del valor).
    serie: dict[int, float] = {}
    completados: set[int] = set()
    for a in anios_rango:
        disponible_yahoo = primer_anio is not None and a >= primer_anio
        valor = dpa_yahoo.get(a, 0.0) if disponible_yahoo else None
        if en_euros and a in propio["anual"]:
            ajustado = propio["anual"][a] / _factor_splits_posteriores(yahoo["splits"], a)
            if _completar(valor, pagos_yahoo.get(a, 0), ajustado):
                valor = ajustado
                completados.add(a)
        if valor is not None:
            serie[a] = valor
    # Quitar huecos del principio (años sin datos de ninguna fuente).
    anios = [a for a in anios_rango if a in serie]
    if anios:
        anios = list(range(anios[0], ultimo + 1))
        for a in anios:
            serie.setdefault(a, 0.0)

    ttm = ttm_yahoo
    ttm_completado = False
    if en_euros and propio["ttm"] is not None and _completar(ttm, pagos_ttm, propio["ttm"]):
        ttm = propio["ttm"]
        ttm_completado = True

    precio = yahoo["ultimo_cierre"] or info.get("cotizacion_divisa")

    base = {
        "id_valor": info["id_valor"],
        "ticker": info["ticker"],
        "empresa": info["empresa"],
        "moneda": moneda,
        "origen_mostrar": " · ".join(info["origenes"]),
        "en_cartera": any(o.startswith("Cartera") for o in info["origenes"]),
        "en_radar": any(o.startswith("Radar") for o in info["origenes"]),
    }

    con_pago = [a for a in anios if serie[a] > 0]
    if len(anios) < 4 or not con_pago:
        motivo = (
            "No ha pagado dividendo en los años con datos."
            if anios and not con_pago
            else "Sin histórico suficiente (hacen falta al menos 4 años)."
        )
        return {
            **base,
            "con_datos": False,
            "puntuacion": None,
            "puntuacion_mostrar": "—",
            "color_puntuacion": "gray",
            "rent_actual": None,
            "rent_actual_mostrar": (
                formatear_pct(ttm / precio * 100) if precio and ttm else "—"
            ),
            "vs_media": None,
            "vs_media_mostrar": "—",
            "color_vs_media": "gray",
            "cagr": None,
            "cagr_mostrar": "—",
            "color_cagr": "gray",
            "sin_recortes": None,
            "sin_recortes_mostrar": "—",
            "recortes": None,
            "recortes_mostrar": "—",
            "regularidad": None,
            "regularidad_mostrar": "—",
            "yoc": None,
            "yoc_mostrar": "—",
            "conclusion": motivo,
            "notas": " ".join(notas),
            "grafico": [],
            "datos_ficha": [],
        }

    # Comparaciones año a año (sobre los años con datos).
    recortes = 0
    for a, b in zip(anios, anios[1:]):
        if serie[a] > 0 and serie[b] < serie[a] * (1 - UMBRAL_BAJADA):
            recortes += 1
    anios_evaluados = len(anios) - 1
    sin_recortes = 0
    for a, b in reversed(list(zip(anios, anios[1:]))):
        if serie[b] > 0 and serie[b] >= serie[a] * (1 - UMBRAL_BAJADA):
            sin_recortes += 1
        else:
            break
    subidas = 0
    for a, b in reversed(list(zip(anios, anios[1:]))):
        if serie[a] > 0 and serie[b] > serie[a] * 1.005:
            subidas += 1
        else:
            break

    # Crecimiento: 5 años si se puede; si no, con lo que haya (mín. 3).
    cagr = None
    anios_cagr = 0
    for n in (5, 4, 3):
        a0 = ultimo - n
        if a0 in serie and serie[a0] > 0 and serie[ultimo] > 0:
            cagr = ((serie[ultimo] / serie[a0]) ** (1 / n) - 1) * 100
            anios_cagr = n
            break

    rent_actual = (ttm / precio * 100) if precio else None
    rentabilidades_5 = [
        serie[a] / yahoo["cierre_medio_anual"][a] * 100
        for a in range(ultimo - 4, ultimo + 1)
        if a in serie and yahoo["cierre_medio_anual"].get(a)
    ]
    media_5 = sum(rentabilidades_5) / len(rentabilidades_5) if len(rentabilidades_5) >= 3 else None
    vs_media = (rent_actual - media_5) if (rent_actual is not None and media_5 is not None) else None

    regularidad = _regularidad([serie[a] for a in anios])
    regularidad_txt = "Alta" if regularidad >= 0.8 else "Media" if regularidad >= 0.55 else "Baja"

    yoc = None
    if info["titulos"] > 0 and info["valor_compra"] > 0 and ttm:
        if en_euros:
            fx = 1.0
        elif info.get("cotizacion_divisa") and info.get("cotizacion_eur"):
            fx = info["cotizacion_eur"] / info["cotizacion_divisa"]
        else:
            fx = None
        if fx is not None:
            yoc = ttm * fx / (info["valor_compra"] / info["titulos"]) * 100

    m = {
        "rent_actual": rent_actual,
        "vs_media": vs_media,
        "cagr": cagr,
        "anios_cagr": anios_cagr,
        "sin_recortes": sin_recortes,
        "recortes": recortes,
        "anios_evaluados": anios_evaluados,
        "subidas_seguidas": subidas,
        "regularidad": regularidad,
    }
    puntuacion = _puntuacion(m)

    if completados or ttm_completado:
        notas.append("Algunos años se han completado con tus cobros (Yahoo no recoge bien algunos scrips).")
    if not en_euros:
        notas.append(f"Cifras en {moneda}: sin efecto del tipo de cambio (salvo el YoC).")
    pagos = [pagos_yahoo[a] for a in anios if pagos_yahoo.get(a) and a not in completados]
    if len(set(pagos)) > 1 and recortes:
        notas.append("El nº de pagos al año cambia: algún recorte puede ser un cambio de calendario.")

    simbolo = {"EUR": "€", "USD": "$", "GBP": "£"}.get(moneda, moneda)
    grafico = [
        {
            "anio": str(a),
            "dpa": round(serie[a], 4),
            "dpa_mostrar": formatear_numero(serie[a], 3),
            "color": "var(--amber-9)" if a in completados else "var(--accent-9)",
        }
        for a in anios
    ]
    grafico.append(
        {
            "anio": "12 m",
            "dpa": round(ttm, 4),
            "dpa_mostrar": formatear_numero(ttm, 3),
            "color": "var(--amber-9)" if ttm_completado else "var(--gray-8)",
        }
    )

    datos_ficha = [
        {"etiqueta": "Dividendo último año", "valor": f"{formatear_numero(serie[ultimo], 3)} {simbolo}"},
        {"etiqueta": "Dividendo últimos 12 meses", "valor": f"{formatear_numero(ttm, 3)} {simbolo}"},
        {
            "etiqueta": "Rentabilidad media 5 años",
            "valor": formatear_pct(media_5) if media_5 is not None else "—",
        },
        {"etiqueta": "Años seguidos subiendo", "valor": str(subidas)},
        {"etiqueta": "Años con pago", "valor": f"{len(con_pago)} de {len(anios)}"},
    ]

    def _signo(x: float, dec: int = 1) -> str:
        return f"{'+' if x > 0 else ''}{formatear_numero(x, dec)}"

    return {
        **base,
        "con_datos": True,
        "puntuacion": puntuacion,
        "puntuacion_mostrar": formatear_numero(puntuacion, 0),
        "color_puntuacion": _color(puntuacion),
        "rent_actual": round(rent_actual, 2) if rent_actual is not None else None,
        "rent_actual_mostrar": formatear_pct(rent_actual) if rent_actual is not None else "—",
        "vs_media": round(vs_media, 2) if vs_media is not None else None,
        "vs_media_mostrar": f"{_signo(vs_media, 2)} p." if vs_media is not None else "—",
        "color_vs_media": (
            "gray" if vs_media is None or abs(vs_media) < 0.25 else "green" if vs_media > 0 else "red"
        ),
        "cagr": round(cagr, 2) if cagr is not None else None,
        "cagr_mostrar": f"{_signo(cagr)} %" if cagr is not None else "—",
        "color_cagr": "gray" if cagr is None or abs(cagr) < 0.5 else "green" if cagr > 0 else "red",
        "sin_recortes": sin_recortes,
        "sin_recortes_mostrar": f"{sin_recortes} / {anios_evaluados}",
        "recortes": recortes,
        "recortes_mostrar": str(recortes),
        "regularidad": regularidad,
        "regularidad_mostrar": regularidad_txt,
        "yoc": round(yoc, 2) if yoc is not None else None,
        "yoc_mostrar": formatear_pct(yoc) if yoc is not None else "—",
        "conclusion": _conclusion(m),
        "notas": " ".join(notas),
        "grafico": grafico,
        "datos_ficha": datos_ficha,
    }
