from datetime import date, datetime, timezone
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
    # Número de teléfono (con prefijo de país, p.ej. "+34600000000") al
    # que se mandan los avisos de RADAR por SMS (punto 5 del encargo) --
    # ver services/twilio_sms.py y states/radar_candidato_state.py.
    # Opcional: sin él, ese usuario no recibe avisos, pero el resto de
    # la app funciona igual.
    #
    # OJO: se llamó primero `telefono_whatsapp` porque los avisos se
    # mandaban por WhatsApp -- se descartó esa vía (Meta exige verificar
    # una empresa real para el WhatsApp Sender de producción, y esto es
    # un proyecto personal sin actividad registrada) a favor de SMS, que
    # no lo exige. Se renombró antes de llegar a migrar la columna en
    # ninguna base de datos, así que no ha hecho falta ningún rename.
    telefono_avisos: Optional[str] = None


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
    importe que se plantea invertir y los precios de compra/venta
    (en la divisa origen del propio valor, no en euros) -- ver
    radar_db.py.

    `id_valor` puede apuntar a un Valor sin ninguna Operacion todavía
    (se reutiliza el mismo alta de "valor nuevo" que en Operaciones,
    ver operaciones_db.crear_valor, pero sin comprar nada). Un mismo
    valor puede estar en la lista de Largo Plazo Y en la de Corto
    Plazo a la vez (dos filas distintas, ver `tipo_lista`) -- son
    listas de seguimiento independientes.

    `precio_max` es el precio de COMPRA (el nombre del campo se quedó
    del diseño original, pero en la UI ya se llama "Precio de compra"):
    marca el color de la fila (rojo/ámbar, ver
    radar_db._color_fila_candidato) y dispara el aviso de compra.
    `precio_min` es el precio de VENTA (en la UI, "Precio de venta").
    Los dos son OPCIONALES e independientes entre sí: se puede dar de
    alta un candidato solo para vigilar el precio de venta sin fijar
    ningún precio de compra, y viceversa. `precio_min` nunca afecta al
    color de la fila (solo `precio_max` lo hace), y cualquiera de los
    dos, si está puesto, dispara su propio aviso cuando se alcanza.

    `alerta_enviada` (punto 5 del encargo, aviso de COMPRA): evita
    mandar el aviso por SMS una y otra vez mientras la fila siga en
    rojo -- se pone a True al mandar el aviso, y se vuelve a poner a
    False en cuanto la cotización deja de estar en rojo, para que si
    vuelve a bajar más adelante se pueda avisar de nuevo.

    `alerta_venta_enviada`: lo mismo pero para el aviso de VENTA (no
    tiene relación con el color de la fila) -- se pone a True al mandar
    el aviso de que la cotización alcanzó/superó el precio de venta, y
    se rearma a False en cuanto vuelve a caer por debajo, para poder
    avisar de nuevo si sube otra vez más adelante (ver
    states/radar_candidato_state.py, refrescar_cotizaciones).
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
    precio_max: Optional[float] = None  # precio de COMPRA, en la divisa origen del valor
    precio_min: Optional[float] = None  # precio de VENTA, en la divisa origen del valor
    alerta_enviada: bool = False
    alerta_venta_enviada: bool = False


class EjecucionRadarHoraria(rx.Model, table=True):
    """Una fila = un chequeo automático de RADAR en segundo plano ya
    ejecutado (ver services/radar_scheduler.py), identificada por la
    hora de Madrid a la que estaba programado ("2026-09-24T09:20").

    Sirve de "cerrojo" simple entre procesos: si por lo que sea hay
    más de una réplica de la app corriendo a la vez (varias instancias
    en Railway), la primera que consiga insertar su fila para esa hora
    (UniqueConstraint en `clave`) es la que ejecuta el chequeo de
    verdad; el resto se encuentra la fila ya creada y se la salta, para
    no duplicar el envío de SMS ni las llamadas a Yahoo Finance.
    """

    __tablename__ = "ejecuciones_radar_horarias"

    clave: str = sqlmodel.Field(unique=True, index=True)
    ejecutada_en: datetime = sqlmodel.Field(default_factory=lambda: datetime.now(timezone.utc))


