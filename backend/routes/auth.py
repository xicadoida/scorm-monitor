"""Autenticacao, confirmacao de e-mail e recuperacao de conta.

Os links de confirmacao usam um fragmento de URL. O fragmento nunca e enviado
ao servidor no GET inicial; o frontend le o valor e o envia somente por POST.
"""
import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func

from auth_utils import (
    CurrentUser,
    auth_secret,
    create_access_token,
    get_current_user,
    is_admin_email,
    login_principal,
    login_rate_limit,
)
from database import SessionLocal
from email_service import send_email
from event_utils import (
    get_event_by_slug,
    get_event_for_student,
    has_event_scope,
    is_email_invited_to_event,
    normalize_email,
    serialize_event,
    student_has_active_event_membership,
)
from models import (
    AccessEvent,
    EmailVerificationToken,
    Event,
    EventMembership,
    PasswordResetToken,
    RegistrationProfile,
    Student,
)
from privacy import prune_expired_access_events, record_access_event, trusted_forwarded_ip_hash
from schemas import ChangePasswordRequest
from security import hash_password, verify_password


router = APIRouter()
TERMS_OF_USE_URL = "https://iaclube.com/sobre/temos-de-uso-lms"
GENERIC_DELIVERY_MESSAGE = (
    "Se houver uma conta elegivel, enviaremos as instrucoes para este e-mail."
)
GENERIC_VERIFICATION_ERROR = "Nao foi possivel confirmar este link."
# Hash valido usado para aproximar o custo de uma senha inexistente.
DUMMY_PASSWORD_HASH = (
    "00000000000000000000000000000000$"
    "0000000000000000000000000000000000000000000000000000000000000000"
)


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


class ResendEmailVerificationRequest(BaseModel):
    email: str
    event_slug: str | None = None


class VerifyEmailRequest(BaseModel):
    token: str
    new_password: str | None = None


class ChangeEmailRequest(BaseModel):
    current_password: str
    new_email: str


def _configuration_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = int(raw_value)
    except ValueError as error:
        raise HTTPException(
            status_code=503,
            detail=f"Configuracao de seguranca invalida: {name}.",
        ) from error
    if not minimum <= value <= maximum:
        raise HTTPException(
            status_code=503,
            detail=f"Configuracao de seguranca invalida: {name}.",
        )
    return value


def _verification_ttl_minutes() -> int:
    return _configuration_int(
        "EMAIL_VERIFICATION_TOKEN_TTL_MINUTES", 60, minimum=5, maximum=24 * 60
    )


def _verification_request_policy() -> tuple[int, int]:
    return (
        _configuration_int("EMAIL_VERIFICATION_MAX_REQUESTS", 3, minimum=1, maximum=20),
        _configuration_int(
            "EMAIL_VERIFICATION_REQUEST_WINDOW_SECONDS", 15 * 60,
            minimum=60,
            maximum=24 * 60 * 60,
        ),
    )


def _verification_attempt_policy() -> tuple[int, int]:
    return (
        _configuration_int("EMAIL_VERIFICATION_MAX_ATTEMPTS", 5, minimum=1, maximum=30),
        _configuration_int(
            "EMAIL_VERIFICATION_ATTEMPT_WINDOW_SECONDS", 15 * 60,
            minimum=60,
            maximum=24 * 60 * 60,
        ),
    )


def _reset_token_hash(token: str) -> str:
    return hmac.new(auth_secret(), token.encode("utf-8"), hashlib.sha256).hexdigest()


