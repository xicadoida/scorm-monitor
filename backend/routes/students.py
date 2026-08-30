from datetime import datetime

from fastapi import APIRouter, Depends

from database import SessionLocal
from models import Student, Enrollment, CourseSession, ClassStudent, RegistrationProfile
from schemas import (
    StudentCreateRequest,
    StudentUpdateRequest,
    AdminResetPasswordRequest,
    DeleteAccountRequest,
)
from security import hash_password, verify_password
from event_utils import get_event_for_email
from auth_utils import CurrentUser, require_admin, require_self_or_admin

router = APIRouter()


@router.post("/students")
def create_student(data: StudentCreateRequest, _: CurrentUser = Depends(require_admin)):
    db = SessionLocal()

    student = Student(
        student_code=data.student_code,
        name=data.name,
        email=data.email,
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

    result = [
        {
            "id": s.id,
            "student_code": s.student_code,
            "name": s.name,
            "email": s.email,
            "person_type": profiles.get(s.student_code).person_type if s.student_code in profiles else "not_informed",
            "accepted_terms_at": profiles.get(s.student_code).accepted_terms_at if s.student_code in profiles else None,
            "event": get_event_for_email(db, s.email)
        }
        for s in students
    ]

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
    db.query(Enrollment).filter(
        Enrollment.student_code == student_code
    ).delete()

    db.query(CourseSession).filter(
        CourseSession.student_id == student_code
    ).delete()

    db.query(ClassStudent).filter(
        ClassStudent.student_code == student_code
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
