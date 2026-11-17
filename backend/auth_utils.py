"""Tokens de acesso assinados e permissões validadas no servidor."""
import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

from database import SessionLocal
from models import Student
from event_utils import has_event_scope, student_has_active_event_membership


AUTH_SECRET_MIN_LENGTH = 32
DEFAULT_TOKEN_TTL_SECONDS = 8 * 60 * 60
DEFAULT_LOGIN_MAX_ATTEMPTS = 5
DEFAULT_LOGIN_WINDOW_SECONDS = 15 * 60


@dataclass
class CurrentUser:
    student_code: str
    email: str
    is_admin: bool
    # O contexto do evento e assinado no token, mas continua sendo conferido
    # no banco a cada requisicao para que uma revogacao tenha efeito imediato.
    active_event_id: int | None = None


@dataclass(frozen=True)
class LoginRateLimit:
    max_attempts: int
    window_seconds: int


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unbase64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def auth_secret() -> bytes:
    value = os.getenv("AUTH_SECRET", "")
    if len(value) < AUTH_SECRET_MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticação indisponível: AUTH_SECRET não configurado no servidor.",
        )
    return value.encode("utf-8")


def _configuration_error(name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Autenticacao indisponivel: {name} invalido no servidor.",
    )


def _positive_setting(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = int(raw_value)
    except ValueError as error:
        raise _configuration_error(name) from error
    if not minimum <= value <= maximum:
        raise _configuration_error(name)
    return value


def token_ttl_seconds() -> int:
    """Retorna um TTL configurado de forma segura, sem falhar no import."""

    return _positive_setting(
        "AUTH_TOKEN_TTL_SECONDS",
        DEFAULT_TOKEN_TTL_SECONDS,
        minimum=60,
        maximum=24 * 60 * 60,
    )


def login_rate_limit() -> LoginRateLimit:
    """Configura a janela de tentativas sem valores inseguros silenciosos."""

    return LoginRateLimit(
        max_attempts=_positive_setting(
            "AUTH_LOGIN_MAX_ATTEMPTS",
            DEFAULT_LOGIN_MAX_ATTEMPTS,
            minimum=1,
            maximum=100,
        ),
        window_seconds=_positive_setting(
            "AUTH_LOGIN_WINDOW_SECONDS",
            DEFAULT_LOGIN_WINDOW_SECONDS,
            minimum=60,
            maximum=24 * 60 * 60,
        ),
    )


def login_principal(email: str, student_code: str | None = None) -> str:
    """Evita guardar e-mail em claro para limitar tentativas desconhecidas."""

    if student_code:
        return student_code
    digest = hmac.new(
        auth_secret(),
        f"login:{email.strip().lower()}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"login:{digest}"


def is_admin_email(email: str) -> bool:
    configured = os.getenv("ADMIN_EMAILS", "")
    admins = {item.strip().lower() for item in configured.split(",") if item.strip()}
    return email.lower() in admins


def create_access_token(student: Student, active_event_id: int | None = None) -> str:
    payload = {
        "sub": student.student_code,
        "ver": student.auth_token_version or 0,
        "exp": int(time.time()) + token_ttl_seconds(),
    }
    if active_event_id is not None:
        # Nao permita que valores arbitrarios ou booleanos virem escopo de
        # evento no token assinado.
        if isinstance(active_event_id, bool):
            raise ValueError("invalid event context")
        payload["evt"] = int(active_event_id)
    encoded_payload = _base64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(auth_secret(), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded_payload}.{_base64url(signature)}"


def _read_token(token: str) -> dict:
    try:
        if token.count(".") != 1:
            raise ValueError("invalid token format")
        encoded_payload, encoded_signature = token.split(".", 1)
        expected = hmac.new(auth_secret(), encoded_payload.encode("ascii"), hashlib.sha256).digest()
        received = _unbase64url(encoded_signature)
        if not hmac.compare_digest(expected, received):
            raise ValueError("invalid signature")
        payload = json.loads(_unbase64url(encoded_payload))
        if not isinstance(payload, dict):
            raise ValueError("invalid payload")
        if not isinstance(payload.get("sub"), str) or not payload["sub"]:
            raise ValueError("invalid subject")
        if int(payload.get("exp", 0)) <= int(time.time()):
            raise ValueError("expired token")
        int(payload.get("ver", -1))
        if "evt" in payload:
            event_id = payload["evt"]
            if isinstance(event_id, bool) or not isinstance(event_id, int) or event_id <= 0:
                raise ValueError("invalid event context")
        return payload
    except (
        ValueError,
        TypeError,
        UnicodeError,
        json.JSONDecodeError,
        binascii.Error,
        OverflowError,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação obrigatória.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = _read_token(authorization.removeprefix("Bearer ").strip())
    try:
        token_version = int(payload["ver"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessao invalida ou expirada.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    db = SessionLocal()
    try:
        student = db.query(Student).filter(Student.student_code == payload["sub"]).first()
        if (
            not student
            or (student.auth_token_version or 0) != token_version
            # Contas antigas e novos cadastros pendentes nao recebem sessao
            # ate comprovarem que controlam o endereco informado.
            or student.email_verified_at is None
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sessão inválida ou expirada.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        is_admin = is_admin_email(student.email)
        active_event_id = payload.get("evt")

        # A lista EventEmail e apenas um convite. Para um token de evento, o
        # vinculo confirmado precisa continuar ativo e corresponder ao e-mail
        # atual da conta. Para a plataforma padrao, uma conta associada a um
        # evento nao pode contornar o isolamento usando um token sem escopo.
        # Administradores ja autorizados podem auditar os dois contextos.
        if not is_admin:
            if active_event_id is not None:
                if not student_has_active_event_membership(db, student, active_event_id):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Sessao invalida ou expirada.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            elif has_event_scope(db, student):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Sessao invalida ou expirada.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        return CurrentUser(
            student_code=student.student_code,
            email=student.email,
            is_admin=is_admin,
            active_event_id=active_event_id,
        )
    finally:
        db.close()


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso administrativo obrigatório.")
    return current_user


def require_self_or_admin(student_code: str, current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.is_admin or current_user.student_code == student_code:
        return current_user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não tem acesso a estes dados.")
