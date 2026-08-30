from datetime import datetime
from fastapi import APIRouter, Depends

from database import SessionLocal
from models import ClassGroup, ClassStudent
from models import Enrollment
from schemas import ClassCreateRequest, AddStudentsToClassRequest
from auth_utils import CurrentUser, require_admin

router = APIRouter()


@router.post("/classes")
def create_class(data: ClassCreateRequest, _: CurrentUser = Depends(require_admin)):
    db = SessionLocal()

    class_group = ClassGroup(
        name=data.name,
        created_at=datetime.utcnow()
    )

    db.add(class_group)
    db.commit()
    db.refresh(class_group)
    db.close()

    return {
        "success": True,
        "id": class_group.id,
        "name": class_group.name
    }


@router.get("/classes")
def list_classes(_: CurrentUser = Depends(require_admin)):
    db = SessionLocal()

    classes = db.query(ClassGroup).all()

    result = [
        {
            "id": c.id,
            "name": c.name,
            "created_at": c.created_at
        }
        for c in classes
    ]

    db.close()

    return result


@router.post("/classes/{class_id}/students")
def add_students_to_class(
    class_id: int,
    data: AddStudentsToClassRequest,
    _: CurrentUser = Depends(require_admin),
):
    db = SessionLocal()

    added = 0

    for student_code in data.student_codes:
        exists = db.query(ClassStudent).filter(
            ClassStudent.class_id == class_id,
            ClassStudent.student_code == student_code
        ).first()

        if exists:
            continue

        relation = ClassStudent(
            class_id=class_id,
            student_code=student_code
        )

        db.add(relation)
        added += 1

    db.commit()
    db.close()

    return {
        "success": True,
        "added": added
    }


@router.get("/classes/{class_id}/students")
def list_class_students(class_id: int, _: CurrentUser = Depends(require_admin)):
    db = SessionLocal()

    students = db.query(ClassStudent).filter(
        ClassStudent.class_id == class_id
    ).all()

    result = [
        {
            "id": s.id,
            "class_id": s.class_id,
            "student_code": s.student_code
        }
        for s in students
    ]

    db.close()

    return result
@router.get("/classes/{class_id}/student-codes")
def get_class_student_codes(class_id: int, _: CurrentUser = Depends(require_admin)):
    db = SessionLocal()

    students = db.query(ClassStudent).filter(
        ClassStudent.class_id == class_id
    ).all()

    result = [s.student_code for s in students]

    db.close()

    return result

@router.post("/classes/{class_id}/enroll")
def enroll_class(class_id: int, data: dict, _: CurrentUser = Depends(require_admin)):
    db = SessionLocal()

    course_code = data.get("course_code")

    students = db.query(ClassStudent).filter(
        ClassStudent.class_id == class_id
    ).all()

    added = 0
    skipped = 0

    for student in students:

        existing = db.query(Enrollment).filter(
            Enrollment.student_code == student.student_code,
            Enrollment.course_code == course_code,
            Enrollment.active == True
        ).first()

        if existing:
            skipped += 1
            continue

        enrollment = Enrollment(
            student_code=student.student_code,
            course_code=course_code,
            active=True,
            assigned_at=datetime.utcnow()
        )

        db.add(enrollment)
        added += 1

    db.commit()
    db.close()

    return {
        "success": True,
        "added": added,
        "skipped": skipped
    }