def _verification_token_hash(token: str) -> str:
    """Usa dominio HMAC separado do token de recuperacao de senha."""

    return hmac.new(
        auth_secret(), f"email-verification:{token}".encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _verification_principal(value: str) -> str:
    """Identificador HMAC para rate limit sem registrar e-mail ou token bruto."""

    digest = hmac.new(
        auth_secret(), f"email-verification-principal:{value}".encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"verification:{digest}"


def _public_app_url(event: dict | None = None) -> str:
    base = os.getenv("PUBLIC_APP_URL", "https://lms.iaclube.help").rstrip("/")
    return f"{base}/{event['slug']}" if event and event.get("slug") else base


def _record_email_result(
    event_type: str,
    success: bool,
    student_code: str,
    event: dict | None,
) -> None:
    """Falha de e-mail e auditavel, mas nao despeja detalhes do provedor."""

    db = SessionLocal()
    try:
        record_access_event(
            db,
            None,
            event_type,
            success=success,
            student_code=student_code,
            event_id=event["id"] if event else None,
            route="email",
        )
        db.commit()
    finally:
        db.close()


def _send_verification_email(
    *,
    email: str,
    name: str,
    student_code: str,
    raw_token: str,
    event: dict | None,
    purpose: str,
) -> bool:
    """Envia o unico local onde o token bruto e usado apos a criacao."""

    verification_url = f"{_public_app_url(event)}#verify_token={raw_token}"
    subject = "Confirme seu e-mail - IACLUBE LMS"
    if purpose == "email_change":
        intro = "Confirme o novo e-mail da sua conta"
    elif purpose == "event_membership":
        intro = "Confirme seu e-mail para acessar este evento"
    else:
        intro = "Confirme seu e-mail para ativar sua conta"
    sent, _ = send_email(
        email,
        subject,
        f"Ola, {name or 'pessoa estudante'}! {intro}: {verification_url}\n\n"
        "O link expira em breve e so pode ser usado uma vez.",
        f"<p>Ola, {name or 'pessoa estudante'}!</p><p>{intro}.</p>"
        f"<p><a href=\"{verification_url}\">Confirmar e-mail</a></p>"
        "<p>O link expira em breve e so pode ser usado uma vez.</p>",
    )
    _record_email_result("email_verification_email", sent, student_code, event)
    return sent


def _invalid_credentials_response() -> JSONResponse:
    """Nao diferencia conta inexistente de senha invalida."""

    return JSONResponse(
        status_code=401,
        content={"success": False, "message": "Credenciais invalidas."},
    )


def _failed_login_attempts(db, principal: str, client_ip_hash: str | None, cutoff: datetime) -> int:
    base_query = db.query(AccessEvent).filter(
        AccessEvent.event_type == "login",
        AccessEvent.success.is_(False),
        AccessEvent.created_at >= cutoff,
    )
    principal_count = base_query.filter(AccessEvent.student_code == principal).count()
    if not client_ip_hash:
        return principal_count
    ip_count = base_query.filter(AccessEvent.ip_hash == client_ip_hash).count()
    return max(principal_count, ip_count)


def _rate_limited_response(window_seconds: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "message": "Muitas tentativas. Aguarde antes de tentar novamente.",
        },
        headers={"Retry-After": str(window_seconds)},
    )


def _verification_rate_limited(
    db,
    request: Request,
    *,
    event_type: str,
    principal: str,
    maximum: int,
    window_seconds: int,
) -> bool:
    cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
    query = db.query(AccessEvent).filter(
        AccessEvent.event_type == event_type,
        AccessEvent.created_at >= cutoff,
    )
    # Cada pedido de reenvio consome a cota, mesmo quando o e-mail e elegivel.
    # Para tentativa de confirmar, apenas falhas consomem a cota do token.
    if event_type not in {"email_verification_requested", "email_change_requested"}:
        query = query.filter(AccessEvent.success.is_(False))
    principal_count = query.filter(AccessEvent.student_code == principal).count()
    client_ip_hash = trusted_forwarded_ip_hash(request)
    if not client_ip_hash:
        return principal_count >= maximum
    return max(principal_count, query.filter(AccessEvent.ip_hash == client_ip_hash).count()) >= maximum


def _mark_verification_attempt(
    db,
    request: Request,
    *,
    success: bool,
    principal: str,
    student_code: str | None = None,
    event_id: int | None = None,
) -> None:
    record_access_event(
        db,
        request,
        "email_verification_attempt",
        success=success,
        # Em falhas o principal e HMAC do token, nunca o valor bruto.
        student_code=student_code if success else principal,
        event_id=event_id,
        route="/auth/verify-email",
    )


def _issue_verification_token(
    db,
    *,
    student: Student,
    email: str,
    purpose: str,
    event_id: int | None,
) -> tuple[str, datetime]:
    """Invalida links anteriores equivalentes e guarda somente o HMAC novo."""

    now = datetime.utcnow()
    target_email = normalize_email(email)
    pending = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.student_code == student.student_code,
        EmailVerificationToken.purpose == purpose,
        EmailVerificationToken.used_at.is_(None),
        func.lower(EmailVerificationToken.email) == target_email,
    )
    pending = (
        pending.filter(EmailVerificationToken.event_id.is_(None))
        if event_id is None
        else pending.filter(EmailVerificationToken.event_id == event_id)
    )
    pending.update({EmailVerificationToken.used_at: now}, synchronize_session=False)

    raw_token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(minutes=_verification_ttl_minutes())
    db.add(
        EmailVerificationToken(
            student_code=student.student_code,
            email=target_email,
            event_id=event_id,
            purpose=purpose,
            token_hash=_verification_token_hash(raw_token),
            expires_at=expires_at,
            created_at=now,
        )
    )
    return raw_token, expires_at


