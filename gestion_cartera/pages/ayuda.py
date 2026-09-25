"""Página AYUDA (/ayuda): explica en términos contables/aritméticos (no
de programación) qué efecto tiene cada tipo de operación, cómo se
calcula el coste FIFO, la rentabilidad (TIR) y el resumen de IRPF.

Página estática -- sin estado propio ni `on_load` de datos: todo el
contenido es texto fijo, agrupado por temas en un `rx.accordion` para
que se pueda consultar sin tener que leer de un tirón. Igual que
Brókers/Usuarios, no lleva el selector de cartera del header (no
trabaja sobre ninguna cartera en concreto).
"""

import reflex as rx

from gestion_cartera.components.auth_guard import requiere_login
from gestion_cartera.components.header import header
from gestion_cartera.components.page_title import page_title
from gestion_cartera.styles import SPACE_LG, SPACE_SM

# Cada sección es (título, [(pregunta/tema, [párrafos...]), ...]).
# Los párrafos se renderizan tal cual, uno debajo de otro, dentro del
# contenido desplegable de cada entrada del acordeón -- así el texto
# de abajo se escribe como una lista de strings normal y corriente, sin
# tener que construir cada rx.text a mano.
_SECCIONES: list[tuple[str, list[tuple[str, list[str]]]]] = [
    (
        "Conceptos generales",
        [
            (
                "¿Qué es una «operación» y cómo se reconstruye la cartera?",
                [
                    "Cada movimiento que registras (una compra, una venta, un dividendo "
                    "cobrado, un split de la empresa...) se guarda como una fila suelta: "
                    "fecha, valor, bróker, tipo de operación y los datos propios de ese "
                    "tipo (títulos, importe, retenciones...). La app nunca guarda «la "
                    "cartera» como una foto fija: la recalcula cada vez recorriendo, en "
                    "orden cronológico, TODAS las operaciones de ese valor desde el "
                    "principio.",
                    "Por eso el orden de las fechas importa mucho. Y cuando dos "
                    "operaciones caen el mismo día, se procesan siempre en un orden fijo "
                    "para que el resultado no dependa de en qué orden las tecleaste: "
                    "primero Dividendo/Prima (se calculan sobre la posición tal y como "
                    "estaba antes de cualquier operación corporativa de ese día), luego "
                    "Split/Contrasplit/Spinoff (reescalan o reparten lo que ya había), "
                    "después una Venta (consume lo que ya está reescalado) y por último "
                    "Compra/Script (los títulos que entran ese mismo día no se venden a "
                    "sí mismos).",
                ],
            ),
            (
                "Cartera de Largo Plazo y de Corto Plazo",
                [
                    "Cada usuario tiene dos carteras independientes entre sí: Largo Plazo "
                    "y Corto Plazo. Todos los cálculos de tenencias, coste, plusvalía, TIR "
                    "y Radar trabajan siempre sobre UNA sola cartera a la vez (la que "
                    "tengas seleccionada arriba).",
                    "La única excepción es la página IRPF, que combina SIEMPRE las dos "
                    "carteras: de cara a Hacienda da igual en qué cartera interna esté "
                    "cada valor, el resultado fiscal es uno solo.",
                ],
            ),
            (
                "El bróker: saldo por bróker frente a coste agregado",
                [
                    "El coste medio, la plusvalía y la TIR de un valor se calculan "
                    "SIEMPRE agregando todos los brókers donde lo tengas depositado, "
                    "dentro de una misma cartera. El bróker concreto de cada operación "
                    "solo se usa para dos cosas: controlar que nunca vendas más títulos "
                    "de los que ese bróker en concreto tiene depositados (no puedes "
                    "vender en un bróker títulos que están depositados en otro), y para "
                    "repartir el coste de un Spinoff (que necesita saber cuánto coste "
                    "tienes en la matriz en ESE bróker concreto).",
                ],
            ),
        ],
    ),
    (
        "Tipos de operación: qué efecto tiene cada una",
        [
            (
                "Compra",
                [
                    "Títulos comprados + importe total pagado. El coste unitario del "
                    "lote nuevo es importe ÷ títulos. No consume nada de lo que ya "
                    "tenías: simplemente añade un lote nuevo a la cola (ver «Coste medio "
                    "y FIFO» más abajo).",
                    "La tabla de valores (empresa, mercado, zona, moneda y "
                    "supersector/sector/grupo) es un catálogo COMPARTIDO por todos los "
                    "usuarios y todas las carteras, no algo propio de cada uno. Si al "
                    "comprar un valor que todavía no existe en el catálogo lo das de "
                    "alta tú, la clasificación que elijas (sobre todo el "
                    "supersector/sector/grupo, que es lo que luego usa Radar para el "
                    "objetivo de balance) la va a heredar cualquier otro usuario que "
                    "compre ese mismo valor más adelante — no la vuelve a elegir cada "
                    "uno por su cuenta.",
                    "Por eso conviene clasificarlo bien a la primera: si tienes dudas "
                    "sobre en qué supersector/sector encaja una empresa, o sospechas que "
                    "ya podría estar dada de alta con otro criterio, merece la pena "
                    "consultarlo antes con otro usuario o con el administrador en vez de "
                    "decidirlo a ciegas — corregirlo después implica cambiar la "
                    "clasificación de ese valor para todo el mundo, no solo para tu "
                    "cartera.",
                ],
            ),
            (
                "Venta",
                [
                    "Títulos vendidos + importe recibido. La venta consume títulos de "
                    "los lotes MÁS ANTIGUOS primero (FIFO: «first in, first out»), no del "
                    "coste medio de toda la posición. El coste de la venta es la suma del "
                    "coste unitario de cada lote consumido, y la plusvalía realizada de "
                    "esa venta es importe recibido − ese coste.",
                    "Ejemplo: tienes dos lotes de un mismo valor, uno de 10 títulos "
                    "comprados a 20 €/título (200 € de coste) y otro de 10 títulos "
                    "comprados a 30 €/título (300 € de coste). Vendes 15 títulos por "
                    "450 € en total. La venta consume primero los 10 del lote más "
                    "antiguo (coste 200 €) y luego 5 del segundo lote (coste 150 €): "
                    "coste total consumido 350 €, plusvalía de esta venta 450 − 350 = "
                    "100 €. Te quedan 5 títulos del segundo lote, a 30 €/título.",
                ],
            ),
            (
                "Dividendo",
                [
                    "Importe bruto cobrado, con sus retenciones (en destino y en origen). "
                    "No cambia ni el número de títulos ni el coste de lo que tienes: es "
                    "puro ingreso. Cuenta como un cobro más en la TIR (en su fecha real) "
                    "y como «Dividendo» en el resumen de IRPF.",
                ],
            ),
            (
                "Prima (de asistencia a junta, etc.)",
                [
                    "A diferencia de un Dividendo, una Prima NO se trata como ingreso "
                    "puro: se trata como una devolución parcial de lo que pagaste por las "
                    "acciones. El importe cobrado se reparte a partes iguales entre TODOS "
                    "los títulos que tienes en ese momento, y esa parte se resta del "
                    "coste unitario de cada lote vivo (sin tocar el número de títulos).",
                    "Ejemplo: tienes 10 títulos con un coste total de 300 € (30 €/título). "
                    "Cobras una Prima de 50 €. 50 ÷ 10 = 5 €/título. El coste unitario baja "
                    "a 25 €/título (250 € de coste total), y sigues teniendo 10 títulos. "
                    "No genera plusvalía en el momento; simplemente abarata lo que ya "
                    "tenías y por tanto aumenta la plusvalía latente futura.",
                ],
            ),
            (
                "Script (ampliación de capital liberada / scrip dividend)",
                [
                    "Modela una ampliación de capital liberada en la que recibes derechos "
                    "de asignación gratuita proporcionales a tus títulos. Siempre añade "
                    "títulos nuevos a tu posición, pero se distinguen dos variantes según "
                    "qué hiciste con el derecho, y eso cambia el COSTE con el que entran "
                    "esos títulos nuevos:",
                    "· Derecho comprado (ejerciste/compraste el derecho): los títulos "
                    "nuevos entran con el coste que pagaste por ellos (importe ÷ títulos), "
                    "exactamente igual que una Compra normal.",
                    "· Derecho vendido (vendiste el derecho en vez de ejercerlo): los "
                    "títulos nuevos entran con coste 0, y el importe que cobraste por "
                    "vender el derecho se registra aparte como un ingreso equivalente a "
                    "un Dividendo (así se refleja tanto en la TIR como en el resumen de "
                    "IRPF, donde aparece como «Venta de derechos»).",
                ],
            ),
            (
                "Split y Contrasplit",
                [
                    "Una operación corporativa que cambia el número de títulos sin que "
                    "cambie el valor total de lo que tienes: reescala TODOS los lotes que "
                    "ya poseías, multiplicando sus títulos y dividiendo su coste unitario "
                    "por el mismo factor (el ratio nuevo/antiguo) — así el coste TOTAL de "
                    "cada lote no cambia ni un céntimo, solo entre cuántos títulos se "
                    "reparte.",
                    "Ejemplo (split 1→10, ratio = 10): tenías 5 títulos a 100 €/título "
                    "(500 € en total) → pasas a tener 50 títulos a 10 €/título (500 € en "
                    "total, sin cambios). Un contrasplit funciona igual pero al revés "
                    "(ratio menor que 1): menos títulos, coste unitario más alto, mismo "
                    "coste total.",
                    "Solo tienes que decir cuántos títulos antiguos equivalen a cuántos "
                    "títulos nuevos (p. ej. «1 antiguo → 10 nuevos»): la app calcula el "
                    "ratio ella sola y, a partir de tu saldo actual en ese bróker, cuántos "
                    "títulos te deberían quedar en total.",
                    "Si el resultado no sale un número entero de títulos, hay que decir "
                    "qué pasó con la fracción sobrante, con tres opciones: «sin ajuste» "
                    "(la fracción se pierde o se gana gratis, sin más efecto); «cobrada en "
                    "efectivo» (el bróker te pagó esa fracción — se trata como una VENTA "
                    "real de esos títulos sobrantes, con su propia plusvalía FIFO, sujeta "
                    "a IRPF); o «completada a entero» (el bróker completó la fracción "
                    "hasta el título entero, cobrándote o no un importe — se trata como "
                    "una COMPRA de esa fracción).",
                ],
            ),
            (
                "Spinoff (escisión)",
                [
                    "Cuando una empresa «matriz» separa parte de su negocio en una "
                    "empresa «filial» (nueva o ya existente en tu catálogo) y te entrega "
                    "acciones de la filial en proporción a las que ya tenías de la "
                    "matriz. Tiene efecto en las DOS empresas a la vez:",
                    "· En la matriz: el número de títulos NO cambia. Lo que cambia es el "
                    "coste — una parte de lo que pagaste por la matriz se traslada a la "
                    "filial, porque ahora una parte de ese negocio ya no es de la matriz. "
                    "Tú indicas qué % del coste se QUEDA en la matriz; el resto es lo que "
                    "se transfiere a la filial.",
                    "· En la filial: recibes títulos nuevos, con el coste transferido "
                    "desde la matriz. Ese coste se calcula automáticamente a partir de lo "
                    "que tenías invertido en la matriz, EN ESE BRÓKER concreto (por eso "
                    "conviene dar de alta el Spinoff bróker por bróker si el valor lo "
                    "tienes repartido en varios).",
                    "Igual que en Split/Contrasplit, si el ratio de reparto de títulos "
                    "deja una fracción, se trata con las mismas tres opciones: sin "
                    "ajuste, cobrada en efectivo (venta real de esa fracción) o "
                    "completada a entero (compra de esa fracción).",
                    "Ejemplo: tenías 100 títulos de la matriz con un coste total de "
                    "4.000 € (40 €/título). El spinoff reparte 1 título de filial por "
                    "cada 4 de matriz, y decides que la matriz se queda el 80 % del "
                    "coste. Coste que se queda en la matriz: 4.000 × 0,80 = 3.200 € "
                    "(sigues con 100 títulos, ahora a 32 €/título). Coste que pasa a la "
                    "filial: 4.000 × 0,20 = 800 €, repartido entre 100 ÷ 4 = 25 títulos "
                    "nuevos de filial → 32 €/título de filial (en este ejemplo coincide "
                    "con el de la matriz, pero es casualidad: depende del % que elijas).",
                ],
            ),
        ],
    ),
    (
        "Edición y eliminación de operaciones",
        [
            (
                "Qué se puede cambiar al editar una operación",
                [
                    "Al editar una operación ya registrada puedes corregir la fecha, "
                    "el bróker, los títulos, el importe, las retenciones y las "
                    "observaciones. Lo único que NO se puede cambiar desde ahí es el "
                    "TIPO de operación y el VALOR (la empresa): si te equivocaste en "
                    "cualquiera de los dos al darla de alta, hay que eliminar esa "
                    "operación y volver a darla de alta desde cero con los datos "
                    "correctos.",
                    "Split/Contrasplit tiene un modo de edición algo más guiado: puedes "
                    "ajustar directamente el ratio y cómo se trató la fracción, tal y "
                    "como quedaron guardados al darla de alta. Spinoff, de momento, "
                    "solo se puede editar «en crudo» (los mismos campos que se "
                    "guardaron, sin repetir el asistente de cálculo automático) — si "
                    "hay que corregir algo importante de un Spinoff, normalmente es más "
                    "sencillo eliminar sus filas (matriz y filial) y volver a darlo de "
                    "alta con el asistente.",
                ],
            ),
            (
                "Validación de saldo al editar o eliminar",
                [
                    "Cualquier cambio que afecte al nº de títulos o al bróker de una "
                    "Compra, Venta, Script, Split/Contrasplit o Spinoff hace que la app "
                    "recalcule TODA la línea temporal de saldo de ese valor en ese "
                    "bróker — no solo en la fecha de esta operación, también las "
                    "posteriores — para comprobar que nunca queda en negativo en ningún "
                    "momento.",
                    "Si el cambio deja sin saldo suficiente a alguna operación "
                    "POSTERIOR que hasta ahora encajaba (por ejemplo, reducir una "
                    "Compra de la que una Venta futura ya disponía), el guardado se "
                    "bloquea y se indica la fecha y el tipo de esa operación en "
                    "conflicto: hay que editar o eliminar primero esa operación "
                    "posterior.",
                    "Al eliminar rige la misma lógica: borrar una Compra, Script, "
                    "Split o Spinoff puede dejar sin saldo suficiente a una operación "
                    "posterior que dependía de esos títulos, y se bloquea igual. Borrar "
                    "una Venta o un Contrasplit, en cambio, nunca se bloquea — quitarlas "
                    "solo LIBERA saldo hacia delante, nunca lo reduce.",
                ],
            ),
        ],
    ),
    (
        "Coste y rentabilidad",
        [
            (
                "Coste medio y FIFO: por qué la plusvalía depende de qué compra se vende",
                [
                    "A diferencia de un coste medio ponderado único (donde toda la "
                    "posición se valora siempre al mismo precio medio, sin importar el "
                    "orden de compra), esta app recuerda cada compra como un «lote» "
                    "independiente — títulos y coste unitario — y, al vender, consume "
                    "primero los lotes más antiguos (FIFO).",
                    "Esto significa que la plusvalía de una venta concreta depende de "
                    "QUÉ compras se están liquidando en ese momento, no de una media de "
                    "toda tu posición histórica. El «precio medio» que ves en pantalla "
                    "(Cartera, detalle de Valor) es el coste de los lotes que TODAVÍA "
                    "tienes, dividido entre los títulos que todavía tienes — nunca "
                    "incluye lotes ya vendidos del todo.",
                ],
            ),
            (
                "TIR (rentabilidad anual, con y sin revalorización)",
                [
                    "La TIR que se muestra es una rentabilidad anual «money-weighted» "
                    "(tiene en cuenta CUÁNDO entró o salió cada euro, no solo cuánto): "
                    "cada operación aporta su movimiento de caja real, en su fecha real "
                    "— Compra y derecho comprado (Script) como salida de dinero; Venta, "
                    "Prima, Dividendo y derecho vendido (Script) como entrada de dinero "
                    "— y se añade un último flujo, a fecha de hoy, con el valor de lo "
                    "que tienes ahora.",
                    "Se calculan dos TIR distintas, según qué se use como ese último "
                    "flujo: «con revalorización» usa el valor de MERCADO actual (refleja "
                    "también si la cotización ha subido o bajado); «sin revalorización» "
                    "usa el valor de COMPRA actual, como si la cotización no se hubiera "
                    "movido — así se aísla el efecto puro de cuándo cobraste o pagaste "
                    "cada cosa, sin el efecto de la subida o bajada de precio.",
                    "Siempre se calcula en BRUTO, sin descontar retenciones: las "
                    "retenciones no son dinero perdido de verdad (normalmente se "
                    "recuperan o compensan en la declaración), así que no restan de "
                    "ningún flujo de caja.",
                ],
            ),
        ],
    ),
    (
        "Declaración de la renta (IRPF)",
        [
            (
                "Dividendos y venta de derechos",
                [
                    "Para cada Dividendo o Script «venta de derechos» del año "
                    "seleccionado, se muestran: el importe BRUTO cobrado; la retención "
                    "en destino (la de tu bróker/país de residencia); y la retención en "
                    "origen (la retenida en el país donde cotiza el valor), desglosada en "
                    "dos partes.",
                    "Ese desglose existe porque, normalmente, solo hasta el 15 % del "
                    "bruto cobrado es acreditable en la declaración sin trámite aparte: "
                    "la app calcula automáticamente la parte «hasta el 15 %» (el menor "
                    "entre la retención en origen real y el 15 % del bruto) y el «exceso "
                    "sobre el 15 %» (el resto), y agrupa ese exceso por zona/mercado en "
                    "una tabla aparte, para que compruebes de un vistazo cuánto se pierde "
                    "o hay que reclamar aparte por cada país o mercado.",
                ],
            ),
            (
                "Ventas: plusvalías por lotes FIFO",
                [
                    "Cada Venta del año seleccionado (incluida la fracción cobrada en "
                    "efectivo de un Split/Contrasplit/Spinoff) se lista con su plusvalía "
                    "FIFO ya calculada: importe recibido menos el coste de los lotes que "
                    "consumió esa venta en concreto. Para que ese coste sea correcto, la "
                    "app reconstruye el histórico COMPLETO del valor desde el principio, "
                    "no solo las operaciones del año seleccionado.",
                    "Importante: si una fracción de Split/Contrasplit se cobró en "
                    "efectivo y llevaba retención, esa retención se muestra en su propia "
                    "fila del listado de ventas, pero A PROPÓSITO no se suma a los "
                    "totales de retención de la sección de dividendos — en la "
                    "declaración, la retención de una ganancia patrimonial (una "
                    "transmisión) va en una casilla distinta a la de un rendimiento del "
                    "capital mobiliario (un dividendo). Se deja como dato informativo "
                    "para que la ubiques tú mismo en la casilla correcta.",
                ],
            ),
        ],
    ),
    (
        "Radar",
        [
            (
                "Objetivo de balance: peso actual, objetivo y proyectado",
                [
                    "El Radar trabaja siempre sobre la cartera de Largo Plazo. Defines "
                    "qué % objetivo quieres tener en cada supersector y en cada zona "
                    "geográfica (el total de cada grupo debe sumar 100).",
                    "El peso ACTUAL de cada categoría se calcula como el valor de "
                    "mercado de lo que tienes en esa categoría, dividido entre el valor "
                    "de mercado total de la cartera. El peso PROYECTADO añade, a lo que "
                    "ya tienes, el importe que tienes previsto invertir en cada fila de "
                    "tu lista de posibles compras — así puedes ver, antes de ejecutar "
                    "nada, si esas compras te acercan o te alejan del objetivo en cada "
                    "categoría.",
                ],
            ),
            (
                "Sistema de alertas por SMS",
                [
                    "Cada fila de la lista de posibles compras (Largo Plazo o Corto "
                    "Plazo) admite un precio de compra y, opcionalmente, un precio de "
                    "venta. La cotización se compara contra esos dos precios y, cuando "
                    "corresponde, se manda un SMS: al número de teléfono que cada "
                    "usuario configura en su propio menú de usuario («Número de "
                    "teléfono (avisos SMS)»), en formato internacional. Si no has "
                    "guardado ningún número, simplemente no recibes avisos.",
                    "Aviso de COMPRA: la fila se pinta en rojo en cuanto la cotización "
                    "cae hasta el precio de compra fijado o por debajo, y ahí se manda "
                    "el SMS. Se pinta en ámbar cuando está hasta un 10 % por encima del "
                    "precio de compra (aviso visual, sin SMS). Aviso de VENTA: es "
                    "independiente del color de la fila — se manda un SMS en cuanto la "
                    "cotización alcanza o supera el precio de venta que hayas puesto.",
                    "Cada aviso se manda UNA sola vez mientras se mantenga la "
                    "condición: en cuanto la cotización sale de esa zona (deja de estar "
                    "en rojo, o vuelve a caer por debajo del precio de venta) el aviso "
                    "se «rearma», y si la condición se vuelve a cumplir más adelante se "
                    "manda un SMS nuevo.",
                    "La cotización se refresca, y los avisos se revisan, de dos formas: "
                    "cada vez que alguien tiene la página Radar abierta (al cargarla, o "
                    "al dar de alta un candidato nuevo), y también automáticamente en "
                    "segundo plano — una vez por hora, de lunes a viernes entre las "
                    "9:20 y las 22:20 (hora de Madrid) — sin que nadie necesite tener la "
                    "app abierta en ese momento.",
                ],
            ),
        ],
    ),
]


