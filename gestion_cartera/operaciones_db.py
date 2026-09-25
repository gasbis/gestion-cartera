"""Consultas de base de datos para el formulario de alta de operación:
listar brokers/valores/sectores, resolver ids, crear un Valor nuevo y
guardar la Operacion final.
"""

import math
from datetime import date, timedelta

import reflex as rx
import sqlalchemy.exc
import sqlmodel

from gestion_cartera.format_utils import formatear_titulos
from gestion_cartera.models import Broker, Cartera, Operacion, Sector, Valor

# Misma tolerancia que cartera_db.EPSILON_TITULOS, para decidir si el
# resultado teórico de un Split/Contrasplit ya es un número entero de
# títulos (ver `resolver_split`).
_EPS_SALDO = 1e-6


class TickerDuplicadoError(ValueError):
    """Se lanza al intentar dar de alta un Valor cuyo ticker ya existe."""


# Igual que cartera_db._PRIORIDAD_MISMO_DIA, pero solo para los tipos que
# mueven el saldo de títulos: en caso de empate de fecha, primero
# Split/Contrasplit/Spinoff (reescalan/crean lo que corresponda), luego
# una Venta (criterio conservador: si vendes y compras el mismo día, no
# se asume que la compra "llegó antes" para tapar la venta) y por último
# Compra/Script.
_PRIORIDAD_MISMO_DIA_SALDO = {
    "Split": 0,
    "Contrasplit": 0,
    "Spinoff": 0,
    "Venta": 1,
    "Compra": 2,
    "Script": 2,
}

# Tipos que mueven el saldo de títulos de un bróker (ver calcular_saldo /
# validar_saldo_nunca_negativo): Split SUMA su num_titulos (ya resuelto,
# ver models.Operacion.num_titulos) igual que Compra/Script, y
# Contrasplit RESTA igual que Venta. Spinoff también SUMA: en la fila de
# la matriz num_titulos vale siempre 0 (no le afecta), y en la fila de
# la filial es el nº de títulos nuevos recibidos, igual que una Compra.
_TIPOS_QUE_SUMAN_SALDO = ("Compra", "Script", "Split", "Spinoff")
_TIPOS_QUE_RESTAN_SALDO = ("Venta", "Contrasplit")
_TIPOS_SALDO = _TIPOS_QUE_SUMAN_SALDO + _TIPOS_QUE_RESTAN_SALDO


def obtener_brokers() -> list[str]:
    with rx.session() as session:
        return [b.nombre for b in session.exec(sqlmodel.select(Broker)).all()]


def obtener_valores() -> list[dict]:
    """{ticker, empresa, mercado} de todo el catálogo de valores.

    Nota: de momento es el catálogo global, no solo lo que el usuario
    posee en la cartera seleccionada (eso requiere calcular tenencias a
    partir de las operaciones, algo que dejamos para cuando montemos la
    página CARTERA).
    """
    with rx.session() as session:
        return [
            {"ticker": v.ticker, "empresa": v.empresa, "mercado": v.mercado}
            for v in session.exec(sqlmodel.select(Valor)).all()
        ]


def obtener_valores_por_ticker(ticker: str) -> list[dict]:
    """Todos los Valores ya registrados con este ticker (en cualquier
    mercado). Se usa para avisar, al buscar un valor nuevo, de que ese
    ticker ya existe en el catálogo -- puede ser el mismo valor (mismo
    mercado, bloquea el alta) o la misma empresa en otro mercado (pide
    confirmación antes de dar de alta un segundo Valor)."""
    with rx.session() as session:
        filas = session.exec(sqlmodel.select(Valor).where(Valor.ticker == ticker)).all()
        return [{"empresa": v.empresa, "mercado": v.mercado} for v in filas]


def obtener_sectores() -> list[dict]:
    with rx.session() as session:
        return [
            {"supersector": s.supersector, "sector": s.sector, "grupo": s.grupo}
            for s in session.exec(sqlmodel.select(Sector)).all()
        ]


