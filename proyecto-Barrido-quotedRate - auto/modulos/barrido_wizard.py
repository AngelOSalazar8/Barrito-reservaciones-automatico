"""
barrido_wizard.py
Responsabilidad: ejecutar el barrido de reservas en BlueZone/Wizard via win32com.

Recibe un DataFrame, retorna un DataFrame con la columna Fecha_Consulta.
"""

import logging
import re
import time
from datetime import datetime

import pandas as pd
import win32com.client

logger = logging.getLogger(__name__)


# ============================================================
# UTILIDADES DE CONEXION A LA TERMINAL
# ============================================================

def _verificar_y_reconectar(bzhao, cfg: dict, notificador=None) -> None:
    """
    Verifica si la terminal BlueZone esta conectada.
    Si no lo esta, intenta reconectar llamando bzhao.connect("").
    Reintenta hasta reintentos_terminal veces con espera entre cada intento.
    Si agota los intentos, envia correo y lanza ConnectionError.
    """
    if bzhao.Connected:
        return

    auto       = cfg["automatizacion"]
    reintentos = auto["reintentos_terminal"]
    espera     = auto["espera_terminal_seg"]

    logger.warning("Terminal BlueZone desconectada. Intentando reconectar...")

    for intento in range(1, reintentos + 1):
        try:
            bzhao.connect("")
        except Exception as e:
            logger.warning(
                "Intento %d/%d - Error al llamar connect: %s", intento, reintentos, e
            )

        if bzhao.Connected:
            logger.info("Terminal reconectada exitosamente en el intento %d.", intento)
            return

        logger.warning(
            "Intento %d/%d: terminal no conectada. Esperando %ds...",
            intento, reintentos, espera,
        )
        time.sleep(espera)

    msg = "La terminal BlueZone no pudo reconectarse tras {} intentos.".format(reintentos)
    logger.error(msg)

    if notificador:
        notificador.enviar_correo(
            cfg,
            "[Barrido Automatico] Terminal BlueZone desconectada",
            (
                "El proceso de Barrido Quoted fue abortado.\n\n"
                "{}\n\n"
                "Favor verificar que la sesion de BlueZone/Wizard este abierta "
                "y con conexion activa."
            ).format(msg),
        )

    raise ConnectionError(msg)


# ============================================================
# UTILIDADES DE LECTURA DE PANTALLA
# ============================================================

def _encuentraDatos(bzhao) -> tuple:
    """
    Lee las 25 lineas de la pantalla actual de Wizard y extrae:
      - amt      : Quoted Rate (PER IS / PER=)
      - rate     : Rate Selected
      - currency : Currency

    Retorna: (amt, rate, currency) como strings (vacios si no se encuentran).
    """
    
    patron_rate     = r'RATE SELECTED = (\S+)'
    patron_currency = r'CURRENCY = (\S+)'
    patron_quoted1  = r'PER IS\s+(\S+)'
    patron_quoted2  = r'PER=\s+(\S+)'

    amt      = ''
    rate     = ''
    currency = ''
    texto    = ''

    for j in range(25):
        linea = bzhao.ReadScreen("", 44, 2 + j, 37)[1].strip()
        texto = texto + ' ' + linea

    m = re.search(patron_quoted1, texto)
    if m:
        amt = m.group(1)

    m = re.search(patron_quoted2, texto)
    if m:
        amt = m.group(1)

    m = re.search(patron_rate, texto)
    if m:
        rate = m.group(1)

    m = re.search(patron_currency, texto)
    if m:
        currency = m.group(1)

    return amt, rate, currency


def _validaDatos(amt, rate, currency, amt2, rate2, currency2) -> tuple:
    """
    Consolida los datos de dos lecturas de pantalla.
    Los valores del segundo conjunto tienen prioridad si no estan vacios.
    """
    if amt2 != '':
        amt = amt2
    if rate2 != '':
        rate = rate2
    if currency2 != '':
        currency = currency2
    return amt, rate, currency


# ============================================================
# FUNCION PRINCIPAL DEL BARRIDO
# ============================================================

