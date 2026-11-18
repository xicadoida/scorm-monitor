from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func

from database import SessionLocal
from models import (
    EmailVerificationToken,
    Enrollment,
    EventMembership,
    PasswordResetToken,
    RegistrationProfile,
    Student,
)
from schemas import (
    StudentCreateRequest,
    StudentUpdateRequest,
    AdminResetPasswordRequest,
    DeleteAccountRequest,
)
from security import hash_password, verify_password
from event_utils import get_confirmed_events_for_student, normalize_email
from auth_utils import CurrentUser, require_admin, require_self_or_admin

router = APIRouter()


@router.post("/students")
def create_student(data: StudentCreateRequest, _: CurrentUser = Depends(require_admin)):
    db = SessionLocal()

    normalized_email = normalize_email(data.email)
    duplicate = db.query(Student).filter(
        (Student.student_code == data.student_code) |
        (func.lower(func.trim(Student.email)) == normalized_email),
    ).first()
    if duplicate:
        db.close()
        return {
            "success": False,
            "message": "Já existe um registro com este código ou e-mail.",
        }

    student = Student(
        student_code=data.student_code,
        name=data.name,
        email=normalized_email,
        created_at=datetime.utcnow()
    )

    db.add(student)
    db.add(RegistrationProfile(
        student_code=student.student_code,
        person_type="not_informed",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    ))
    db.commit()
    db.refresh(student)
    db.close()

    return {
        "id": student.id,
        "student_code": student.student_code,
        "name": student.name,
        "email": student.email,
        "active": student.active,
    }


@router.get("/students")
def list_students(_: CurrentUser = Depends(require_admin)):
    db = SessionLocal()

    students = db.query(Student).all()
    profiles = {
        profile.student_code: profile
        for profile in db.query(RegistrationProfile).all()
    }

    result = []
    for student in students:
        events = get_confirmed_events_for_student(db, student)
        result.append({
            "id": student.id,
            "student_code": student.student_code,
            "name": student.name,
            "email": student.email,
            "active": student.active,
            "email_verified": student.email_verified_at is not None,
            "deactivated_at": student.deactivated_at,
            "person_type": profiles.get(student.student_code).person_type if student.student_code in profiles else "not_informed",
            "accepted_terms_at": profiles.get(student.student_code).accepted_terms_at if student.student_code in profiles else None,
            # Mantem o campo antigo somente quando nao ha ambiguidade. A lista
            # completa e a fonte correta para contas em mais de um evento.
            "event": events[0] if len(events) == 1 else None,
            "events": events,
        })

    db.close()

    return result


@router.put("/students/{student_code}")
def update_student(
    student_code: str,
    data: StudentUpdateRequest,
    _: CurrentUser = Depends(require_self_or_admin),
):
    db = SessionLocal()
    student = db.query(Student).filter(Student.student_code == student_code).first()

    if not student or not student.active:
        db.close()
        return {"success": False, "message": "Aluno não encontrado."}

    if data.name is not None:
        name = data.name.strip()
        if not name:
            db.close()
            return {"success": False, "message": "O nome não pode ficar vazio."}
        student.name = name

    db.commit()
    db.close()
    return {"success": True}


@router.post("/students/{student_code}/reset-password")
def reset_student_password(
    student_code: str,
    data: AdminResetPasswordRequest,
    _: CurrentUser = Depends(require_admin),
):
    """Redefinição feita exclusivamente pela área administrativa."""
    password = data.new_password.strip()
    if len(password) < 6:
        return {"success": False, "message": "A senha precisa ter pelo menos 6 caracteres."}

    db = SessionLocal()
    student = db.query(Student).filter(Student.student_code == student_code).first()
    if not student or not student.active:
        db.close()
        return {"success": False, "message": "Aluno não encontrado."}

    student.password_hash = hash_password(password)
    student.auth_token_version = (student.auth_token_version or 0) + 1
    db.commit()
    db.close()
    return {"success": True, "message": "Senha redefinida com sucesso."}


def _deactivate_student(db, student):
    """Revoga acesso sem apagar o histórico que usa ``student_code``.

    O banco legado não possui FKs entre os registros acadêmicos. Manter o
    aluno e seu identificador reservado é mais seguro do que apagar linhas e
    permitir que uma conta futura herde sessões, presenças ou auditoria.
    """

    now = datetime.utcnow()
    student.active = False
    student.deactivated_at = now
    student.auth_token_version = (student.auth_token_version or 0) + 1

    db.query(EventMembership).filter(
        EventMembership.student_code == student.student_code,
        EventMembership.revoked_at.is_(None),
    ).update(
        {EventMembership.status: "revoked", EventMembership.revoked_at: now},
        synchronize_session=False,
    )
    # Tokens continuam auditáveis, mas deixam de poder ser usados.
    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.student_code == student.student_code,
        EmailVerificationToken.used_at.is_(None),
    ).update({EmailVerificationToken.used_at: now}, synchronize_session=False)
    db.query(PasswordResetToken).filter(
        PasswordResetToken.student_code == student.student_code,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: now}, synchronize_session=False)

    # A matrícula permanece como histórico, mas não pode liberar novo acesso
    # caso um operador restaure a conta sem revisar os vínculos.
    db.query(Enrollment).filter(
        Enrollment.student_code == student.student_code,
        Enrollment.active.is_(True),
    ).update({Enrollment.active: False}, synchronize_session=False)

    db.commit()


@router.delete("/students/{student_code}")
def delete_student(student_code: str, _: CurrentUser = Depends(require_admin)):
    """Desativa a conta pelo admin, preservando o histórico acadêmico."""
    db = SessionLocal()

    student = db.query(Student).filter(
        Student.student_code == student_code
    ).first()

    if not student or not student.active:
        db.close()
        return {"success": False, "message": "Aluno não encontrado."}

    try:
        _deactivate_student(db, student)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return {"success": True, "message": "Conta desativada e histórico preservado."}


@router.post("/students/{student_code}/delete-account")
def self_delete_account(
    student_code: str,
    data: DeleteAccountRequest,
    _: CurrentUser = Depends(require_self_or_admin),
):
    """Auto-exclusão pelo próprio aluno, exige a senha atual como confirmação."""
    db = SessionLocal()

    student = db.query(Student).filter(
        Student.student_code == student_code
    ).first()

    if not student or not student.active:
        db.close()
        return {"success": False, "message": "Aluno não encontrado."}

    if not verify_password(data.password, student.password_hash):
        db.close()
        return {"success": False, "message": "Senha incorreta."}

    try:
        _deactivate_student(db, student)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return {"success": True, "message": "Conta desativada e histórico preservado."}
