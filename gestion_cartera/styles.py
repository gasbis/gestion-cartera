"""Tokens de diseño propios de la app.

Estos NO sustituyen el tema de Radix (fondo, superficies, texto, botones,
selects...) que se configura en `app.py` con `rx.theme(...)`. Este módulo
cubre solo lo que Radix no puede inferir por sí solo: la semántica
financiera de ganancia/pérdida y una escala de espaciados consistente
para usar en props como `padding`/`margin` donde no hay un prop nativo
tipo `spacing="4"`.
"""

# --- Semántica financiera --------------------------------------------------
# Usar SIEMPRE estos dos para valores con signo (rentabilidad, saldo,
# revalorización). No reutilizar el color de acento (azul) para esto: el
# acento es de marca/interacción, esta es información de estado.
POSITIVE = "var(--green-9)"   # ganancia / saldo positivo / revalorización al alza
NEGATIVE = "var(--red-9)"     # pérdida / saldo negativo / revalorización a la baja
NEUTRAL = "var(--gray-9)"     # sin variación o dato no aplicable


def gain_loss_color(value: float) -> str:
    """Devuelve el color semántico correspondiente al signo de `value`.

    Pensado para colorear cifras de rentabilidad/saldo una vez vengan de
    datos reales, p.ej.: `color=gain_loss_color(saldo_valor)`.
    """
    if value > 0:
        return POSITIVE
    if value < 0:
        return NEGATIVE
    return NEUTRAL


# --- Enlaces / navegación -----------------------------------------------
# Color compartido por los enlaces del menú de navegación y por cualquier
# otro texto que deba verse "como un enlace" (p.ej. el nombre de usuario
# en la barra de cartera), para que ambos coincidan siempre por
# construcción en vez de depender del valor por defecto de Radix.
LINK_COLOR = "var(--accent-11)"


# --- Espaciados --------------------------------------------------------
# Escala única para padding/margin manuales, para no ir mezclando "1em",
# "0.75em", "50" sueltos por el código como en el boceto inicial.
SPACE_XS = "0.5em"
SPACE_SM = "0.75em"
SPACE_MD = "1em"
SPACE_LG = "1.5em"
SPACE_XL = "2em"


# --- Tablas --------------------------------------------------------------
# Cabecera de tabla "pegada" arriba al hacer scroll, para que en
# listados largos (CARTERA, OPERACIONES) los nombres de columna no
# desaparezcan por arriba. Se aplica a cada `column_header_cell` (celda
# <th>) por separado, NO al `table.header` (<thead>) que las envuelve:
# `position: sticky` en el propio <thead> no se comporta de forma
# fiable en un layout de tabla, mientras que aplicado celda a celda es
# el patrón estándar y sí funciona siempre.
#
# IMPORTANTE (verificado con un repro aislado en navegador real, vía
# Playwright, tras varios intentos fallidos basados en suposiciones):
# `rx.table.root` (Radix `Table.Root`) NO es una tabla "plana" -- por
# dentro envuelve el <table> en su propio componente `ScrollArea`
# (`rt-ScrollAreaRoot` > `rt-ScrollAreaViewport`, con
# `overflow: scroll`), que es el ancestro real y más cercano al `<th>`
# a efectos de `position: sticky`. Cualquier `max_height`/`overflow`
# puesto en una caja NUESTRA por fuera (como hacía antes `scroll_x`)
# nunca llega a esa capa interna de Radix -- así que ese
# `ScrollAreaViewport` nunca queda con una altura acotada, nunca
# scrollea de verdad, y la cabecera (pegada a él) no se queda fija:
# se desplaza como una fila más.
#
# La única forma que funciona es pasar `height` (fijo, NO
# `max_height`) directamente como prop en la llamada a
# `rx.table.root(...)` de cada página -- así SÍ llega al
# `ScrollAreaViewport` interno, que entonces queda acotado a esa
# altura y scrollea de verdad, tanto en vertical (con lo que
# `position: sticky` en cada `column_header_cell` por fin se pega a
# él) como en horizontal (columnas anchas). Ya no hace falta envolver
# la tabla en `scroll_x` ni fijar ningún `overflow` a mano: basta con
# `rx.table.root(..., width="100%", height="75vh", min_width="0")`.
# `top="0"` en `STICKY_TABLE_HEADER` es relativo a ese
# `ScrollAreaViewport`, no a la ventana entera. El fondo es
# imprescindible: sin él, al quedar la celda fija encima de las filas
# que van desfilando por debajo se verían a través suyo.
STICKY_TABLE_HEADER = {
    "position": "sticky",
    "top": "0",
    "z_index": "1",
    "background_color": "var(--gray-1)",
}