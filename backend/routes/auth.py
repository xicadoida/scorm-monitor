from fastapi import APIRouter
from pydantic import BaseModel

from database import SessionLocal
from models import Student

router = APIRouter()


class LoginRequest(BaseModel):
    email: str


@router.post("/auth/login")
def login(data: LoginRequest):
    db = SessionLocal()

    student = db.query(Student).filter(
        Student.email == data.email
    ).first()

    db.close()

    if not student:
        return {
            "success": False,
            "message": "Student not found"
        }

    return {
        "success": True,
        "student": {
            "id": student.id,
            "student_code": student.student_code,
            "name": student.name,
            "email": student.email
        }
    }