from backend.email_service import send_verification_email


def test_smtp_receives_transactional_verification_message(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeSmtp:
        def __init__(self, host, port, **kwargs) -> None:
            captured["host"] = host
            captured["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, *_) -> None:
            return

        def login(self, username: str, password: str) -> None:
            captured["credentials"] = (username, password)

        def send_message(self, message) -> None:
            captured["message"] = message

    monkeypatch.setenv("HEALTHAI_EMAIL_DELIVERY", "smtp")
    monkeypatch.setenv("HEALTHAI_SMTP_HOST", "smtp.hostinger.com")
    monkeypatch.setenv("HEALTHAI_SMTP_PORT", "465")
    monkeypatch.setenv("HEALTHAI_SMTP_SECURITY", "ssl")
    monkeypatch.setenv(
        "HEALTHAI_SMTP_USERNAME",
        "nao-responda@healthai.net.br",
    )
    monkeypatch.setenv("HEALTHAI_SMTP_PASSWORD", "senha-teste")
    monkeypatch.setenv(
        "HEALTHAI_EMAIL_FROM",
        "HealthAI <nao-responda@healthai.net.br>",
    )
    monkeypatch.setattr("backend.email_service.smtplib.SMTP_SSL", FakeSmtp)

    send_verification_email(
        recipient="usuario@example.com",
        recipient_name="Usuário Teste",
        verification_url="https://healthai.example/verify-email?token=segredo",
    )

    assert captured["host"] == "smtp.hostinger.com"
    assert captured["port"] == 465
    assert captured["credentials"] == (
        "nao-responda@healthai.net.br",
        "senha-teste",
    )
    message = captured["message"]
    assert message["To"] == "usuario@example.com"
    assert "segredo" in str(message)
