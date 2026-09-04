import uuid
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func

from database import SessionLocal
from models import Student, Event, RegistrationProfile, PasswordResetToken
from schemas import ChangePasswordRequest
from security import hash_password, verify_password
from event_utils import get_event_for_email
from auth_utils import CurrentUser, create_access_token, get_current_user, is_admin_email
from email_service import send_email
from privacy import prune_expired_access_events, record_access_event

router = APIRouter()
TERMS_OF_USE_URL = "https://iaclube.com/sobre/temos-de-uso-lms"


class LoginRequest(BaseModel):
    email: str
    password: str
    event_slug: str | None = None


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    person_type: Literal["pf", "pj"]
    accepted_terms: bool
    event_slug: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: str
    event_slug: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


def _reset_token_hash(token: str) -> str:
    secret = os.getenv("AUTH_SECRET", "")
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="Recupera\u00e7\u00e3o de senha indispon\u00edvel no servidor.")
    return hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def _public_app_url(event: dict | None = None) -> str:
    base = os.getenv("PUBLIC_APP_URL", "https://lms.iaclube.help").rstrip("/")
    return f"{base}/{event['slug']}" if event and event.get("slug") else base


def _record_email_result(event_type: str, success: bool, student: Student, event: dict | None):
    """Falha de e-mail n\u00e3o desfaz cadastro ou troca de senha; fica audit\u00e1vel."""
    db = SessionLocal()
    try:
        record_access_event(
            db, None, event_type, success=success, student_code=student.student_code,
            event_id=event["id"] if event else None, route="email",
        )
        db.commit()
    finally:
        db.close()


def _send_registration_confirmation(student: Student, event: dict | None):
    name = student.name.strip() or "pessoa estudante"
    sent, _ = send_email(
        student.email,
        "Cadastro confirmado - IACLUBE LMS",
        f"Ol\u00e1, {name}! Seu cadastro no IACLUBE LMS foi criado com sucesso. Acesse: {_public_app_url(event)}",
        f"<p>Ol\u00e1, {name}!</p><p>Seu cadastro no <strong>IACLUBE LMS</strong> foi criado com sucesso.</p><p><a href=\"{_public_app_url(event)}\">Acessar a plataforma</a></p>",
    )
    _record_email_result("registration_email", sent, student, event)


def _check_event_access(db, email, event_slug):
    """Impede que contas de evento atravessem para a plataforma padrão."""
    student_event = get_event_for_email(db, email)

    if event_slug:
        target_event = db.query(Event).filter(Event.slug == event_slug.strip().lower()).first()
        if not target_event:
            return False, "Evento não encontrado."
        if not student_event or student_event["id"] != target_event.id:
            return False, "Este e-mail não está cadastrado neste evento."
        return True, None

    if student_event:
        return False, "Use o link exclusivo do seu evento para entrar."

    return True, None


@router.post("/auth/login")
def login(data: LoginRequest, request: Request):
    db = SessionLocal()
    email = data.email.strip().lower()

    student = db.query(Student).filter(
        func.lower(Student.email) == email
    ).first()

    if not student:
        record_access_event(db, request, "login", success=False, route="/auth/login")
        prune_expired_access_events(db)
        db.commit()
        db.close()
        return {
            "success": False,
            "message": "Aluno não encontrado."
        }

    if not verify_password(data.password, student.password_hash):
        record_access_event(
            db, request, "login", success=False,
            student_code=student.student_code, route="/auth/login",
        )
        prune_expired_access_events(db)
        db.commit()
        db.close()
        return {
            "success": False,
            "message": "Senha incorreta."
        }

    event = get_event_for_email(db, student.email)
    allowed, message = _check_event_access(db, student.email, data.event_slug)
    if not allowed:
        record_access_event(
            db, request, "login", success=False,
            student_code=student.student_code,
            event_id=event["id"] if event else None,
            route="/auth/login",
        )
        prune_expired_access_events(db)
        db.commit()
        db.close()
        return {"success": False, "message": message}
    record_access_event(
        db, request, "login", success=True,
        student_code=student.student_code,
        event_id=event["id"] if event else None,
        route="/auth/login",
    )
    prune_expired_access_events(db)
    db.commit()
    access_token = create_access_token(student)
    db.close()

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "student": {
            "id": student.id,
            "student_code": student.student_code,
            "name": student.name,
            "email": student.email,
            "event": event,
            "is_admin": is_admin_email(student.email),
        }
    }


