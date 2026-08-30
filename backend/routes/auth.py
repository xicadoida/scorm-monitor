import uuid
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func

from database import SessionLocal
from models import Student, Event, RegistrationProfile
from schemas import ChangePasswordRequest
from security import hash_password, verify_password
from event_utils import get_event_for_email
from auth_utils import CurrentUser, create_access_token, get_current_user
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
            "event": event
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

    return {
        "success": True,
        "student": {
            "id": student.id,
            "student_code": student.student_code,
            "name": student.name,
            "email": student.email,
            "event": event
        }
    }


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
