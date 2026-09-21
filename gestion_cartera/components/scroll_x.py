"""Envoltorio para contenido ancho (normalmente una `rx.table.root` con
muchas columnas): en pantallas estrechas, en vez de comprimirse hasta
ser ilegible o romper el layout de la página, el contenido se puede
desplazar horizontalmente dentro de su propio contenedor.

Con `vertical=True`, además limita su propia altura y scrollea también
en vertical -- imprescindible para que una cabecera de tabla "sticky"
(ver `styles.STICKY_TABLE_HEADER`) tenga de verdad un scroll al que
pegarse.

OJO -- IMPORTANTE: `rx.table.root` (Radix `Table.Root`) trae por
defecto su PROPIO contenedor interno con `overflow-x: auto` para el
scroll horizontal. Si dejamos que ese contenedor de Radix conviva con
el nuestro, hay DOS ancestros con overflow no-visible entre la
cabecera `sticky` y el viewport, y `position: sticky` se "pega" al más
cercano (el de Radix) -- que no es el que realmente scrollea en
vertical (nunca tiene su altura acotada), así que la cabecera no se
queda fija: se comporta como una fila más. Se comprobó exactamente
este comportamiento. Por eso, siempre que se envuelve una
`rx.table.root` con `scroll_x`, hay que anular el contenedor propio de
Radix pasándole `overflow="visible"` como prop -- así el ÚNICO
contenedor con scroll real que queda es el de `scroll_x`."""

import reflex as rx


def scroll_x(*children: rx.Component, vertical: bool = False, **props) -> rx.Component:
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

    if vertical:
        props.setdefault("max_height", "75vh")
        props["overflow_y"] = "auto"

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
