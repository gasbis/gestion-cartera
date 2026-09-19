"""Consultas de base de datos para el formulario de alta de operación:
listar brokers/valores/sectores, resolver ids, crear un Valor nuevo y
guardar la Operacion final.
"""

from datetime import date, timedelta

import reflex as rx
import sqlalchemy.exc
import sqlmodel

from gestion_cartera.format_utils import formatear_titulos
from gestion_cartera.models import Broker, Cartera, Operacion, Sector, Valor


class TickerDuplicadoError(ValueError):
    """Se lanza al intentar dar de alta un Valor cuyo ticker ya existe."""


# Igual que cartera_db._PRIORIDAD_MISMO_DIA, pero solo para los tipos que
# mueven el saldo de títulos: en caso de empate de fecha, una Venta se
# considera ANTES que una Compra/Script del mismo día (criterio
# conservador: si vendes y compras el mismo día, no se asume que la
# compra "llegó antes" para tapar la venta).
_PRIORIDAD_MISMO_DIA_SALDO = {"Venta": 0, "Compra": 1, "Script": 1}


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
    derecho se compró como si se vendió, ambos aportan títulos), menos
    Venta. Dividendo y Prima no alteran el nº de títulos, así que no
    cuentan aquí. `excluir_id_operacion` sirve para recalcular el saldo
    al EDITAR una operación, sin contarse a sí misma."""
    with rx.session() as session:
        query = sqlmodel.select(Operacion).where(
            Operacion.id_cartera == id_cartera,
            Operacion.id_valor == id_valor,
            Operacion.id_broker == id_broker,
            Operacion.fecha <= fecha_limite,
            Operacion.tipo_operacion.in_(["Compra", "Venta", "Script"]),
        )
        if excluir_id_operacion is not None:
            query = query.where(Operacion.id != excluir_id_operacion)
        saldo = 0.0
        for op in session.exec(query).all():
            if op.tipo_operacion == "Venta":
                saldo -= op.num_titulos
            else:  # Compra, Script
                saldo += op.num_titulos
        return saldo


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
            Operacion.tipo_operacion.in_(["Compra", "Venta", "Script"]),
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
        if op["tipo_operacion"] == "Venta":
            saldo -= op["num_titulos"]
        else:  # Compra, Script
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
) -> int:
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
        )
        session.add(operacion)
        session.commit()
        session.refresh(operacion)
        return operacion.id