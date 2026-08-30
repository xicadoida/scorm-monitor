"""Envio opcional por Gmail API, sem tornar o fluxo da aplica\u00e7\u00e3o dependente do e-mail."""
import base64
import json
import os
from email.message import EmailMessage
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _gmail_access_token() -> str:
    values = {
        "client_id": os.getenv("GMAIL_CLIENT_ID", ""),
        "client_secret": os.getenv("GMAIL_CLIENT_SECRET", ""),
        "refresh_token": os.getenv("GMAIL_REFRESH_TOKEN", ""),
        "grant_type": "refresh_token",
    }
    if not all(values[key] for key in ("client_id", "client_secret", "refresh_token")):
        raise RuntimeError("Credenciais da Gmail API ainda n\u00e3o foram configuradas.")
    request = Request(
        "https://oauth2.googleapis.com/token",
        data=urlencode(values).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))["access_token"]


def send_email(to: str, subject: str, text: str, html: str | None = None) -> tuple[bool, str | None]:
    """Retorna o resultado sem lan\u00e7ar exce\u00e7\u00e3o para o cadastro/recupera\u00e7\u00e3o."""
    if os.getenv("EMAIL_PROVIDER", "").strip().lower() != "gmail_api":
        return False, "Envio de e-mail n\u00e3o configurado."

    sender = os.getenv("EMAIL_SENDER", "").strip()
    if not sender:
        return False, "Remetente de e-mail n\u00e3o configurado."

    try:
        message = EmailMessage()
        message["To"] = to
        message["From"] = f'{os.getenv("EMAIL_SENDER_NAME", "IACLUBE LMS")} <{sender}>'
        message["Subject"] = subject
        message.set_content(text)
        if html:
            message.add_alternative(html, subtype="html")

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")
        _post_json(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            {"raw": raw},
            {"Authorization": f"Bearer {_gmail_access_token()}"},
        )
        return True, None
    except Exception as exc:  # O envio nunca impede uma opera\u00e7\u00e3o principal.
        return False, str(exc)[:300]