def obtener_cartera_id(id_usuario: int, tipo_cartera: str) -> int | None:
    with rx.session() as session:
        cartera = session.exec(
            sqlmodel.select(Cartera).where(
                Cartera.id_usuario == id_usuario,
                Cartera.tipo_cartera == tipo_cartera,
            )
        ).first()
        return cartera.id if cartera else None


def obtener_ultimo_broker(id_cartera: int) -> str | None:
    with rx.session() as session:
        operacion = session.exec(
            sqlmodel.select(Operacion)
            .where(Operacion.id_cartera == id_cartera)
            .order_by(Operacion.fecha.desc())
        ).first()
        if operacion is None:
            return None
        broker = session.get(Broker, operacion.id_broker)
        return broker.nombre if broker else None


def obtener_valor_id_por_ticker_mercado(ticker: str, mercado: str) -> int | None:
    with rx.session() as session:
        valor = session.exec(
            sqlmodel.select(Valor).where(Valor.ticker == ticker, Valor.mercado == mercado)
        ).first()
        return valor.id if valor else None


def obtener_broker_id_por_nombre(nombre: str) -> int | None:
    with rx.session() as session:
        broker = session.exec(sqlmodel.select(Broker).where(Broker.nombre == nombre)).first()
        return broker.id if broker else None


def obtener_sector_id(supersector: str, sector: str, grupo: str) -> int | None:
    with rx.session() as session:
        fila = session.exec(
            sqlmodel.select(Sector).where(
                Sector.supersector == supersector,
                Sector.sector == sector,
                Sector.grupo == grupo,
            )
        ).first()
        return fila.id if fila else None


def crear_valor(
    ticker: str, empresa: str, id_sector: int, mercado: str, zona: str, moneda: str
) -> int:
    with rx.session() as session:
        valor = Valor(
            ticker=ticker,
            empresa=empresa,
            id_sector=id_sector,
            mercado=mercado,
            zona=zona,
            moneda=moneda,
        )
        session.add(valor)
        try:
            session.commit()
        except sqlalchemy.exc.IntegrityError:
            session.rollback()
            raise TickerDuplicadoError(
                f"Ya tienes registrado el valor «{ticker}» exactamente en el mercado "
                f"«{mercado}». Selecciónalo como valor existente en lugar de darlo de "
                "alta de nuevo."
            ) from None
        session.refresh(valor)
        return valor.id


def obtener_operaciones(id_cartera: int) -> list[dict]:
    """Todas las operaciones de una cartera, con ticker/empresa/broker ya
    unidos, listas para listar/ordenar/filtrar y para precargar el
    formulario de edición."""
    with rx.session() as session:
        filas = session.exec(
            sqlmodel.select(Operacion, Valor, Broker)
            .where(Operacion.id_cartera == id_cartera)
            .join(Valor, Operacion.id_valor == Valor.id)
            .join(Broker, Operacion.id_broker == Broker.id)
        ).all()
        return [
            {
                "id": op.id,
                "tipo_operacion": op.tipo_operacion,
                "fecha": op.fecha.isoformat(),
                "fecha_mostrar": op.fecha.strftime("%d/%m/%Y"),
                "id_valor": valor.id,
                "ticker": valor.ticker,
                "empresa": valor.empresa,
                "id_broker": broker.id,
                "num_titulos": op.num_titulos,
                "num_titulos_mostrar": formatear_titulos(op.num_titulos),
                "broker": broker.nombre,
                "importe": op.importe,
                "importe_unitario": op.importe_unitario,
                "retencion_origen": op.retencion_origen,
                "retencion_destino": op.retencion_destino,
                "tipo_derecho_script": op.tipo_derecho_script,
                "ratio": op.ratio,
                "tipo_ajuste_fraccion": op.tipo_ajuste_fraccion,
                "id_valor_relacionado": op.id_valor_relacionado,
                "pct_reparto": op.pct_reparto,
                "observaciones": op.observaciones or "",
            }
            for op, valor, broker in filas
        ]