@router.post("/auth/register")
def register(data: RegisterRequest, request: Request):
    db = SessionLocal()
    email = data.email.strip().lower()

    if not data.accepted_terms:
        record_access_event(db, request, "registration", success=False, route="/auth/register")
        prune_expired_access_events(db)
        db.commit()
        db.close()
        return {"success": False, "message": "É necessário aceitar os termos de uso para criar a conta."}

    if len(data.password) < 6:
        record_access_event(db, request, "registration", success=False, route="/auth/register")
        prune_expired_access_events(db)
        db.commit()
        db.close()
        return {"success": False, "message": "A senha precisa ter pelo menos 6 caracteres."}

    existing_student = db.query(Student).filter(
        func.lower(Student.email) == email
    ).first()

    if existing_student:
        record_access_event(db, request, "registration", success=False, route="/auth/register")
        prune_expired_access_events(db)
        db.commit()
        db.close()
        return {
            "success": False,
            "message": "Este email já está cadastrado."
        }

    allowed, message = _check_event_access(db, email, data.event_slug)
    if not allowed:
        record_access_event(db, request, "registration", success=False, route="/auth/register")
        prune_expired_access_events(db)
        db.commit()
        db.close()
        return {"success": False, "message": message}

    student = Student(
        student_code=f"aluno_{uuid.uuid4().hex[:8]}",
        name=data.name,
        email=email,
        password_hash=hash_password(data.password)
    )

    db.add(student)
    db.flush()

    event = get_event_for_email(db, student.email)
    now = datetime.utcnow()
    db.add(RegistrationProfile(
        student_code=student.student_code,
        person_type=data.person_type,
        accepted_terms_at=now,
        accepted_terms_url=TERMS_OF_USE_URL,
        event_id=event["id"] if event else None,
        created_at=now,
        updated_at=now,
    ))
    record_access_event(
        db, request, "registration", success=True,
        student_code=student.student_code,
        event_id=event["id"] if event else None,
        route="/auth/register",
    )
    prune_expired_access_events(db)
    db.commit()
    db.refresh(student)
    db.close()
    _send_registration_confirmation(student, event)

    return {
        "success": True,
        "student": {
            "id": student.id,
            "student_code": student.student_code,
            "name": student.name,
            "email": student.email,
            "event": event,
            "is_admin": is_admin_email(student.email),
        }
    }


