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


def _deliver(message: EmailMessage, *, failure_context: str) -> None:
    delivery = setting("HEALTHAI_EMAIL_DELIVERY", "console").strip().lower()
    if delivery == "console":
        logger.warning("E-mail em modo local: %s", failure_context)
        return
    if delivery != "smtp":
        raise EmailDeliveryError("Modo de entrega de e-mail inválido.")

    host = setting("HEALTHAI_SMTP_HOST").strip()
    username = setting("HEALTHAI_SMTP_USERNAME").strip()
    smtp_password = setting("HEALTHAI_SMTP_PASSWORD")
    security = setting("HEALTHAI_SMTP_SECURITY", "ssl").strip().lower()
    default_port = 465 if security == "ssl" else 587
    try:
        port = int(setting("HEALTHAI_SMTP_PORT", str(default_port)))
    except ValueError as error:
        raise EmailDeliveryError("Porta SMTP inválida.") from error
    if not host or not username or not smtp_password or not message["From"]:
        raise EmailDeliveryError("Configuração SMTP incompleta.")
    if security not in {"ssl", "starttls"}:
        raise EmailDeliveryError("Segurança SMTP inválida.")

    context = ssl.create_default_context()
    try:
        if security == "ssl":
            with smtplib.SMTP_SSL(host, port, timeout=10, context=context) as smtp:
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
        logger.exception("O servidor SMTP não entregou %s.", failure_context)
        raise EmailDeliveryError("Não foi possível enviar o e-mail.") from error


def send_verification_email(
    *,
    recipient: str,
    recipient_name: str,
    verification_url: str,
) -> None:
    """Envia a confirmação ou registra o link no modo local."""
    if setting("HEALTHAI_EMAIL_DELIVERY", "console").strip().lower() == "console":
        logger.warning(
            "E-mail em modo local para %s. Link de verificação: %s",
            recipient,
            verification_url,
        )
        return
    sender = setting("HEALTHAI_EMAIL_FROM").strip()

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
    _deliver(message, failure_context="o e-mail de verificação")


def send_password_reset_email(
    *,
    recipient: str,
    recipient_name: str,
    reset_url: str,
) -> None:
    """Envia um link de uso único para redefinir a senha."""
    if setting("HEALTHAI_EMAIL_DELIVERY", "console").strip().lower() == "console":
        logger.warning(
            "E-mail em modo local para %s. Link de recuperação: %s",
            recipient,
            reset_url,
        )
        return
    sender = setting("HEALTHAI_EMAIL_FROM").strip()
    safe_name = html.escape(recipient_name)
    safe_url = html.escape(reset_url, quote=True)
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = "Redefina sua senha do HealthAI"
    message.set_content(
        f"Olá, {recipient_name}. Para redefinir sua senha, acesse: {reset_url}\n\n"
        "O link expira em 1 hora e só pode ser usado uma vez. Se você não "
        "solicitou a alteração, ignore esta mensagem."
    )
    message.add_alternative(
        (
            f"<p>Olá, {safe_name}.</p>"
            "<p>Recebemos uma solicitação para redefinir sua senha do HealthAI.</p>"
            f'<p><a href="{safe_url}">Redefinir minha senha</a></p>'
            "<p>O link expira em 1 hora e só pode ser usado uma vez. "
            "Se você não solicitou a alteração, ignore esta mensagem.</p>"
        ),
        subtype="html",
    )
    _deliver(message, failure_context="o e-mail de recuperação de senha")