def obtener_operaciones_de_valor(id_cartera: int, id_valor: int) -> list[dict]:
    """Como `obtener_operaciones`, pero solo las de un valor concreto
    (para el listado de la página de detalle de valor), ordenadas de más
    reciente a más antigua."""
    with rx.session() as session:
        filas = session.exec(
            sqlmodel.select(Operacion, Valor, Broker)
            .where(Operacion.id_cartera == id_cartera, Operacion.id_valor == id_valor)
            .join(Valor, Operacion.id_valor == Valor.id)
            .join(Broker, Operacion.id_broker == Broker.id)
        ).all()
        datos = [
            {
                "id": op.id,
                "tipo_operacion": op.tipo_operacion,
                "fecha": op.fecha.isoformat(),
                "fecha_mostrar": op.fecha.strftime("%d/%m/%Y"),
                "id_valor": valor.id,
                "ticker": valor.ticker,
                "empresa": valor.empresa,
                "id_broker": broker.id,
                "num_titulos": op.num_titulos,
                "num_titulos_mostrar": formatear_titulos(op.num_titulos),
                "broker": broker.nombre,
                "importe": op.importe,
                "importe_unitario": op.importe_unitario,
                "retencion_origen": op.retencion_origen,
                "retencion_destino": op.retencion_destino,
                "tipo_derecho_script": op.tipo_derecho_script,
                "observaciones": op.observaciones or "",
            }
            for op, valor, broker in filas
        ]
        return sorted(datos, key=lambda d: d["fecha"], reverse=True)


def calcular_saldo(
    id_cartera: int,
    id_valor: int,
    id_broker: int,
    fecha_limite: date,
    excluir_id_operacion: int | None = None,
) -> float:
    """Nº de títulos que se poseían de este valor, en este bróker y esta
    cartera, hasta `fecha_limite` inclusive: Compra + Script (tanto si el
    derecho se compró como si se vendió, ambos aportan títulos) + Split,
    menos Venta y Contrasplit. Dividendo y Prima no alteran el nº de
    títulos, así que no cuentan aquí. `excluir_id_operacion` sirve para
    recalcular el saldo al EDITAR una operación, sin contarse a sí
    misma."""
    with rx.session() as session:
        query = sqlmodel.select(Operacion).where(
            Operacion.id_cartera == id_cartera,
            Operacion.id_valor == id_valor,
            Operacion.id_broker == id_broker,
            Operacion.fecha <= fecha_limite,
            Operacion.tipo_operacion.in_(_TIPOS_SALDO),
        )
        if excluir_id_operacion is not None:
            query = query.where(Operacion.id != excluir_id_operacion)
        saldo = 0.0
        for op in session.exec(query).all():
            if op.tipo_operacion in _TIPOS_QUE_RESTAN_SALDO:
                saldo -= op.num_titulos
            else:
                saldo += op.num_titulos
        return saldo


