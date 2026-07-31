"""
config_loader.py
Responsabilidad: cargar y validar el archivo config.json.
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

# Claves requeridas por seccion
REQUIRED_KEYS = {
    "database": ["server", "dbname", "user", "password", "driver"],
    "db_barrido": ["driver", "server", "database", "usernameDB", "passwordDB", "table"],
    "mailAppPass": ["sender", "receiver", "passwordMail"],
    "automatizacion": [
        "days_back",
        "min_reservas",
        "espera_min_reservas_seg",
        "reintentos_min_reservas",
        "reintentos_terminal",
        "espera_terminal_seg",
    ],
}


def cargar_config(config_path: str) -> dict:
    """
    Carga config.json y valida que existan todas las claves requeridas.
    Lanza FileNotFoundError si no existe el archivo.
    Lanza KeyError si faltan claves obligatorias.
    """
    logger.info("Cargando configuracion desde: %s", config_path)

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            "No se encontro el archivo de configuracion: {}".format(config_path)
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    for seccion, claves in REQUIRED_KEYS.items():
        if seccion not in config:
            raise KeyError(
                "Falta la seccion '{}' en config.json".format(seccion)
            )
        for clave in claves:
            if clave not in config[seccion]:
                raise KeyError(
                    "Falta la clave '{}' en la seccion '{}' de config.json".format(
                        clave, seccion
                    )
                )

    logger.info("Configuracion cargada y validada correctamente.")
    return config