def ejecutar_barrido(df_reservas: pd.DataFrame, cfg: dict, notificador=None) -> pd.DataFrame:
    """
    Ejecuta el barrido P502 en BlueZone para cada reserva del DataFrame.

    Flujo por reserva:
      1. Verifica conexion de terminal (reconecta si es necesario)
      2. Navega a /for p502
      3. Consulta DR (Display Reservation)
      4. Consulta QR (Quoted Rate)
      5. Si hay pantalla adicional (mod=1), navega a ella
      6. Si hay MORE, presiona PA1 para paginar

    Parametros:
        df_reservas : DataFrame con columna 'Reservation'
        cfg         : dict completo de config.json
        notificador : modulo notificador (opcional)

    Retorna:
        DataFrame con columnas: Reserva, QUOTED_RATE, Rate, Currency, Fecha_Consulta
    """
    lsreserva = list(df_reservas["Reservation"])
    fecha_hoy = datetime.today().strftime('%Y-%m-%d')
    total     = len(lsreserva)

    logger.info("Inicializando conexion con BlueZone/Wizard...")

    bzhao = win32com.client.Dispatch("BZWhll.WhllObj")

    try:
        bzhao.connect("")
    except Exception as e:
        logger.warning("Error al llamar bzhao.connect al inicio: %s", e)

    # Verificacion inicial de la terminal
    _verificar_y_reconectar(bzhao, cfg, notificador)
    logger.info("Terminal conectada. Iniciando barrido de %d reservas...", total)

    L_reserva  = []
    L_amt      = []
    L_rate     = []
    L_currency = []

    for idx, reserva in enumerate(lsreserva, start=1):
        logger.info("[%d/%d] Procesando reserva: %s", idx, total, reserva)

        # Verificar conexion antes de cada reserva
        _verificar_y_reconectar(bzhao, cfg, notificador)

        amt      = ''
        rate     = ''
        currency = ''

        try:
            # Navegar a pantalla P502
            bzhao.sendkey("<Clear>")
            bzhao.WaitReady(0, 0.00001)
            bzhao.sendkey("/for p502")
            bzhao.WaitReady(0, 0.00001)
            bzhao.SendKey("<Enter>")
            bzhao.WaitReady(0, 0.00001)

            # DR - Display Reservation
            bzhao.WriteScreen("DR", 2, 2)
            bzhao.WriteScreen("R/" + reserva, 11, 6)
            bzhao.SendKey("<Enter>")
            bzhao.WaitReady(0, 0.00001)

            amt2, rate2, currency2 = _encuentraDatos(bzhao)
            amt, rate, currency    = _validaDatos(amt, rate, currency, amt2, rate2, currency2)

            # QR - Quoted Rate
            bzhao.WriteScreen("qr", 2, 2)
            bzhao.SendKey("<Enter>")
            bzhao.WaitReady(0, 0.00001)

            amt2, rate2, currency2 = _encuentraDatos(bzhao)
            amt, rate, currency    = _validaDatos(amt, rate, currency, amt2, rate2, currency2)

            # Verificar si hay modulo 1 adicional
            mod1 = bzhao.ReadScreen("", 1, 2, 37)[1].strip()
            if re.search(r'1\b', mod1):
                bzhao.WriteScreen("                               ", 11, 6)
                bzhao.WriteScreen("1", 11, 6)
                bzhao.SendKey("<Enter>")
                bzhao.WaitReady(0, 0.00001)

                amt2, rate2, currency2 = _encuentraDatos(bzhao)
                amt, rate, currency    = _validaDatos(amt, rate, currency, amt2, rate2, currency2)

            # Verificar paginacion (MORE)
            more = bzhao.ReadScreen("", 9, 23, 72)[1].strip()
            if re.search(r'MORE\b', more):
                bzhao.SendKey("<PA1>")
                bzhao.WaitReady(0, 0.00001)

                amt2, rate2, currency2 = _encuentraDatos(bzhao)
                amt, rate, currency    = _validaDatos(amt, rate, currency, amt2, rate2, currency2)

        except ConnectionError:
            # Propagar para que el orquestador la maneje
            raise

        except Exception as e:
            logger.error("Error al procesar reserva %s: %s", reserva, e)
            # Se registra el error pero se continua con las demas reservas

        L_reserva.append(reserva)
        L_amt.append(amt)
        L_rate.append(rate)
        L_currency.append(currency)

    logger.info("Barrido completado. Total procesadas: %d", len(L_reserva))

    df_resultado = pd.DataFrame({
        "Reserva":        L_reserva,
        "QUOTED_RATE":    L_amt,
        "Rate":           L_rate,
        "Currency":       L_currency,
        "Fecha_Consulta": fecha_hoy,
    })

    return df_resultado