def resolver_split(
    id_cartera: int,
    id_valor: int,
    id_broker: int,
    fecha: date,
    ratio: float,
) -> dict:
    """Para el formulario de Split/Contrasplit: a partir del saldo que
    ya se tiene en este bróker+valor+cartera a `fecha` (ver
    `calcular_saldo`) y el `ratio` (nuevo/antiguo, p.ej. 10.0 en un
    split 1→10, o 0.1 en un contrasplit 10→1) que se quiere aplicar,
    calcula el resultado teórico y si deja fracción de título -- toda
    la aritmética que si no habría que hacer a mano (ver conversación
    de diseño del 24/09/2026 sobre Split/Contrasplit).

    Devuelve:
    - "saldo_actual": el saldo de partida en este bróker.
    - "teorico": saldo_actual * ratio, sin redondear.
    - "es_entero": True si `teorico` ya es un número entero de títulos
      (con tolerancia), en cuyo caso no hace falta preguntar nada sobre
      fracciones -- el formulario usa directamente "entero_abajo".
    - "entero_abajo" / "entero_arriba": el entero inmediatamente por
      debajo/por encima de `teorico` (iguales entre sí si es_entero).
      Cuando NO es_entero, el formulario le pregunta al usuario qué
      pasó con la fracción (ver models.Operacion.tipo_ajuste_fraccion)
      y usa "entero_abajo" (el bróker pagó/perdió la fracción) o
      "entero_arriba" (el bróker completó hasta el título entero,
      gratis o pagando) según la respuesta.
    - "fraccion": tamaño de esa fracción (0.0 si es_entero).
    """
    saldo_actual = calcular_saldo(id_cartera, id_valor, id_broker, fecha)
    teorico = saldo_actual * ratio
    entero_abajo = math.floor(teorico + _EPS_SALDO)
    entero_arriba = math.ceil(teorico - _EPS_SALDO)
    es_entero = entero_arriba == entero_abajo
    return {
        "saldo_actual": saldo_actual,
        "teorico": teorico,
        "es_entero": es_entero,
        "entero_abajo": entero_abajo,
        "entero_arriba": entero_arriba,
        "fraccion": 0.0 if es_entero else round(abs(teorico - entero_abajo), 6),
    }


def resolver_spinoff(
    id_cartera: int,
    id_valor_matriz: int,
    id_broker: int,
    fecha: date,
    pct_reparto_matriz: float,
    ratio_titulos_matriz: float,
    ratio_titulos_filial: float,
) -> dict:
    """Para el formulario de Spinoff: toda la aritmética a partir de lo
    que ya tienes en la MATRIZ, en ESE bróker concreto, a esa fecha --
    igual que `resolver_split` para Split/Contrasplit, nunca a mano (ver
    conversación de diseño del 24-25/09/2026).

    `pct_reparto_matriz`: % (0-1) del coste que se QUEDA en la matriz;
    el resto (1 - esto) es lo que se transfiere a la filial.
    `ratio_titulos_matriz` / `ratio_titulos_filial`: por cada
    `ratio_titulos_matriz` títulos de la matriz, corresponden
    `ratio_titulos_filial` títulos de la filial (p.ej. 4 y 1 en un
    reparto de "1 acción de filial por cada 4 de matriz").

    A diferencia de `resolver_split`, aquí además hace falta el COSTE
    total de la matriz en ese bróker (no solo el nº de títulos) para
    saber cuánto se transfiere a la filial -- por eso usa
    `cartera_db.obtener_coste_total_broker`, la única función que
    calcula coste FIFO filtrado a un solo bróker (ver su docstring).

    Devuelve:
    - "saldo_matriz" / "coste_matriz": títulos y coste total que ya
      tienes en la matriz en ese bróker.
    - "coste_transferido": la parte de ese coste que pasa a la filial.
    - "teorico" / "es_entero" / "entero_abajo" / "entero_arriba" /
      "fraccion": el nº de títulos de filial que corresponden según el
      ratio, igual que en `resolver_split`.
    """
    from gestion_cartera.cartera_db import obtener_coste_total_broker

    saldo_matriz = calcular_saldo(id_cartera, id_valor_matriz, id_broker, fecha)
    coste_matriz = obtener_coste_total_broker(id_cartera, id_valor_matriz, id_broker, fecha)
    coste_transferido = coste_matriz * (1 - pct_reparto_matriz)
    teorico = (
        saldo_matriz * (ratio_titulos_filial / ratio_titulos_matriz)
        if ratio_titulos_matriz
        else 0.0
    )
    entero_abajo = math.floor(teorico + _EPS_SALDO)
    entero_arriba = math.ceil(teorico - _EPS_SALDO)
    es_entero = entero_arriba == entero_abajo
    return {
        "saldo_matriz": saldo_matriz,
        "coste_matriz": coste_matriz,
        "coste_transferido": coste_transferido,
        "teorico": teorico,
        "es_entero": es_entero,
        "entero_abajo": entero_abajo,
        "entero_arriba": entero_arriba,
        "fraccion": 0.0 if es_entero else round(abs(teorico - entero_abajo), 6),
    }


