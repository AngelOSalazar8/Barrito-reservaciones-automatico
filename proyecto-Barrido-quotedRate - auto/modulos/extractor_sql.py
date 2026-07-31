"""
extractor_sql.py
Responsabilidad: conectar a SQL Server, ejecutar la consulta parametrizada
con days_back, validar el minimo de registros y retornar un DataFrame.
No genera ningun archivo CSV intermedio.
"""

import logging
import time
from datetime import datetime

import pandas as pd
import pyodbc

logger = logging.getLogger(__name__)


def _construir_conn_str(db_cfg: dict, timeout: int = 30) -> str:
    """Construye la cadena de conexion ODBC para SQL Server."""
    return (
        "DRIVER={{{driver}}};"
        "SERVER={server};"
        "DATABASE={dbname};"
        "UID={user};"
        "PWD={password};"
        f"Connection Timeout={timeout}"
    ).format(**db_cfg)


def extraer_reservas(cfg: dict, sql_path: str, notificador=None) -> pd.DataFrame:
    """
    Ejecuta la consulta SQL con el valor de days_back del config.
    Valida que el resultado tenga al menos min_reservas registros.
    Si no, espera y reintenta hasta reintentos_min_reservas veces.
    Si agota los reintentos, envia correo y lanza ValueError.

    Parametros:
        cfg          : dict completo de config.json
        sql_path     : ruta absoluta al archivo WkSQLQuery.sql
        notificador  : modulo notificador (opcional, para enviar correo en error)

    Retorna:
        DataFrame con las reservas extraidas.
    """
    auto         = cfg["automatizacion"]
    min_reservas = auto["min_reservas"]
    espera       = auto["espera_min_reservas_seg"]
    reintentos   = auto["reintentos_min_reservas"]

    # Determinar days_back segun el dia de la semana si existe la clave days_back_por_dia.
    # Claves: "0"=Lunes, "1"=Martes, ..., "4"=Viernes (weekday() de Python).
    # Si el dia actual no esta en el mapa o la clave no existe, usa days_back como fallback.
    dia_hoy   = str(datetime.today().weekday())
    days_back = int(
        auto.get("days_back_por_dia", {}).get(dia_hoy, auto["days_back"])
    )

    logger.info(
        "Dia de la semana: %s | days_back determinado: %d",
        datetime.today().strftime("%A"), days_back
    )

    reintentos_conn  = auto.get("reintentos_conn_sql", 3)
    espera_conn      = auto.get("espera_conn_sql_seg", 120)
    conn_timeout     = auto.get("conn_timeout_seg", 60)

    conn_str = _construir_conn_str(cfg["database"], timeout=conn_timeout)
    conn     = None

    for conn_intento in range(1, reintentos_conn + 1):
        try:
            logger.info(
                "Conectando a SQL Server... (intento %d/%d)",
                conn_intento, reintentos_conn
            )
            conn = pyodbc.connect(conn_str)
            logger.info("Conexion a SQL Server establecida.")
            break
        except Exception as e:
            if conn_intento < reintentos_conn:
                logger.warning(
                    "Fallo de conexion SQL (intento %d/%d): %s. "
                    "Reintentando en %ds...",
                    conn_intento, reintentos_conn, e, espera_conn
                )
                time.sleep(espera_conn)
            else:
                logger.error(
                    "No se pudo conectar a SQL Server tras %d intentos: %s",
                    reintentos_conn, e
                )
                raise

    with open(sql_path, "r", encoding="utf-8") as f:
        query = f.read().replace("{DAYS_BACK}", str(days_back))

    df = pd.DataFrame()

    for intento in range(1, reintentos + 1):
        logger.info("Ejecutando consulta SQL (intento %d/%d)...", intento, reintentos)

        try:
            df = pd.read_sql_query(query, conn)
        except Exception as e:
            logger.error("Error al ejecutar la consulta SQL: %s", e)
            conn.close()
            raise

        registros = len(df)
        logger.info("Registros encontrados: %d", registros)

        if registros >= min_reservas:
            logger.info(
                "Validacion de minimo OK (%d >= %d).", registros, min_reservas
            )
            break

        if intento < reintentos:
            logger.warning(
                "Solo %d registros (minimo requerido: %d). "
                "Esperando %ds antes del intento %d...",
                registros, min_reservas, espera, intento + 1,
            )
            time.sleep(espera)
        else:
            conn.close()
            msg = (
                "Tras {} intentos, el numero de reservas ({}) "
                "no alcanzo el minimo requerido ({})."
            ).format(reintentos, registros, min_reservas)
            logger.error(msg)

            if notificador:
                notificador.enviar_correo(
                    cfg,
                    "[Barrido Automatico] Pocas reservas detectadas",
                    (
                        "El proceso de Barrido Quoted fue abortado.\n\n"
                        "{}\n\n"
                        "Favor revisar la disponibilidad de datos en SQL Server."
                    ).format(msg),
                )

            raise ValueError(msg)

    # Normalizar columna booleana para compatibilidad
    if "ClienteNacional" in df.columns:
        df["ClienteNacional"] = df["ClienteNacional"].astype(int)

    conn.close()
    logger.info("Extraccion SQL completada. Total de registros: %d", len(df))
    return df
