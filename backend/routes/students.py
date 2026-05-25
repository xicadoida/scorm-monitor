from datetime import datetime

from fastapi import APIRouter

from database import SessionLocal
from models import Student
from schemas import StudentCreateRequest

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