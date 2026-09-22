from datetime import date, datetime
from typing import Optional

import reflex as rx
import sqlmodel


class Usuario(rx.Model, table=True):
    __tablename__ = "usuarios"

    nombre: str
    email: str = sqlmodel.Field(unique=True, index=True)
    password_hash: str
    # True al crear el usuario: se le fuerza a cambiarla en su primer
    # inicio de sesión, ver components/auth.py y states/auth_state.py.
    debe_cambiar_password: bool = True
    # Permite revocar el acceso de un usuario sin borrar sus datos.
    activo: bool = True


class Cartera(rx.Model, table=True):
    __tablename__ = "carteras"
    __table_args__ = (
        sqlmodel.UniqueConstraint(
            "id_usuario", "tipo_cartera", name="uq_cartera_usuario_tipo"
        ),
    )

    id_usuario: int = sqlmodel.Field(foreign_key="usuarios.id")
    tipo_cartera: str  # "Largo Plazo" | "Corto Plazo"


class Broker(rx.Model, table=True):
    __tablename__ = "brokers"

    nombre: str = sqlmodel.Field(unique=True)


class Sector(rx.Model, table=True):
    """Una fila = un Grupo de industria de Morningstar, con su Sector y
    Supersector correspondientes ya "aplanados" en la misma fila. Es una
    tabla de referencia (semi-estática, se puebla una vez con
    `seed_sectores.py`), no algo que el usuario edite.
    """

    __tablename__ = "sectores"
    __table_args__ = (
        sqlmodel.UniqueConstraint(
            "supersector", "sector", "grupo", name="uq_sector_jerarquia"
        ),
    )

    supersector: str  # Cíclico | Defensivo | Sensible
    sector: str  # uno de los 11 sectores Morningstar
    grupo: str  # uno de los 55 grupos de industria Morningstar


class Valor(rx.Model, table=True):
    """Un mismo ticker puede existir más de una vez si cotiza en más de
    un mercado (p.ej. una acción y su ADR): lo que es único es la
    combinación ticker+mercado, no el ticker por sí solo.
    """

    __tablename__ = "valores"
    __table_args__ = (
        sqlmodel.UniqueConstraint("ticker", "mercado", name="uq_valor_ticker_mercado"),
    )

    ticker: str = sqlmodel.Field(index=True)
    empresa: str
    id_sector: int = sqlmodel.Field(foreign_key="sectores.id")
    mercado: Optional[str] = None  # bolsa donde cotiza (NASDAQ, NYSE, BME...)
    zona: str  # ESP | EURO | USA | UK
    moneda: str  # divisa de cotización (USD, GBP, EUR...), la da Twelve Data

    # Caché de cotización (no se pide cada vez a Twelve Data, se refresca
    # solo cuando este dato está "viejo"; ver services/twelvedata.py).
    cotizacion_divisa: Optional[float] = None  # precio en la divisa original
    cotizacion_eur: Optional[float] = None  # precio convertido a euros
    cotizacion_actualizada_en: Optional[datetime] = None


class ObjetivoBalance(rx.Model, table=True):
    """Peso 'objetivo' (entero 0-100) que el usuario quiere para cada
    categoría de supersector o de zona, usado en la página RADAR
    (/radar) para comparar contra el peso real de la cartera de Largo
    Plazo -- ver radar_db.py. La suma de los pesos de un mismo `tipo`
    debe valer 100 (se valida en states/radar_state.py, no aquí).
    """

    __tablename__ = "objetivos_balance"
    __table_args__ = (
        sqlmodel.UniqueConstraint(
            "id_usuario", "tipo", "categoria", name="uq_objetivo_usuario_tipo_categoria"
        ),
    )

    id_usuario: int = sqlmodel.Field(foreign_key="usuarios.id")
    tipo: str  # "supersector" | "zona"
    categoria: str  # uno de SUPERSECTORES o de ZONAS, según `tipo` (ver radar_db.py)
    peso: int


class RadarCandidato(rx.Model, table=True):
    """Fila de la lista de "posibles compras" de la página RADAR
    (/radar, punto 4 del encargo): un Valor en seguimiento, con el
    importe que se plantea invertir y los precios máx/mín de compra
    (en la divisa origen del propio valor, no en euros) -- ver
    radar_db.py.

    `id_valor` puede apuntar a un Valor sin ninguna Operacion todavía
    (se reutiliza el mismo alta de "valor nuevo" que en Operaciones,
    ver operaciones_db.crear_valor, pero sin comprar nada). Un mismo
    valor puede estar en la lista de Largo Plazo Y en la de Corto
    Plazo a la vez (dos filas distintas, ver `tipo_lista`) -- son
    listas de seguimiento independientes (punto 7 del encargo, fase
    futura: de momento solo se usa "Largo Plazo").
    """

    __tablename__ = "radar_candidatos"
    __table_args__ = (
        sqlmodel.UniqueConstraint(
            "id_usuario", "id_valor", "tipo_lista", name="uq_radar_candidato_usuario_valor_lista"
        ),
    )

    id_usuario: int = sqlmodel.Field(foreign_key="usuarios.id")
    id_valor: int = sqlmodel.Field(foreign_key="valores.id")
    tipo_lista: str = "Largo Plazo"  # "Largo Plazo" | "Corto Plazo"

    importe_invertir: float  # en euros
    precio_max: float  # en la divisa origen del valor (Valor.moneda)
    precio_min: Optional[float] = None  # en la divisa origen del valor


class Operacion(rx.Model, table=True):
    __tablename__ = "operaciones"

    id_cartera: int = sqlmodel.Field(foreign_key="carteras.id")
    id_valor: int = sqlmodel.Field(foreign_key="valores.id")
    id_broker: int = sqlmodel.Field(foreign_key="brokers.id")

    tipo_operacion: str  # Compra | Venta | Dividendo | Script | Prima
    fecha: date

    num_titulos: float
    importe: float

    # Calculado en el formulario (Importe / NumTits) pero SÍ se guarda,
    # salvo en Script, donde no aplica y se deja en None.
    importe_unitario: Optional[float] = None

    # Solo tienen valor en Dividendo y en Script con venta de derechos.
    retencion_origen: Optional[float] = None
    retencion_destino: Optional[float] = None

    # Solo aplica a Script: si hubo compra o venta de derechos .
    # Se guarda (a diferencia de importe_neto, que es solo informativo y
    # nunca se guarda).
    tipo_derecho_script: Optional[str] = None  # "Compra" | "Venta"

    observaciones: Optional[str] = None