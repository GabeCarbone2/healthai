"""Entrega de e-mails transacionais por SMTP autenticado."""

import html
import logging
import smtplib
import ssl
from email.message import EmailMessage

from backend.settings import setting

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Falha controlada ao entregar uma mensagem transacional."""


def send_verification_email(
    *,
    recipient: str,
    recipient_name: str,
    verification_url: str,
) -> None:
    """Envia a confirmação ou registra o link no modo local."""
    delivery = setting("HEALTHAI_EMAIL_DELIVERY", "console").strip().lower()
    if delivery == "console":
        logger.warning(
            "E-mail em modo local para %s. Link de verificação: %s",
            recipient,
            verification_url,
        )
        return
    if delivery != "smtp":
        raise EmailDeliveryError("Modo de entrega de e-mail inválido.")

    host = setting("HEALTHAI_SMTP_HOST").strip()
    username = setting("HEALTHAI_SMTP_USERNAME").strip()
    smtp_password = setting("HEALTHAI_SMTP_PASSWORD")
    sender = setting("HEALTHAI_EMAIL_FROM").strip()
    security = setting("HEALTHAI_SMTP_SECURITY", "ssl").strip().lower()
    default_port = 465 if security == "ssl" else 587
    try:
        port = int(setting("HEALTHAI_SMTP_PORT", str(default_port)))
    except ValueError as error:
        raise EmailDeliveryError("Porta SMTP inválida.") from error
    if not host or not username or not smtp_password or not sender:
        raise EmailDeliveryError("Configuração SMTP incompleta.")
    if security not in {"ssl", "starttls"}:
        raise EmailDeliveryError("Segurança SMTP inválida.")

    safe_name = html.escape(recipient_name)
    safe_url = html.escape(verification_url, quote=True)
    text = (
        f"Olá, {recipient_name}. Confirme seu e-mail no HealthAI acessando: "
        f"{verification_url}\n\nO link expira em 24 horas."
    )
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = "Confirme seu e-mail no HealthAI"
    message.set_content(text)
    message.add_alternative(
        (
            f"<p>Olá, {safe_name}.</p>"
            "<p>Confirme seu e-mail para ativar sua conta no HealthAI.</p>"
            f'<p><a href="{safe_url}">Confirmar meu e-mail</a></p>'
            "<p>O link expira em 24 horas.</p>"
        ),
        subtype="html",
    )
    context = ssl.create_default_context()
    try:
        if security == "ssl":
            with smtplib.SMTP_SSL(
                host,
                port,
                timeout=10,
                context=context,
            ) as smtp:
                smtp.login(username, smtp_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=10) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
                smtp.login(username, smtp_password)
                smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        logger.exception("O servidor SMTP não entregou o e-mail de verificação.")
        raise EmailDeliveryError(
            "Não foi possível enviar o e-mail de verificação."
        ) from error
