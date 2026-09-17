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


# --- Espaciados --------------------------------------------------------
# Escala única para padding/margin manuales, para no ir mezclando "1em",
# "0.75em", "50" sueltos por el código como en el boceto inicial.
SPACE_XS = "0.5em"
SPACE_SM = "0.75em"
SPACE_MD = "1em"
SPACE_LG = "1.5em"
SPACE_XL = "2em"