def _event_for_request(db, event_slug: str | None) -> Event | None:
    return get_event_by_slug(db, event_slug) if event_slug else None


def _event_dict(event: Event | None) -> dict | None:
    return serialize_event(event)


def _can_use_event_context(db, student: Student, event_slug: str | None) -> tuple[bool, dict | None]:
    """Valida o ambiente de login, sempre via membership confirmada."""

    if event_slug:
        event = _event_for_request(db, event_slug)
        if not event:
            return False, None
        event_data = _event_dict(event)
        if is_admin_email(student.email) or student_has_active_event_membership(db, student, event.id):
            return True, event_data
        return False, event_data
    if is_admin_email(student.email):
        return True, None
    return (not has_event_scope(db, student)), None


@router.post("/auth/login")
def login(data: LoginRequest, request: Request):
    auth_secret()
    policy = login_rate_limit()
    db = SessionLocal()
    try:
        email = normalize_email(data.email)
        student = db.query(Student).filter(func.lower(Student.email) == email).first()
        principal = login_principal(email, student.student_code if student else None)
        client_ip_hash = trusted_forwarded_ip_hash(request)
        cutoff = datetime.utcnow() - timedelta(seconds=policy.window_seconds)

        if _failed_login_attempts(db, principal, client_ip_hash, cutoff) >= policy.max_attempts:
            record_access_event(
                db,
                request,
                "login_rate_limited",
                success=False,
                student_code=principal,
                route="/auth/login",
            )
            prune_expired_access_events(db)
            db.commit()
            return _rate_limited_response(policy.window_seconds)

        if not student:
            verify_password(data.password, DUMMY_PASSWORD_HASH)
            record_access_event(db, request, "login", success=False, student_code=principal, route="/auth/login")
            prune_expired_access_events(db)
            db.commit()
            return _invalid_credentials_response()

        if not verify_password(data.password, student.password_hash):
            record_access_event(
                db,
                request,
                "login",
                success=False,
                student_code=student.student_code,
                route="/auth/login",
            )
            prune_expired_access_events(db)
            db.commit()
            return _invalid_credentials_response()

        if student.email_verified_at is None:
            record_access_event(
                db,
                request,
                "login",
                success=False,
                student_code=student.student_code,
                route="/auth/login",
            )
            db.commit()
            return {
                "success": False,
                "message": "Confirme seu e-mail antes de entrar. Use a opcao de reenviar confirmacao se necessario.",
            }

        allowed, event = _can_use_event_context(db, student, data.event_slug)
        if not allowed:
            record_access_event(
                db,
                request,
                "login",
                success=False,
                student_code=student.student_code,
                event_id=event["id"] if event else None,
                route="/auth/login",
            )
            prune_expired_access_events(db)
            db.commit()
            return {"success": False, "message": "Esta conta nao tem acesso a este ambiente."}

        record_access_event(
            db,
            request,
            "login",
            success=True,
            student_code=student.student_code,
            event_id=event["id"] if event else None,
            route="/auth/login",
        )
        prune_expired_access_events(db)
        db.commit()
        access_token = create_access_token(student, event["id"] if event else None)
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
            },
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/auth/logout")
def logout(request: Request, current_user: CurrentUser = Depends(get_current_user)):
    """Revoga todos os tokens ativos da conta pela versao de autenticacao."""

    db = SessionLocal()
    try:
        student = db.query(Student).filter(Student.student_code == current_user.student_code).first()
        if not student:
            raise HTTPException(status_code=401, detail="Sessao invalida ou expirada.")
        student.auth_token_version = (student.auth_token_version or 0) + 1
        record_access_event(
            db,
            request,
            "logout",
            success=True,
            student_code=student.student_code,
            event_id=current_user.active_event_id,
            route="/auth/logout",
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return {"success": True, "message": "Sessao encerrada com sucesso."}


def _registration_is_eligible(db, email: str, event_slug: str | None) -> tuple[bool, Event | None]:
    """Aplica o convite apenas para emitir confirmacao, nunca para autorizar."""

    if event_slug:
        event = _event_for_request(db, event_slug)
        return bool(event and is_email_invited_to_event(db, email, event.id)), event
    # Uma pessoa convidada deve iniciar pelo link do evento, impedindo que use
    # o cadastro padrao para mais tarde atravessar esse isolamento.
    return (not has_event_scope_for_email(db, email)), None


def has_event_scope_for_email(db, email: str) -> bool:
    # Import local evita expor uma consulta de convite como regra de acesso.
    from event_utils import has_any_event_invitation

    return has_any_event_invitation(db, email)


def _verification_request_response() -> dict:
    return {"success": True, "message": GENERIC_DELIVERY_MESSAGE}


def _request_verification(
    db,
    request: Request,
    *,
    email: str,
    event_slug: str | None,
    registration_data: RegisterRequest | None = None,
) -> dict:
    """Fluxo compartilhado por cadastro e reenvio, sem enumerar contas."""

    auth_secret()
    maximum, window_seconds = _verification_request_policy()
    principal = _verification_principal(email)
    if _verification_rate_limited(
        db,
        request,
        event_type="email_verification_requested",
        principal=principal,
        maximum=maximum,
        window_seconds=window_seconds,
    ):
        record_access_event(
            db,
            request,
            "email_verification_rate_limited",
            success=False,
            student_code=principal,
            route="/auth/resend-email-verification",
        )
        db.commit()
        return _rate_limited_response(window_seconds)

    eligible, requested_event = _registration_is_eligible(db, email, event_slug)
    existing = db.query(Student).filter(func.lower(Student.email) == email).first()
    student = existing
    purpose = None
    event_id = requested_event.id if requested_event and eligible else None

    # Reservas administrativas continuam proibidas para criacao publica. Uma
    # conta administrativa ja provisionada ainda pode receber sua confirmacao.
    if not existing and is_admin_email(email):
        eligible = False

    if eligible and not student:
        if registration_data is None:
            # Reenvio para um endereco sem conta e intencionalmente inerte.
            eligible = False
        else:
            now = datetime.utcnow()
            student = Student(
                student_code=f"aluno_{uuid.uuid4().hex[:8]}",
                name=registration_data.name.strip(),
                email=email,
                password_hash=hash_password(registration_data.password),
                email_verified_at=None,
            )
            db.add(student)
            db.flush()
            # O perfil registra apenas o cadastro, sem conceder nem inferir
            # pertencimento de evento. Membership so nasce apos o link.
            db.add(
                RegistrationProfile(
                    student_code=student.student_code,
                    person_type=registration_data.person_type,
                    accepted_terms_at=now,
                    accepted_terms_url=TERMS_OF_USE_URL,
                    event_id=None,
                    created_at=now,
                    updated_at=now,
                )
            )

    if eligible and student:
        if student.email_verified_at is None:
            purpose = "registration"
        elif requested_event and event_id and not student_has_active_event_membership(db, student, event_id):
            purpose = "event_membership"
        elif student.email_verified_at is None:
            purpose = "registration"

    event_data = _event_dict(requested_event) if event_id else None
    if purpose and student:
        raw_token, _ = _issue_verification_token(
            db,
            student=student,
            email=email,
            purpose=purpose,
            event_id=event_id,
        )
        record_access_event(
            db,
            request,
            "email_verification_requested",
            success=True,
            # Mantem o mesmo principal HMAC das solicitacoes inertes para que
            # a cota conte pedidos elegiveis e nao elegiveis igualmente.
            student_code=principal,
            event_id=event_id,
            route="/auth/register" if registration_data else "/auth/resend-email-verification",
        )
        db.commit()
        _send_verification_email(
            email=student.email,
            name=student.name,
            student_code=student.student_code,
            raw_token=raw_token,
            event=event_data,
            purpose=purpose,
        )
        return _verification_request_response()

    # Registra uma solicitacao inerte com principal HMAC para aplicar limite de
    # abuso, mas nao revela se a conta, o convite ou o evento existem.
    record_access_event(
        db,
        request,
        "email_verification_requested",
        success=False,
        student_code=principal,
        event_id=requested_event.id if requested_event else None,
        route="/auth/register" if registration_data else "/auth/resend-email-verification",
    )
    db.commit()
    return _verification_request_response()


@router.post("/auth/register")
def register(data: RegisterRequest, request: Request):
    email = normalize_email(data.email)
    db = SessionLocal()
    try:
        if not data.accepted_terms:
            record_access_event(db, request, "registration", success=False, route="/auth/register")
            db.commit()
            return {"success": False, "message": "E necessario aceitar os termos de uso para criar a conta."}
        if len(data.password) < 6:
            record_access_event(db, request, "registration", success=False, route="/auth/register")
            db.commit()
            return {"success": False, "message": "A senha precisa ter pelo menos 6 caracteres."}
        response = _request_verification(
            db,
            request,
            email=email,
            event_slug=data.event_slug,
            registration_data=data,
        )
        # O registro principal e mantido para metricas sem incluir token.
        if isinstance(response, dict):
            record_access_event(db, request, "registration", success=True, route="/auth/register")
            db.commit()
        return response
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/auth/resend-email-verification")
def resend_email_verification(data: ResendEmailVerificationRequest, request: Request):
    db = SessionLocal()
    try:
        return _request_verification(
            db,
            request,
            email=normalize_email(data.email),
            event_slug=data.event_slug,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _activate_event_membership(db, student: Student, event_id: int, email: str, now: datetime) -> bool:
    """Ativa exclusivamente o evento gravado no token confirmado."""

    if not is_email_invited_to_event(db, email, event_id):
        return False
    membership = db.query(EventMembership).filter(
        EventMembership.student_code == student.student_code,
        EventMembership.event_id == event_id,
    ).first()
    if membership:
        membership.email = email
        membership.status = "confirmed"
        membership.confirmed_at = now
        membership.revoked_at = None
    else:
        db.add(
            EventMembership(
                student_code=student.student_code,
                event_id=event_id,
                email=email,
                status="confirmed",
                confirmed_at=now,
                created_at=now,
            )
        )
    return True


@router.post("/auth/verify-email")
def verify_email(data: VerifyEmailRequest, request: Request):
    auth_secret()
    raw_token = (data.token or "").strip()
    principal = _verification_principal(raw_token)
    maximum, window_seconds = _verification_attempt_policy()
    db = SessionLocal()
    try:
        if _verification_rate_limited(
            db,
            request,
            event_type="email_verification_attempt",
            principal=principal,
            maximum=maximum,
            window_seconds=window_seconds,
        ):
            record_access_event(
                db,
                request,
                "email_verification_rate_limited",
                success=False,
                student_code=principal,
                route="/auth/verify-email",
            )
            db.commit()
            return _rate_limited_response(window_seconds)

        now = datetime.utcnow()
        token = db.query(EmailVerificationToken).filter(
            EmailVerificationToken.token_hash == _verification_token_hash(raw_token),
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.expires_at >= now,
        ).first()
        if not token:
            _mark_verification_attempt(db, request, success=False, principal=principal)
            db.commit()
            return {"success": False, "message": GENERIC_VERIFICATION_ERROR}

        student = db.query(Student).filter(Student.student_code == token.student_code).first()
        if not student or token.purpose not in {"registration", "event_membership", "email_change"}:
            token.used_at = now
            _mark_verification_attempt(db, request, success=False, principal=principal)
            db.commit()
            return {"success": False, "message": GENERIC_VERIFICATION_ERROR}

        # O primeiro titular do e-mail escolhe sua propria senha depois de
        # receber o link. Assim, quem preencheu um cadastro com e-mail alheio
        # nao conserva a senha escolhida antes da comprovacao.
        if token.purpose != "email_change" and student.email_verified_at is None:
            if not data.new_password or len(data.new_password) < 6:
                # Mesmo um token valido nao pode ser sondado indefinidamente.
                # O identificador persistido na auditoria e somente o HMAC do
                # token, portanto o limite nao expõe o segredo recebido por
                # e-mail. A primeira chamada sem senha e esperada pelo fluxo
                # visual e conta como uma tentativa dentro da janela.
                _mark_verification_attempt(
                    db,
                    request,
                    success=False,
                    principal=principal,
                    event_id=token.event_id,
                )
                db.commit()
                return {
                    "success": False,
                    "requires_new_password": True,
                    "message": "Defina uma nova senha de pelo menos 6 caracteres para ativar a conta.",
                }

        event_access_granted = False
        if token.purpose == "email_change":
            target_email = normalize_email(token.email)
            duplicate = db.query(Student).filter(
                func.lower(Student.email) == target_email,
                Student.student_code != student.student_code,
            ).first()
            if duplicate or is_admin_email(target_email):
                token.used_at = now
                _mark_verification_attempt(db, request, success=False, principal=principal)
                db.commit()
                return {"success": False, "message": GENERIC_VERIFICATION_ERROR}

            student.email = target_email
            student.email_verified_at = now
            student.auth_token_version = (student.auth_token_version or 0) + 1
            db.query(EventMembership).filter(
                EventMembership.student_code == student.student_code,
                EventMembership.status == "confirmed",
                EventMembership.revoked_at.is_(None),
            ).update(
                {EventMembership.status: "revoked", EventMembership.revoked_at: now},
                synchronize_session=False,
            )
            db.query(PasswordResetToken).filter(
                PasswordResetToken.student_code == student.student_code,
                PasswordResetToken.used_at.is_(None),
            ).update({PasswordResetToken.used_at: now}, synchronize_session=False)
        else:
            if normalize_email(student.email) != normalize_email(token.email):
                token.used_at = now
                _mark_verification_attempt(db, request, success=False, principal=principal)
                db.commit()
                return {"success": False, "message": GENERIC_VERIFICATION_ERROR}
            if student.email_verified_at is None:
                student.password_hash = hash_password(data.new_password)
                student.email_verified_at = now
                student.auth_token_version = (student.auth_token_version or 0) + 1
            if token.event_id is not None:
                event_access_granted = _activate_event_membership(
                    db, student, token.event_id, normalize_email(student.email), now
                )

        token.used_at = now
        db.query(EmailVerificationToken).filter(
            EmailVerificationToken.student_code == student.student_code,
            EmailVerificationToken.id != token.id,
            EmailVerificationToken.used_at.is_(None),
        ).update({EmailVerificationToken.used_at: now}, synchronize_session=False)
        _mark_verification_attempt(
            db,
            request,
            success=True,
            principal=principal,
            student_code=student.student_code,
            event_id=token.event_id,
        )
        db.commit()
        message = "E-mail confirmado. Agora voce ja pode entrar."
        if token.event_id is not None and not event_access_granted:
            message = "E-mail confirmado. O acesso ao evento precisa de um convite ativo."
        return {
            "success": True,
            "message": message,
            "event_access_granted": event_access_granted,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/auth/forgot-password")
def forgot_password(data: ForgotPasswordRequest, request: Request):
    """Sempre responde genericamente para nao enumerar contas ou convites."""

    auth_secret()
    email = normalize_email(data.email)
    db = SessionLocal()
    try:
        student = db.query(Student).filter(func.lower(Student.email) == email).first()
        event = _event_for_request(db, data.event_slug) if data.event_slug else None
        event_data = None
        allowed = bool(student and student.email_verified_at is not None)
        if allowed and event:
            allowed = student_has_active_event_membership(db, student, event.id) or is_admin_email(student.email)
            event_data = _event_dict(event) if allowed else None
        elif allowed and data.event_slug:
            allowed = False
        elif allowed and not is_admin_email(student.email) and has_event_scope(db, student):
            allowed = False

        if allowed and student:
            now = datetime.utcnow()
            db.query(PasswordResetToken).filter(
                PasswordResetToken.student_code == student.student_code,
                PasswordResetToken.used_at.is_(None),
            ).update({PasswordResetToken.used_at: now}, synchronize_session=False)
            raw_token = secrets.token_urlsafe(32)
            ttl = _configuration_int(
                "PASSWORD_RESET_TOKEN_TTL_MINUTES", 60, minimum=5, maximum=24 * 60
            )
            db.add(
                PasswordResetToken(
                    student_code=student.student_code,
                    token_hash=_reset_token_hash(raw_token),
                    expires_at=now + timedelta(minutes=ttl),
                    created_at=now,
                )
            )
            record_access_event(
                db,
                request,
                "password_reset_requested",
                success=True,
                student_code=student.student_code,
                event_id=event.id if event else None,
                route="/auth/forgot-password",
            )
            db.commit()
            reset_url = f"{_public_app_url(event_data)}?reset_token={raw_token}"
            sent, _ = send_email(
                student.email,
                "Redefinicao de senha - IACLUBE LMS",
                f"Ola, {student.name}! Use este link para criar uma nova senha: {reset_url}\n\n"
                f"O link expira em {ttl} minutos.",
                f"<p>Ola, {student.name}!</p><p>Use o link abaixo para criar uma nova senha. "
                f"Ele expira em {ttl} minutos.</p><p><a href=\"{reset_url}\">Redefinir senha</a></p>",
            )
            _record_email_result("password_reset_email", sent, student.student_code, event_data)
        else:
            record_access_event(
                db,
                request,
                "password_reset_requested",
                success=False,
                student_code=_verification_principal(email),
                route="/auth/forgot-password",
            )
            db.commit()
        return _verification_request_response()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/auth/reset-password")
def reset_password(data: ResetPasswordRequest, request: Request):
    if len(data.new_password) < 6:
        return {"success": False, "message": "A nova senha precisa ter pelo menos 6 caracteres."}

    db = SessionLocal()
    try:
        token = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == _reset_token_hash(data.token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at >= datetime.utcnow(),
        ).first()
        if not token:
            record_access_event(db, request, "password_reset_completed", success=False, route="/auth/reset-password")
            db.commit()
            return {"success": False, "message": "Este link de recuperacao e invalido ou expirou."}

        student = db.query(Student).filter(Student.student_code == token.student_code).first()
        if not student:
            token.used_at = datetime.utcnow()
            db.commit()
            return {"success": False, "message": "Este link de recuperacao e invalido ou expirou."}

        now = datetime.utcnow()
        token.used_at = now
        student.password_hash = hash_password(data.new_password)
        # A recuperacao entregue no proprio endereco tambem e prova de posse,
        # mas nunca cria membership de evento por coincidencia de e-mail.
        student.email_verified_at = now
        student.auth_token_version = (student.auth_token_version or 0) + 1
        record_access_event(
            db,
            request,
            "password_reset_completed",
            success=True,
            student_code=student.student_code,
            route="/auth/reset-password",
        )
        db.commit()
        return {"success": True, "message": "Senha redefinida. Entre com a nova senha."}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/auth/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    if current_user.student_code != data.student_code:
        raise HTTPException(status_code=403, detail="Voce nao pode alterar a senha de outra pessoa.")
    if len(data.new_password) < 6:
        return {"success": False, "message": "A nova senha precisa ter pelo menos 6 caracteres."}

    db = SessionLocal()
    try:
        student = db.query(Student).filter(Student.student_code == data.student_code).first()
        if not student:
            return {"success": False, "message": "Aluno nao encontrado."}
        if not verify_password(data.current_password, student.password_hash):
            return {"success": False, "message": "Senha atual incorreta."}
        student.password_hash = hash_password(data.new_password)
        student.auth_token_version = (student.auth_token_version or 0) + 1
        db.commit()
        access_token = create_access_token(student, current_user.active_event_id)
        return {
            "success": True,
            "message": "Senha alterada com sucesso.",
            "access_token": access_token,
            "token_type": "bearer",
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/auth/change-email")
def change_email(
    data: ChangeEmailRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Mantem o endereco atual ate o novo titular confirmar o link."""

    target_email = normalize_email(data.new_email)
    db = SessionLocal()
    try:
        student = db.query(Student).filter(Student.student_code == current_user.student_code).first()
        if not student or not verify_password(data.current_password, student.password_hash):
            return {"success": False, "message": "Nao foi possivel solicitar a alteracao de e-mail."}
        if not target_email or target_email == normalize_email(student.email) or is_admin_email(target_email):
            return {"success": False, "message": "Nao foi possivel solicitar a alteracao de e-mail."}
        duplicate = db.query(Student).filter(
            func.lower(Student.email) == target_email,
            Student.student_code != student.student_code,
        ).first()
        if duplicate:
            return {"success": False, "message": "Nao foi possivel solicitar a alteracao de e-mail."}

        maximum, window_seconds = _verification_request_policy()
        principal = _verification_principal(
            f"email-change:{student.student_code}:{target_email}"
        )
        if _verification_rate_limited(
            db,
            request,
            event_type="email_change_requested",
            principal=principal,
            maximum=maximum,
            window_seconds=window_seconds,
        ):
            record_access_event(
                db,
                request,
                "email_verification_rate_limited",
                success=False,
                student_code=principal,
                route="/auth/change-email",
            )
            db.commit()
            return _rate_limited_response(window_seconds)

        raw_token, _ = _issue_verification_token(
            db,
            student=student,
            email=target_email,
            purpose="email_change",
            event_id=None,
        )
        record_access_event(
            db,
            request,
            "email_change_requested",
            success=True,
            student_code=principal,
            route="/auth/change-email",
        )
        db.commit()
        _send_verification_email(
            email=target_email,
            name=student.name,
            student_code=student.student_code,
            raw_token=raw_token,
            event=None,
            purpose="email_change",
        )
        return _verification_request_response()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
