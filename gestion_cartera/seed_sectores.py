"""Datos y función de siembra para la tabla SECTORES, según la
clasificación de Morningstar (Morningstar Global Equity Classification
Structure): 3 Supersectores, 11 Sectores, 55 Grupos de industria.

Verificado cruzando la documentación oficial de Morningstar Indexes
(indexes.morningstar.com, que confirma "3 Super Sectors, 11 Sectors, 55
Industry Groups, 145 Industries" como estructura vigente) con una tabla
de códigos de grupo de industria "Nov. 2019 - Onward" de fuente
independiente: ambas coinciden exactamente en 55 grupos.

Los nombres de sector/supersector son los oficiales (traducidos). Los
nombres de "grupo" son una traducción propia de los nombres en inglés de
Morningstar, no una cita literal de ningún documento con derechos de
autor — son solo etiquetas de categoría.
"""

import reflex as rx

from gestion_cartera.models import Sector

# supersector -> sector -> [grupos de industria]
TAXONOMIA_MORNINGSTAR: dict[str, dict[str, list[str]]] = {
    "Cíclico": {
        "Materiales Básicos": [
            "Agricultura",
            "Materiales de Construcción",
            "Química",
            "Productos Forestales",
            "Metales y Minería",
            "Acero",
        ],
        "Consumo Cíclico": [
            "Vehículos y Componentes",
            "Mobiliario y Electrodomésticos",
            "Construcción de Viviendas",
            "Fabricación - Textil y Mobiliario",
            "Envases y Embalajes",
            "Servicios Personales",
            "Restauración",
            "Distribución - Cíclica",
            "Viajes y Ocio",
        ],
        "Servicios Financieros": [
            "Gestión de Activos",
            "Banca",
            "Mercados de Capitales",
            "Seguros",
            "Servicios Financieros Diversificados",
            "Servicios de Crédito",
        ],
        "Inmobiliario": [
            "Promoción y Servicios Inmobiliarios",
            "REITs (Fondos de Inversión Inmobiliaria)",
        ],
    },
    "Defensivo": {
        "Consumo Defensivo": [
            "Bebidas Alcohólicas",
            "Bebidas No Alcohólicas",
            "Bienes de Consumo Envasados",
            "Educación",
            "Distribución - Defensiva",
            "Tabaco",
        ],
        "Sanidad": [
            "Biotecnología",
            "Farmacéuticas",
            "Seguros Médicos",
            "Proveedores y Servicios Sanitarios",
            "Dispositivos e Instrumental Médico",
            "Diagnóstico e Investigación Médica",
            "Distribución Médica",
        ],
        "Servicios Públicos": [
            "Eléctricas - Productores Independientes",
            "Eléctricas Reguladas",
        ],
    },
    "Sensible": {
        "Comunicación": [
            "Telecomunicaciones",
            "Medios de Comunicación Diversificados",
            "Medios Interactivos",
        ],
        "Energía": [
            "Petróleo y Gas",
            "Otras Fuentes de Energía",
        ],
        "Industria": [
            "Aeroespacial y Defensa",
            "Servicios Empresariales",
            "Conglomerados",
            "Construcción",
            "Maquinaria Agrícola y de Construcción",
            "Distribución Industrial",
            "Productos Industriales",
            "Transporte",
            "Gestión de Residuos",
        ],
        "Tecnología": [
            "Software",
            "Hardware",
            "Semiconductores",
        ],
    },
}


def seed_sectores() -> int:
    """Inserta en SECTORES los grupos que aún no existan.

    Idempotente: se puede ejecutar varias veces sin duplicar filas
    (comprueba por la combinación supersector+sector+grupo).
    Devuelve el número de filas nuevas insertadas.
    """
    insertados = 0
    with rx.session() as session:
        existentes = {
            (s.supersector, s.sector, s.grupo)
            for s in session.exec(sqlmodel_select_all()).all()
        }
        for supersector, sectores in TAXONOMIA_MORNINGSTAR.items():
            for sector, grupos in sectores.items():
                for grupo in grupos:
                    clave = (supersector, sector, grupo)
                    if clave in existentes:
                        continue
                    session.add(
                        Sector(supersector=supersector, sector=sector, grupo=grupo)
                    )
                    insertados += 1
        session.commit()
    return insertados


def sqlmodel_select_all():
    import sqlmodel

    return sqlmodel.select(Sector)


if __name__ == "__main__":
    # Uso: reflex run debe haber creado ya las tablas (reflex db migrate)
    # antes de ejecutar esto. Luego: python -m gestion_cartera.seed_sectores
    n = seed_sectores()
    print(f"Insertados {n} grupos de industria nuevos.")