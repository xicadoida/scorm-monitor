import uuid
from fastapi import APIRouter
from pydantic import BaseModel

from database import SessionLocal
from models import Student
from security import hash_password, verify_password

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


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
            "message": "Aluno não encontrado."
        }

    if not verify_password(data.password, student.password_hash):
        return {
            "success": False,
            "message": "Senha incorreta."
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

    student = Student(
        student_code=f"aluno_{uuid.uuid4().hex[:8]}",
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password)
    )

    db.add(student)
    db.commit()
    db.refresh(student)
    db.close()

    return {
        "success": True,
        "student": {
            "id": student.id,
            "student_code": student.student_code,
            "name": student.name,
            "email": student.email
        }
    }