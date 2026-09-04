"""Tokens de acesso assinados e permissões validadas no servidor."""
import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

from database import SessionLocal
from models import Student


TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "28800"))


@dataclass
class CurrentUser:
    student_code: str
    email: str
    is_admin: bool


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unbase64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _secret() -> bytes:
    value = os.getenv("AUTH_SECRET", "")
    if len(value) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticação indisponível: AUTH_SECRET não configurado no servidor.",
        )
    return value.encode("utf-8")


def is_admin_email(email: str) -> bool:
    configured = os.getenv("ADMIN_EMAILS", "admin@admin.com")
    admins = {item.strip().lower() for item in configured.split(",") if item.strip()}
    return email.lower() in admins


def create_access_token(student: Student) -> str:
    payload = {
        "sub": student.student_code,
        "ver": student.auth_token_version or 0,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    encoded_payload = _base64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(_secret(), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded_payload}.{_base64url(signature)}"


def _read_token(token: str) -> dict:
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        expected = hmac.new(_secret(), encoded_payload.encode("ascii"), hashlib.sha256).digest()
        received = _unbase64url(encoded_signature)
        if not hmac.compare_digest(expected, received):
            raise ValueError("invalid signature")
        payload = json.loads(_unbase64url(encoded_payload))
        if not payload.get("sub") or int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired token")
        return payload
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
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
    db = SessionLocal()
    try:
        student = db.query(Student).filter(Student.student_code == payload["sub"]).first()
        if not student or (student.auth_token_version or 0) != int(payload.get("ver", -1)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sessão inválida ou expirada.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return CurrentUser(
            student_code=student.student_code,
            email=student.email,
            is_admin=is_admin_email(student.email),
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
