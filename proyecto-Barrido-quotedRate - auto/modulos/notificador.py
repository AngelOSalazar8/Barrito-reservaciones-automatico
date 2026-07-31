"""
notificador.py
Responsabilidad: envio de correos de alerta y notificacion via Gmail SMTP.
"""

import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def enviar_correo(cfg: dict, asunto: str, cuerpo: str) -> bool:
    """
    Envia un correo de texto plano via Gmail SMTP usando App Password.

    Parametros:
        cfg    : dict completo de config.json
        asunto : Asunto del correo
        cuerpo : Cuerpo del correo en texto plano

    Retorna:
        True si el envio fue exitoso, False si ocurrio un error.
    """
    mail_cfg = cfg.get("mailAppPass", {})
    sender   = mail_cfg.get("sender", "")
    receivers = mail_cfg.get("receiver", [])
    password  = mail_cfg.get("passwordMail", "")

    if not sender or not receivers or not password:
        logger.error("Configuracion de correo incompleta. No se enviara notificacion.")
        return False

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cuerpo_completo = (
        "{}\n\n"
        "---\n"
        "Barrido Automatico - Quoted Rate\n"
        "\n"
        "Fecha/hora: {}"
    ).format(cuerpo, timestamp)

    try:
        msg = MIMEMultipart()
        msg["From"]    = sender
        msg["To"]      = ", ".join(receivers)
        msg["Subject"] = asunto
        msg.attach(MIMEText(cuerpo_completo, "plain", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, receivers, msg.as_string())

        logger.info("Correo enviado: '%s' -> %s", asunto, receivers)
        return True

    except Exception as e:
        logger.error("Error al enviar correo '%s': %s", asunto, e)
        return False