def _entrada(pregunta: str, parrafos: list[str]) -> rx.accordion.item:
    return rx.accordion.item(
        header=pregunta,
        content=rx.flex(
            *[rx.text(p, size="2", color_scheme="gray") for p in parrafos],
            direction="column",
            spacing="2",
            padding_bottom=SPACE_SM,
        ),
    )


def _seccion(titulo: str, entradas: list[tuple[str, list[str]]]) -> rx.Component:
    return rx.flex(
        rx.heading(titulo, size="4"),
        rx.accordion.root(
            *[_entrada(pregunta, parrafos) for pregunta, parrafos in entradas],
            type="multiple",
            collapsible=True,
            width="100%",
            variant="surface",
        ),
        direction="column",
        spacing="3",
        width="100%",
    )


def pagina_ayuda() -> rx.Component:
    return rx.container(
        header(),
        rx.flex(
            page_title(
                "Ayuda",
                "Qué efecto tiene cada operación, cómo se calcula el coste, la "
                "rentabilidad y el resumen de IRPF -- en términos contables, no de "
                "programación.",
            ),
            *[_seccion(titulo, entradas) for titulo, entradas in _SECCIONES],
            direction="column",
            spacing="6",
            padding="1em",
            padding_top=SPACE_LG,
        ),
        size="4",
    )


def ayuda() -> rx.Component:
    return requiere_login(pagina_ayuda())