class Operacion(rx.Model, table=True):
    __tablename__ = "operaciones"

    id_cartera: int = sqlmodel.Field(foreign_key="carteras.id")
    id_valor: int = sqlmodel.Field(foreign_key="valores.id")
    id_broker: int = sqlmodel.Field(foreign_key="brokers.id")

    tipo_operacion: str  # Compra | Venta | Dividendo | Script | Prima | Split | Contrasplit | Spinoff
    fecha: date

    # Para Split/Contrasplit, `num_titulos` es el resultado YA RESUELTO
    # (títulos que se añaden -- Split -- o se quitan -- Contrasplit --
    # de este bróker en concreto), calculado una sola vez al guardar la
    # operación a partir de `ratio` y el saldo de ese momento -- ver
    # states/operaciones_state.py. Se guarda así (en vez de recalcularlo
    # cada vez a partir de `ratio`) para que las funciones de saldo
    # ligeras (operaciones_db.calcular_saldo /
    # validar_saldo_nunca_negativo) puedan seguir sumando/restando
    # `num_titulos` sin más, igual que con Compra/Venta/Script, sin
    # tener que conocer el mecanismo de reescalado FIFO.
    #
    # Spinoff genera SIEMPRE dos filas ligadas (ver `id_valor_relacionado`
    # más abajo), y aquí es donde se distinguen: en la fila de la MATRIZ
    # vale siempre 0.0 (un spinoff nunca cambia su nº de títulos, solo
    # reescala coste -- ver `pct_reparto`); en la fila de la FILIAL es el
    # nº de títulos nuevos recibidos (> 0), igual que en una Compra. Si
    # el ratio de títulos dejaba fracción y se cobró en efectivo, esa
    # fracción se guarda como una TERCERA fila, una Venta normal aparte
    # sobre la filial, sin ningún campo especial de Spinoff.
    num_titulos: float
    importe: float

    # Calculado en el formulario (Importe / NumTits) pero SÍ se guarda,
    # salvo en Script/Split/Contrasplit, donde no aplica y se deja en
    # None (en Split/Contrasplit el importe, si lo hay, es el de la
    # fracción -- ver `tipo_ajuste_fraccion` -- no el de "todos los
    # títulos", así que dividir por num_titulos no tendría sentido).
    importe_unitario: Optional[float] = None

    # Solo tienen valor en Dividendo, en Script con venta de derechos, y
    # en Split/Contrasplit cuando la fracción sobrante se cobró en
    # efectivo (tipo_ajuste_fraccion == "Venta").
    retencion_origen: Optional[float] = None
    retencion_destino: Optional[float] = None

    # Solo aplica a Script: si hubo compra o venta de derechos .
    # Se guarda (a diferencia de importe_neto, que es solo informativo y
    # nunca se guarda).
    tipo_derecho_script: Optional[str] = None  # "Compra" | "Venta"

    # Solo aplica a Split/Contrasplit: la proporción nueva/antigua del
    # ratio (10.0 en un split 1→10; 0.1 en un contrasplit 10→1) -- ver
    # cartera_db.PosicionFIFO.aplicar_split. Es lo que usa el motor FIFO
    # (cartera_db.py, resumen_irpf_db.py, valor_db.py) para reescalar
    # los lotes que ya se poseían SIN alterar su coste total, algo que
    # `num_titulos` por sí solo no permite reconstruir con precisión
    # (dos brokers con el mismo ratio nominal pueden acabar con una
    # fracción de título distinta cada uno, según el saldo de partida).
    ratio: Optional[float] = None

    # Solo aplica a Split/Contrasplit cuando el ratio no da un número
    # entero de títulos y el bróker resolvió la fracción sobrante con
    # dinero de por medio (si el ajuste fue "gratis", se deja en None):
    # "Venta" -- el bróker pagó esa fracción (ver `importe` y las
    # retenciones de arriba) y cuenta como una venta parcial más a
    # efectos de plusvalía; "Compra" -- hubo que abonar algo para
    # completar el título (el importe entra como coste nuevo, sin
    # retenciones -- no se retiene sobre dinero que uno mismo paga).
    tipo_ajuste_fraccion: Optional[str] = None  # "Compra" | "Venta"

    # Solo aplica a Spinoff: id del Valor "al otro lado" de esta fila --
    # desde la fila de la matriz apunta a la filial, y viceversa. Ambas
    # filas comparten fecha y bróker, y se dan de alta y se enlazan a la
    # vez (ver states/alta_operacion_form.py._guardar_spinoff). Sirve
    # sobre todo de trazabilidad -- el motor FIFO (cartera_db.py) no lo
    # necesita para calcular nada, porque cada fila ya lleva resuelto
    # todo lo que le hace falta a SU PROPIO Valor (ver `num_titulos` y
    # `pct_reparto`).
    id_valor_relacionado: Optional[int] = sqlmodel.Field(
        default=None, foreign_key="valores.id"
    )

    # Solo aplica a Spinoff, y solo tiene efecto en la fila de la MATRIZ
    # (en la fila de la filial se guarda igualmente, por trazabilidad,
    # pero el motor FIFO no lo usa: ver `aplicar_spinoff`). Es el % (0-1)
    # del coste de la matriz que se QUEDA en la matriz -- el resto
    # (1 - esto) es el que se transfiere a la filial. Se aplica
    # multiplicando el `coste_unitario` de cada lote vivo de la matriz,
    # SIN tocar su nº de títulos (a diferencia de `ratio` en
    # Split/Contrasplit, que reescala títulos y coste a la vez) -- ver
    # cartera_db.PosicionFIFO.aplicar_reescalado_coste.
    pct_reparto: Optional[float] = None

    observaciones: Optional[str] = None