@router.post("/auth/forgot-password")
def forgot_password(data: ForgotPasswordRequest, request: Request):
    """Sempre responde de forma gen\u00e9rica para n\u00e3o revelar e-mails cadastrados."""
    db = SessionLocal()
    email = data.email.strip().lower()
    student = db.query(Student).filter(func.lower(Student.email) == email).first()
    event = get_event_for_email(db, email) if student else None
    generic_response = {
        "success": True,
        "message": "Se o e-mail estiver cadastrado, enviaremos as instru\u00e7\u00f5es de recupera\u00e7\u00e3o.",
    }

    if not student:
        record_access_event(db, request, "password_reset_requested", success=False, route="/auth/forgot-password")
        db.commit()
        db.close()
        return generic_response

    allowed, _ = _check_event_access(db, student.email, data.event_slug)
    if not allowed:
        record_access_event(db, request, "password_reset_requested", success=False, student_code=student.student_code, route="/auth/forgot-password")
        db.commit()
        db.close()
        return generic_response

    now = datetime.utcnow()
    db.query(PasswordResetToken).filter(
        PasswordResetToken.student_code == student.student_code,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: now}, synchronize_session=False)
    raw_token = secrets.token_urlsafe(32)
    ttl = max(5, int(os.getenv("PASSWORD_RESET_TOKEN_TTL_MINUTES", "60")))
    db.add(PasswordResetToken(
        student_code=student.student_code,
        token_hash=_reset_token_hash(raw_token),
        expires_at=now + timedelta(minutes=ttl),
        created_at=now,
    ))
    record_access_event(
        db, request, "password_reset_requested", success=True,
        student_code=student.student_code, event_id=event["id"] if event else None,
        route="/auth/forgot-password",
    )
    db.commit()
    db.refresh(student)
    db.close()

    reset_url = f"{_public_app_url(event)}?reset_token={raw_token}"
    sent, _ = send_email(
        student.email,
        "Redefini\u00e7\u00e3o de senha - IACLUBE LMS",
        f"Ol\u00e1, {student.name}! Use este link para criar uma nova senha: {reset_url}\n\nO link expira em {ttl} minutos.",
        f"<p>Ol\u00e1, {student.name}!</p><p>Use o link abaixo para criar uma nova senha. Ele expira em {ttl} minutos.</p><p><a href=\"{reset_url}\">Redefinir senha</a></p>",
    )
    _record_email_result("password_reset_email", sent, student, event)
    return generic_response


@router.post("/auth/reset-password")
def reset_password(data: ResetPasswordRequest, request: Request):
    if len(data.new_password) < 6:
        return {"success": False, "message": "A nova senha precisa ter pelo menos 6 caracteres."}

    db = SessionLocal()
    token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == _reset_token_hash(data.token),
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at >= datetime.utcnow(),
    ).first()
    if not token:
        record_access_event(db, request, "password_reset_completed", success=False, route="/auth/reset-password")
        db.commit()
        db.close()
        return {"success": False, "message": "Este link de recupera\u00e7\u00e3o \u00e9 inv\u00e1lido ou expirou."}

    student = db.query(Student).filter(Student.student_code == token.student_code).first()
    if not student:
        token.used_at = datetime.utcnow()
        db.commit()
        db.close()
        return {"success": False, "message": "Conta n\u00e3o encontrada."}

    now = datetime.utcnow()
    token.used_at = now
    student.password_hash = hash_password(data.new_password)
    student.auth_token_version = (student.auth_token_version or 0) + 1
    event = get_event_for_email(db, student.email)
    record_access_event(
        db, request, "password_reset_completed", success=True,
        student_code=student.student_code, event_id=event["id"] if event else None,
        route="/auth/reset-password",
    )
    db.commit()
    db.close()
    return {"success": True, "message": "Senha redefinida. Entre com a nova senha."}


@router.post("/auth/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    if current_user.student_code != data.student_code:
        raise HTTPException(status_code=403, detail="Você não pode alterar a senha de outra pessoa.")

    if len(data.new_password) < 6:
        return {"success": False, "message": "A nova senha precisa ter pelo menos 6 caracteres."}

    db = SessionLocal()

    student = db.query(Student).filter(
        Student.student_code == data.student_code
    ).first()

    if not student:
        db.close()
        return {"success": False, "message": "Aluno não encontrado."}

    if not verify_password(data.current_password, student.password_hash):
        db.close()
        return {"success": False, "message": "Senha atual incorreta."}

    student.password_hash = hash_password(data.new_password)
    student.auth_token_version = (student.auth_token_version or 0) + 1
    db.commit()
    db.refresh(student)
    access_token = create_access_token(student)
    db.close()

    return {
        "success": True,
        "message": "Senha alterada com sucesso.",
        "access_token": access_token,
        "token_type": "bearer",
    }
