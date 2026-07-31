"""
barrido_auto.py
Orquestador principal del proceso automatizado de Barrido Quoted Rate.

Flujo:
  1. Cargar configuracion (config.json)
  2. Extraer reservas desde SQL Server (con validacion de minimo y reintentos)
  3. Ejecutar barrido en Wizard/BlueZone (con manejo de desconexion)
  4. Subir resultado a dbo.Barrido_quoted (INSERT acumulativo)
  5. Notificar resultado por correo

Ejecucion prevista:
  "C:\\Python310-32\\python.exe" "ruta\\barrido_auto.py"

Programador de Windows: ejecutar todos los dias.
Salida redirigida a barrido.log automaticamente via RotatingFileHandler.
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

# ============================================================
# RUTAS BASE
# ============================================================

# Rutas base — compatible con ejecucion como script y como exe compilado.
# PyInstaller --onefile extrae a _MEI*, pero sys.executable apunta al exe real.
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SQL_PATH    = os.path.join(BASE_DIR, "Consultas", "WkSQLQuery.sql")
LOG_PATH    = os.path.join(BASE_DIR, "barrido.log")

# Asegurar que el directorio del proyecto este en el path
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


# ============================================================
# CONFIGURACION DE LOGGING
# ============================================================

def _configurar_logging() -> None:
    """
    Configura logging con salida a archivo rotativo y a consola.
    El archivo barrido.log rota al llegar a 5 MB, conservando 5 backups.
    """
    fmt      = "%(asctime)s [%(levelname)-8s] %(name)s - %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    handler_archivo = RotatingFileHandler(
        LOG_PATH,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler_archivo.setFormatter(logging.Formatter(fmt, datefmt=date_fmt))

    handler_consola = logging.StreamHandler(sys.stdout)
    handler_consola.setFormatter(logging.Formatter(fmt, datefmt=date_fmt))

    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler_archivo, handler_consola],
    )


# ============================================================
# IMPORTACION DE MODULOS (despues de configurar el path)
# ============================================================

from modulos.config_loader import cargar_config
from modulos import notificador
from modulos import extractor_sql
from modulos import barrido_wizard
from modulos import uploader_bd

logger = logging.getLogger(__name__)


# ============================================================
# FLUJO PRINCIPAL
# ============================================================

def main() -> None:
    _configurar_logging()

    inicio = datetime.now()
    separador = "=" * 65

    logger.info(separador)
    logger.info(
        "INICIO DEL BARRIDO AUTOMATICO - %s",
        inicio.strftime("%Y-%m-%d %H:%M:%S"),
    )
    logger.info(separador)

    # ----------------------------------------------------------
    # PASO 1: Cargar configuracion
    # ----------------------------------------------------------
    try:
        cfg = cargar_config(CONFIG_PATH)
    except Exception as e:
        logger.critical("No se pudo cargar la configuracion: %s", e)
        sys.exit(1)

    # ----------------------------------------------------------
    # PASO 2: Extraer reservas desde SQL Server
    # ----------------------------------------------------------
    logger.info("--- PASO 1/3: Extraccion de reservas desde SQL Server ---")
    try:
        df_reservas = extractor_sql.extraer_reservas(
            cfg, SQL_PATH, notificador=notificador
        )
    except ValueError as e:
        # Minimo de reservas no alcanzado tras reintentos (correo ya enviado)
        logger.critical("Proceso abortado: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.critical("Fallo inesperado en extraccion SQL: %s", e)
        notificador.enviar_correo(
            cfg,
            "[Barrido Automatico] Error en extraccion SQL",
            (
                "El proceso fue abortado durante la extraccion de datos.\n\n"
                "Detalle del error: {}\n\n"
                "Favor revisar la conexion con SQL Server."
            ).format(e),
        )
        sys.exit(1)

    # ----------------------------------------------------------
    # PASO 3: Ejecutar barrido en Wizard/BlueZone
    # ----------------------------------------------------------
    logger.info("--- PASO 2/3: Barrido en Wizard/BlueZone ---")
    try:
        df_resultado = barrido_wizard.ejecutar_barrido(
            df_reservas, cfg, notificador=notificador
        )
    except ConnectionError as e:
        # La terminal no pudo reconectarse (correo ya enviado)
        logger.critical("Proceso abortado por desconexion de terminal: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.critical("Fallo inesperado en el barrido Wizard: %s", e)
        notificador.enviar_correo(
            cfg,
            "[Barrido Automatico] Error en barrido Wizard",
            (
                "El proceso fallo durante el barrido de reservas.\n\n"
                "Detalle del error: {}\n\n"
                "Favor revisar BlueZone y el log: {}"
            ).format(e, LOG_PATH),
        )
        sys.exit(1)

    # ----------------------------------------------------------
    # PASO 4: Subir resultado a dbo.Barrido_quoted
    # ----------------------------------------------------------
    modo_prueba = cfg["automatizacion"].get("prueba", False)

    if modo_prueba:
        logger.warning("*** MODO PRUEBA ACTIVO: la subida a la BD fue omitida. ***")
        logger.warning("*** Para produccion, cambia 'prueba' a false en config.json. ***")
        filas = 0
    else:
        logger.info("--- PASO 3/3: Subida a base de datos ---")
        try:
            filas = uploader_bd.subir_barrido(cfg, df_resultado)
        except Exception as e:
            logger.critical("Fallo al subir datos a la BD: %s", e)
            notificador.enviar_correo(
                cfg,
                "[Barrido Automatico] Error al subir a BD",
                (
                    "El barrido se completo pero no pudo subirse a la base de datos.\n\n"
                    "Reservas procesadas : {}\n"
                    "Detalle del error   : {}\n\n"
                    "Favor revisar la conexion con SQL Server de destino."
                ).format(len(df_resultado), e),
            )
            sys.exit(1)

    # ----------------------------------------------------------
    # PASO 5: Notificacion de exito
    # ----------------------------------------------------------
    fin      = datetime.now()
    duracion = str(fin - inicio).split(".")[0]
    fecha_consulta = datetime.today().strftime("%Y-%m-%d")

    # Dia de ejecucion y days_back usado (leido igual que en extractor_sql)
    dia_hoy   = str(inicio.weekday())
    days_back_usado = int(
        cfg["automatizacion"].get("days_back_por_dia", {}).get(
            dia_hoy, cfg["automatizacion"]["days_back"]
        )
    )
    dia_nombre = inicio.strftime("%A %d/%m/%Y")   # ej. "Thursday 03/07/2026"

    aviso_prueba = (
        "\n\n*** MODO PRUEBA: los datos NO fueron subidos a la base de datos. ***\n"
        "Cambia 'prueba' a false en config.json para produccion."
        if modo_prueba else ""
    )

    resumen = (
        "El barrido automatico se completo exitosamente.{aviso}\n\n"
        "Dia de ejecucion   : {dia}\n"
        "Dias consultados   : -{days_back} dia(s) hacia atras\n"
        "Fecha de consulta  : {fecha}\n"
        "Reservas procesadas: {procesadas}\n"
        "Filas insertadas   : {filas}\n"
        "Duracion total     : {duracion}"
    ).format(
        aviso=aviso_prueba,
        dia=dia_nombre,
        days_back=days_back_usado,
        fecha=fecha_consulta,
        procesadas=len(df_resultado),
        filas=filas if not modo_prueba else "0 (modo prueba)",
        duracion=duracion,
    )

    logger.info(resumen)
    notificador.enviar_correo(
        cfg,
        "[Barrido Automatico] Proceso completado exitosamente",
        resumen,
    )

    logger.info(separador)
    logger.info("BARRIDO FINALIZADO - %s", fin.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info(separador)


# ============================================================
# PUNTO DE ENTRADA
# ============================================================

if __name__ == "__main__":
    main()
