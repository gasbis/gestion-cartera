"""Texto emergente que funciona igual con ratón que en pantalla táctil.

`rx.tooltip` (Radix Tooltip) y el atributo HTML `title` solo se abren al
pasar el ratón: Radix ignora a propósito los eventos táctiles en el
tooltip y los navegadores móviles no muestran nunca el `title`. Por eso
en el móvil no había forma de ver, p. ej., el desglose de «Otros» en la
leyenda del donut o la cotización en euros del RADAR.

Aquí se pinta el mismo disparador dos veces y el CSS (assets/theme.css,
clases `solo-raton` / `solo-tactil`) deja visible solo uno según el
dispositivo:

  - Con ratón (`hover: hover` y `pointer: fine`): `rx.tooltip`, que se
    abre al pasar por encima, como hasta ahora.
  - En táctil: `rx.popover`, que se abre al tocar y se cierra al tocar
    fuera.

No se anida un componente dentro del otro porque los dos `Trigger` de
Radix usan `asChild` y el del exterior acabaría aplicando sus eventos al
contenido del interior, no al elemento que se toca.
"""

from typing import Callable

import reflex as rx


def ayuda_emergente(
    disparador: Callable[[], rx.Component],
    contenido: rx.Var | str,
    display: str = "inline-flex",
) -> rx.Component:
    """`disparador` es una función (no un componente ya creado) porque
    hacen falta dos copias independientes del mismo elemento: una por
    cada variante."""
    return rx.fragment(
        rx.tooltip(
            rx.box(disparador(), class_name="solo-raton", display=display, align_items="center"),
            content=contenido,
        ),
        rx.popover.root(
            rx.popover.trigger(
                rx.box(
                    disparador(),
                    class_name="solo-tactil",
                    display=display,
                    align_items="center",
                    cursor="pointer",
                )
            ),
            rx.popover.content(
                rx.text(contenido, size="1"),
                size="1",
                side="top",
                max_width="min(320px, 90vw)",
            ),
        ),
    )