def validar_saldo_nunca_negativo(
    id_cartera: int,
    id_valor: int,
    id_broker: int,
    *,
    excluir_id_operacion: int | None = None,
    operacion_simulada: dict | None = None,
) -> str | None:
    """Recorre TODA la línea temporal de Compra/Venta/Script de este valor
    en este bróker (no solo un punto concreto) y comprueba que el saldo
    acumulado nunca sea negativo en ningún momento.

    Se usa al editar o borrar una operación: a diferencia de
    `calcular_saldo` (que da el saldo hasta una fecha), esto detecta
    también el caso en que el cambio deja *inválida* alguna operación
    POSTERIOR que hasta ahora encajaba (p. ej. reducir o borrar una
    Compra de la que una Venta futura ya disponía).

    `excluir_id_operacion` saca esa operación del recuento (se está
    editando o borrando y no debe contarse dos veces / en su estado
    antiguo). `operacion_simulada` -- un dict con `fecha`,
    `tipo_operacion` y `num_titulos` -- se añade como si ya existiera,
    para validar el resultado ANTES de guardarlo.

    Devuelve un mensaje de error con la fecha y el tipo de la operación
    donde se incumple, o None si el saldo se mantiene siempre >= 0.
    """
    with rx.session() as session:
        query = sqlmodel.select(Operacion).where(
            Operacion.id_cartera == id_cartera,
            Operacion.id_valor == id_valor,
            Operacion.id_broker == id_broker,
            Operacion.tipo_operacion.in_(_TIPOS_SALDO),
        )
        if excluir_id_operacion is not None:
            query = query.where(Operacion.id != excluir_id_operacion)
        operaciones = [
            {
                "fecha": op.fecha,
                "tipo_operacion": op.tipo_operacion,
                "num_titulos": op.num_titulos,
            }
            for op in session.exec(query).all()
        ]

    if operacion_simulada is not None:
        operaciones.append(operacion_simulada)

    operaciones.sort(
        key=lambda o: (o["fecha"], _PRIORIDAD_MISMO_DIA_SALDO.get(o["tipo_operacion"], 1))
    )

    saldo = 0.0
    for op in operaciones:
        if op["tipo_operacion"] in _TIPOS_QUE_RESTAN_SALDO:
            saldo -= op["num_titulos"]
        else:
            saldo += op["num_titulos"]
        if saldo < -1e-9:
            return (
                f"Esta modificación deja el saldo en negativo ({saldo:g} títulos) a partir "
                f"de la operación de {op['tipo_operacion']} del {op['fecha'].strftime('%d/%m/%Y')}."
            )
    return None


def buscar_operacion_compensatoria(
    id_cartera: int,
    id_valor: int,
    id_broker: int,
    num_titulos_diferencia: float,
    fecha_limite: date,
    excluir_id_operacion: int | None = None,
) -> dict | None:
    """Para explicar un descuadre en un Dividendo: busca una Compra o
    Venta (mismo valor+bróker+cartera) de exactamente
    `num_titulos_diferencia` títulos, fechada en los 30 días anteriores a
    `fecha_limite` (sin incluir ese mismo día). Devuelve la primera que
    encuentre, o None."""
    desde = fecha_limite - timedelta(days=30)
    with rx.session() as session:
        query = sqlmodel.select(Operacion).where(
            Operacion.id_cartera == id_cartera,
            Operacion.id_valor == id_valor,
            Operacion.id_broker == id_broker,
            Operacion.tipo_operacion.in_(["Compra", "Venta"]),
            Operacion.fecha >= desde,
            Operacion.fecha < fecha_limite,
            Operacion.num_titulos == num_titulos_diferencia,
        )
        if excluir_id_operacion is not None:
            query = query.where(Operacion.id != excluir_id_operacion)
        op = session.exec(query).first()
        if op is None:
            return None
        return {
            "tipo_operacion": op.tipo_operacion,
            "fecha_mostrar": op.fecha.strftime("%d/%m/%Y"),
            "num_titulos": op.num_titulos,
        }


