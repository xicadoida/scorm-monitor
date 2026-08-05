import uuid
from fastapi import APIRouter
from pydantic import BaseModel

from database import SessionLocal
from models import Student, Event
from schemas import ChangePasswordRequest
from security import hash_password, verify_password
from event_utils import get_event_for_email

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str
    event_slug: str | None = None


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
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
def login(data: LoginRequest):
    db = SessionLocal()

    student = db.query(Student).filter(
        Student.email == data.email
    ).first()

    if not student:
        db.close()
        return {
            "success": False,
            "message": "Aluno não encontrado."
        }

    if not verify_password(data.password, student.password_hash):
        db.close()
        return {
            "success": False,
            "message": "Senha incorreta."
        }

    event = get_event_for_email(db, student.email)
    allowed, message = _check_event_access(db, student.email, data.event_slug)
    if not allowed:
        db.close()
        return {"success": False, "message": message}
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


@router.post("/auth/register")
def register(data: RegisterRequest):
    db = SessionLocal()

    existing_student = db.query(Student).filter(
        Student.email == data.email
    ).first()

    if existing_student:
        db.close()
        return {
            "success": False,
            "message": "Este email já está cadastrado."
        }

    allowed, message = _check_event_access(db, data.email, data.event_slug)
    if not allowed:
        db.close()
        return {"success": False, "message": message}

    student = Student(
        student_code=f"aluno_{uuid.uuid4().hex[:8]}",
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password)
    )

    db.add(student)
    db.commit()
    db.refresh(student)

    event = get_event_for_email(db, student.email)
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
def change_password(data: ChangePasswordRequest):
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
    db.commit()
    db.close()

    return {"success": True, "message": "Senha alterada com sucesso."}
