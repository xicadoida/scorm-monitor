from datetime import datetime

from fastapi import APIRouter, Depends

from database import SessionLocal
from models import (
    AttendanceRecord,
    ClassStudent,
    CourseSession,
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

    student = Student(
        student_code=data.student_code,
        name=data.name,
        email=normalize_email(data.email),
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
        "email": student.email
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
            "email_verified": student.email_verified_at is not None,
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

    if not student:
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
    if not student:
        db.close()
        return {"success": False, "message": "Aluno não encontrado."}

    student.password_hash = hash_password(password)
    student.auth_token_version = (student.auth_token_version or 0) + 1
    db.commit()
    db.close()
    return {"success": True, "message": "Senha redefinida com sucesso."}


def _delete_student_cascade(db, student_code):
    # Os identificadores nao possuem chave estrangeira no schema legado. Sem
    # esta limpeza, uma eventual reutilizacao de student_code poderia herdar
    # dados, tokens ou memberships de uma pessoa excluida.
    db.query(EventMembership).filter(
        EventMembership.student_code == student_code
    ).delete()

    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.student_code == student_code
    ).delete()

    db.query(PasswordResetToken).filter(
        PasswordResetToken.student_code == student_code
    ).delete()

    db.query(RegistrationProfile).filter(
        RegistrationProfile.student_code == student_code
    ).delete()

    db.query(Enrollment).filter(
        Enrollment.student_code == student_code
    ).delete()

    db.query(CourseSession).filter(
        CourseSession.student_id == student_code
    ).delete()

    db.query(ClassStudent).filter(
        ClassStudent.student_code == student_code
    ).delete()

    db.query(AttendanceRecord).filter(
        AttendanceRecord.student_code == student_code
    ).delete()

    db.query(Student).filter(
        Student.student_code == student_code
    ).delete()

    db.commit()


@router.delete("/students/{student_code}")
def delete_student(student_code: str, _: CurrentUser = Depends(require_admin)):
    """Exclusão pelo admin, sem exigir senha."""
    db = SessionLocal()

    student = db.query(Student).filter(
        Student.student_code == student_code
    ).first()

    if not student:
        db.close()
        return {"success": False, "message": "Aluno não encontrado."}

    _delete_student_cascade(db, student_code)
    db.close()

    return {"success": True, "message": "Aluno excluído com sucesso."}


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

    if not student:
        db.close()
        return {"success": False, "message": "Aluno não encontrado."}

    if not verify_password(data.password, student.password_hash):
        db.close()
        return {"success": False, "message": "Senha incorreta."}

    _delete_student_cascade(db, student_code)
    db.close()

    return {"success": True, "message": "Conta excluída com sucesso."}