def actualizar_operacion(
    id_operacion: int,
    *,
    fecha: date,
    id_broker: int,
    num_titulos: float,
    importe: float,
    importe_unitario: float | None,
    retencion_origen: float | None,
    retencion_destino: float | None,
    tipo_derecho_script: str | None,
    observaciones: str | None,
    ratio: float | None = None,
    tipo_ajuste_fraccion: str | None = None,
    id_valor_relacionado: int | None = None,
    pct_reparto: float | None = None,
) -> None:
    with rx.session() as session:
        op = session.get(Operacion, id_operacion)
        if op is None:
            return
        op.fecha = fecha
        op.id_broker = id_broker
        op.num_titulos = num_titulos
        op.importe = importe
        op.importe_unitario = importe_unitario
        op.retencion_origen = retencion_origen
        op.retencion_destino = retencion_destino
        op.tipo_derecho_script = tipo_derecho_script
        op.observaciones = observaciones
        # Split/Contrasplit/Spinoff: ver crear_operacion más abajo. Para
        # el resto de tipos siempre se guardan a None (no aplican).
        op.ratio = ratio
        op.tipo_ajuste_fraccion = tipo_ajuste_fraccion
        op.id_valor_relacionado = id_valor_relacionado
        op.pct_reparto = pct_reparto
        session.add(op)
        session.commit()


def eliminar_operacion(id_operacion: int) -> None:
    with rx.session() as session:
        op = session.get(Operacion, id_operacion)
        if op is not None:
            session.delete(op)
            session.commit()


def crear_operacion(
    *,
    id_cartera: int,
    id_valor: int,
    id_broker: int,
    tipo_operacion: str,
    fecha: date,
    num_titulos: float,
    importe: float,
    importe_unitario: float | None,
    retencion_origen: float | None,
    retencion_destino: float | None,
    tipo_derecho_script: str | None,
    observaciones: str | None,
    ratio: float | None = None,
    tipo_ajuste_fraccion: str | None = None,
    id_valor_relacionado: int | None = None,
    pct_reparto: float | None = None,
) -> int:
    """`ratio`/`tipo_ajuste_fraccion` aplican a Split/Contrasplit (ver
    comentarios en models.Operacion); `id_valor_relacionado`/
    `pct_reparto` a Spinoff -- para el resto de tipos se dejan en None.
    `num_titulos` ya viene RESUELTO desde el formulario
    (states/alta_operacion_form.py, vía operaciones_db.resolver_split /
    resolver_spinoff): el delta de títulos que se suma o resta en este
    bróker en concreto, no el ratio en bruto."""
    with rx.session() as session:
        operacion = Operacion(
            id_cartera=id_cartera,
            id_valor=id_valor,
            id_broker=id_broker,
            tipo_operacion=tipo_operacion,
            fecha=fecha,
            num_titulos=num_titulos,
            importe=importe,
            importe_unitario=importe_unitario,
            retencion_origen=retencion_origen,
            retencion_destino=retencion_destino,
            tipo_derecho_script=tipo_derecho_script,
            observaciones=observaciones,
            ratio=ratio,
            tipo_ajuste_fraccion=tipo_ajuste_fraccion,
            id_valor_relacionado=id_valor_relacionado,
            pct_reparto=pct_reparto,
        )
        session.add(operacion)
        session.commit()
        session.refresh(operacion)
        return operacion.id