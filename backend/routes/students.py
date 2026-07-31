from datetime import datetime

from fastapi import APIRouter

from database import SessionLocal
from models import Student, Enrollment, CourseSession, ClassStudent
from schemas import StudentCreateRequest, DeleteAccountRequest
from security import verify_password

router = APIRouter()


@router.post("/students")
def create_student(data: StudentCreateRequest):
    db = SessionLocal()

    student = Student(
        student_code=data.student_code,
        name=data.name,
        email=data.email,
        created_at=datetime.utcnow()
    )

    db.add(student)
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
def list_students():
    db = SessionLocal()

    students = db.query(Student).all()

    result = [
        {
            "id": s.id,
            "student_code": s.student_code,
            "name": s.name,
            "email": s.email
        }
        for s in students
    ]

    db.close()

    return result


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
def delete_student(student_code: str):
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
def self_delete_account(student_code: str, data: DeleteAccountRequest):
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