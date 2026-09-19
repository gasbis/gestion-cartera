"""Envoltorio para contenido ancho (normalmente una `rx.table.root` con
muchas columnas): en pantallas estrechas, en vez de comprimirse hasta
ser ilegible o romper el layout de la página, el contenido se puede
desplazar horizontalmente dentro de su propio contenedor."""

import reflex as rx


def scroll_x(*children: rx.Component, **props) -> rx.Component:
    # Un pequeño padding a la derecha: si la última columna termina
    # justo en el borde del área con scroll, se ve "cortada" (el
    # propio contenedor tapa el último pixel de su contenido). Con un
    # respiro mínimo queda siempre visible entera, se necesite o no el
    # scroll. `setdefault` para que una página pueda pisarlo si hace
    # falta.
    #
    # OJO: box_sizing="border-box" es imprescindible aquí -- sin él,
    # width="100%" + padding_right se SUMAN (box-sizing "content-box"
    # por defecto), así que el contenedor acababa siendo más ancho que
    # su propio padre y desbordaba la página entera (scroll horizontal
    # de más, todo desplazado). Con border-box el padding se descuenta
    # del 100%, no se añade.
    props.setdefault("padding_right", "0.5em")
    return rx.box(
        *children,
        overflow_x="auto",
        width="100%",
        box_sizing="border-box",
        # Imprescindible: este contenedor es hijo de un rx.flex (o de
        # un grid), y por defecto un hijo de flex/grid tiene
        # min-width: auto -- no se encoge por debajo del ancho de su
        # contenido aunque se le diga width="100%". Sin este min_width
        # a 0, `overflow_x="auto"` nunca llega a activarse: la tabla
        # simplemente desborda el contenedor y la corta el elemento de
        # más arriba, sin barra de scroll visible. Con min_width="0" el
        # contenedor SÍ se encoge al 100% del padre y el scroll
        # aparece cuando hace falta.
        min_width="0",
        **props,
    )
