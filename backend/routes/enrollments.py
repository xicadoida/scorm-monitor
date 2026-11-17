from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from database import SessionLocal
from models import Enrollment, Course, Student
from schemas import EnrollmentCreateRequest
from event_utils import (
    course_is_available_for_event,
    student_can_access_course,
)
from auth_utils import CurrentUser, get_current_user, require_admin, require_self_or_admin

router = APIRouter()


@router.post("/enrollments")
def create_enrollment(data: EnrollmentCreateRequest, _: CurrentUser = Depends(require_admin)):
    db = SessionLocal()

    enrollment = Enrollment(
        student_code=data.student_code,
        course_code=data.course_code,
        active=True,
        assigned_at=datetime.utcnow()
    )

    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    db.close()

    return {
        "id": enrollment.id,
        "student_code": enrollment.student_code,
        "course_code": enrollment.course_code,
        "active": enrollment.active
    }


@router.post("/students/{student_code}/enroll/{course_code}")
def self_enroll(
    student_code: str,
    course_code: str,
    current_user: CurrentUser = Depends(require_self_or_admin),
):
    db = SessionLocal()

    student = db.query(Student).filter(
        Student.student_code == student_code
    ).first()

    if not student:
        db.close()
        return {"success": False, "message": "Aluno não encontrado."}

    course = db.query(Course).filter(
        Course.course_code == course_code,
        Course.active == True
    ).first()

    if not course:
        db.close()
        return {"success": False, "message": "Curso não encontrado."}

    # A regra vale nos dois sentidos: uma conta de evento não pode usar uma
    # matrícula direta para entrar no catálogo padrão, e uma conta padrão não
    # pode entrar em curso de evento.
    if not current_user.is_admin and not student_can_access_course(
        db, student, course, current_user.active_event_id
    ):
        db.close()
        raise HTTPException(status_code=403, detail="Você não tem acesso a esse curso.")

    existing = db.query(Enrollment).filter(
        Enrollment.student_code == student_code,
        Enrollment.course_code == course_code
    ).first()

    if existing:
        existing.active = True
        db.commit()
        db.close()
        return {"success": True, "message": "Inscrição confirmada."}

    enrollment = Enrollment(
        student_code=student_code,
        course_code=course_code,
        active=True,
        assigned_at=datetime.utcnow()
    )

    db.add(enrollment)
    db.commit()
    db.close()

    return {"success": True, "message": "Inscrição realizada com sucesso."}


@router.get("/students/{student_code}/courses")
def get_student_courses(
    student_code: str,
    current_user: CurrentUser = Depends(require_self_or_admin),
):
    db = SessionLocal()

    enrollments = db.query(Enrollment).filter(
        Enrollment.student_code == student_code,
        Enrollment.active == True
    ).all()

    course_codes = [e.course_code for e in enrollments]

    courses = db.query(Course).filter(
        Course.course_code.in_(course_codes),
        Course.active == True
    ).all()

    # Administradores podem auditar todas as matrículas. Para alunos, a
    # visibilidade acompanha a afiliação atual do evento, inclusive quando
    # restaram matrículas legadas de outro escopo.
    if not current_user.is_admin:
        student = db.query(Student).filter(
            Student.student_code == student_code
        ).first()
        courses = [
            course for course in courses
            if course_is_available_for_event(course, current_user.active_event_id)
        ]

    result = [
        {
            "id": c.id,
            "title": c.title,
            "course_code": c.course_code,
            "scorm_path": c.scorm_path,
            "active": c.active,
            "color_primary": c.color_primary
        }
        for c in courses
    ]

    db.close()

    return result
