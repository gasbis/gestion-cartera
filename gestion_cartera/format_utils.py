"""Formateo de números al estilo español: punto (.) como separador de
miles, coma (,) como separador decimal -- p.ej. 1.234,56.

Centralizado aquí porque se necesita en varios sitios (cartera_db.py,
operaciones_db.py, los estados de alta/edición de operaciones...) y así
se formatea igual en toda la app en vez de repetir el mismo intercambio
de separadores en cada sitio.
"""


def formatear_numero(valor: float, decimales: int = 2) -> str:
    """1234.5 -> '1.234,50' (con `decimales` decimales, agrupando miles)."""
    # f"{valor:,.2f}" da el formato "en inglés" (1,234.50); se intercambian
    # los separadores con un carácter provisional para no pisarse.
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "�").replace(".", ",").replace("�", ".")


def formatear_eur(valor: float, decimales: int = 2) -> str:
    return f"{formatear_numero(valor, decimales)} €"


def formatear_pct(valor: float, decimales: int = 2) -> str:
    return f"{formatear_numero(valor, decimales)} %"


def formatear_titulos(valor: float) -> str:
    """Nº de títulos: sin decimales si es un número entero (lo habitual),
    con hasta 4 si no lo es (derechos fraccionados, script...)."""
    if valor == int(valor):
        return formatear_numero(valor, 0)
    return formatear_numero(valor, 4).rstrip("0").rstrip(",")
