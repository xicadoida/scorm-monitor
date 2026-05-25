from datetime import datetime

from fastapi import APIRouter

from database import SessionLocal
from models import Enrollment, Course
from schemas import EnrollmentCreateRequest

router = APIRouter()


@router.post("/enrollments")
def create_enrollment(data: EnrollmentCreateRequest):
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


@router.get("/students/{student_code}/courses")
def get_student_courses(student_code: str):
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

    result = [
        {
            "id": c.id,
            "title": c.title,
            "course_code": c.course_code,
            "scorm_path": c.scorm_path,
            "active": c.active
        }
        for c in courses
    ]

    db.close()

    return result