"""
uploader_bd.py
Responsabilidad: tomar el DataFrame resultado del barrido e insertarlo
de forma acumulativa en la tabla dbo.Barrido_quoted (SQL Server).
"""

import logging

import pandas as pd
import pyodbc

logger = logging.getLogger(__name__)

INSERT_SQL = (
    "INSERT INTO {tabla} (Reserva, QUOTED_RATE, Rate, Currency, Fecha_Consulta) "
    "VALUES (?, ?, ?, ?, ?)"
)


def _construir_conn_str(db_cfg: dict) -> str:
    """Construye la cadena de conexion ODBC para la BD de barrido."""
    return (
        "DRIVER={{{driver}}};"
        "SERVER={server};"
        "DATABASE={database};"
        "UID={usernameDB};"
        "PWD={passwordDB}"
    ).format(**db_cfg)


def subir_barrido(cfg: dict, df: pd.DataFrame) -> int:
    """
    Inserta todos los registros del DataFrame en dbo.Barrido_quoted.
    La insercion es acumulativa: no trunca ni elimina datos previos.

    Parametros:
        cfg : dict completo de config.json
        df  : DataFrame con columnas Reserva, QUOTED_RATE, Rate, Currency, Fecha_Consulta

    Retorna:
        Numero de filas insertadas.
    """
    db_cfg = cfg["db_barrido"]
    tabla  = db_cfg["table"]

    logger.info(
        "Conectando a BD de destino (%s / %s)...",
        db_cfg["server"], db_cfg["database"],
    )

    try:
        conn   = pyodbc.connect(_construir_conn_str(db_cfg))
        cursor = conn.cursor()
    except Exception as e:
        logger.error("Error al conectar con la BD de destino: %s", e)
        raise

    sql = INSERT_SQL.format(tabla=tabla)

    def _val(v):
        """
        Convierte un valor del DataFrame a algo seguro para pyodbc.
        - None o string vacio  → None  (pyodbc envia NULL; compatible con cualquier tipo de columna)
        - Cualquier otro valor → str   (el driver ODBC hace el cast al tipo real de la columna)
        """
        if v is None:
            return None
        s = str(v).strip()
        return None if s == "" else s

    registros = [
        (
            _val(row["Reserva"]),
            _val(row["QUOTED_RATE"]),
            _val(row["Rate"]),
            _val(row["Currency"]),
            str(row["Fecha_Consulta"]),   # siempre presente, formato YYYY-MM-DD
        )
        for _, row in df.iterrows()
    ]

    try:
        cursor.fast_executemany = True
        cursor.executemany(sql, registros)
        conn.commit()
        filas = len(registros)
        logger.info(
            "Insercion completada: %d filas insertadas en %s.", filas, tabla
        )
    except Exception as e:
        conn.rollback()
        logger.error("Error al insertar en BD, se hizo rollback: %s", e)
        raise
    finally:
        cursor.close()
        conn.close()

    return filas
