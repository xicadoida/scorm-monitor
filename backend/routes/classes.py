from datetime import datetime
from fastapi import APIRouter, Depends

from database import SessionLocal
from models import ClassGroup, ClassStudent, Course, Enrollment, Event, Student
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

    class_group = db.query(ClassGroup).filter(ClassGroup.id == class_id).first()
    if not class_group:
        db.close()
        return {"success": False, "message": "Turma não encontrada."}

    requested_codes = list(dict.fromkeys(data.student_codes))
    valid_codes = {
        student.student_code
        for student in db.query(Student).filter(
            Student.student_code.in_(requested_codes),
            Student.active.is_(True),
        ).all()
    }
    invalid_codes = [code for code in requested_codes if code not in valid_codes]
    if invalid_codes:
        db.close()
        return {
            "success": False,
            "message": "Um ou mais alunos não existem ou estão desativados.",
        }

    added = 0

    for student_code in requested_codes:
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

    class_group = db.query(ClassGroup).filter(ClassGroup.id == class_id).first()
    course = db.query(Course).filter(
        Course.course_code == course_code,
        Course.active.is_(True),
    ).first()
    if not class_group or not course:
        db.close()
        return {"success": False, "message": "Turma ou curso não encontrado ou inativo."}
    if course.event_id is not None and not db.query(Event.id).filter(
        Event.id == course.event_id,
        Event.active.is_(True),
    ).first():
        db.close()
        return {"success": False, "message": "O evento do curso está inativo."}

    class_students = db.query(ClassStudent).filter(
        ClassStudent.class_id == class_id
    ).all()
    student_codes = [row.student_code for row in class_students]
    active_student_codes = {
        student.student_code
        for student in db.query(Student).filter(
            Student.student_code.in_(student_codes),
            Student.active.is_(True),
        ).all()
    } if student_codes else set()

    added = 0
    skipped = 0

    for student in class_students:
        if student.student_code not in active_student_codes:
            skipped += 1
            continue

        existing = db.query(Enrollment).filter(
            Enrollment.student_code == student.student_code,
            Enrollment.course_code == course_code,
        ).first()

        if existing:
            if not existing.active:
                existing.active = True
                added += 1
                continue
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
