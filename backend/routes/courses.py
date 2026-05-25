from datetime import datetime
from fastapi import APIRouter

from database import SessionLocal
from models import Course
from schemas import CourseCreateRequest

router = APIRouter()


@router.post("/courses")
def create_course(data: CourseCreateRequest):
    db = SessionLocal()

    course = Course(
        title=data.title,
        course_code=data.course_code,
        scorm_path=data.scorm_path,
        active=True,
        created_at=datetime.utcnow()
    )

    db.add(course)
    db.commit()
    db.refresh(course)
    db.close()

    return {
        "id": course.id,
        "title": course.title,
        "course_code": course.course_code,
        "scorm_path": course.scorm_path,
        "active": course.active
    }


@router.get("/courses")
def list_courses():
    db = SessionLocal()

    courses = db.query(Course).all()

    result = [
        {
            "id": c.id,
            "title": c.title,
            "course_code": c.course_code,
            "scorm_path": c.scorm_path,
            "active": c.active,
            "created_at": c.created_at
        }
        for c in courses
    ]

    db.close()

    return result