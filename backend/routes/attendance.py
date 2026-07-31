from datetime import datetime, date as date_cls

from fastapi import APIRouter

from database import SessionLocal
from models import (
    AttendanceModule,
    AttendanceModulePart,
    AttendanceRecord,
    Course,
    Student
)
from schemas import (
    AttendanceModuleCreateRequest,
    AttendanceModuleUpdateRequest,
    AttendanceModulePartCreateRequest,
    AttendanceModulePartUpdateRequest,
    AttendanceRecordUpdateRequest
)
from event_utils import get_event_for_email

router = APIRouter()


def _parse_date(value):
    if not value:
        return None

    try:
        return date_cls.fromisoformat(value)
    except ValueError:
        return None


def _serialize_part(part, course_titles):
    return {
        "id": part.id,
        "module_id": part.module_id,
        "course_code": part.course_code,
        "label": part.label or course_titles.get(part.course_code, "Parte"),
        "date": part.date.isoformat() if part.date else None,
        "position": part.position
    }


@router.post("/attendance/modules")
def create_module(data: AttendanceModuleCreateRequest):
    db = SessionLocal()

    module = AttendanceModule(
        name=data.name,
        event_id=data.event_id,
        position=data.position or 0,
        created_at=datetime.utcnow()
    )

    db.add(module)
    db.commit()
    db.refresh(module)
    db.close()

    return {"id": module.id, "name": module.name, "event_id": module.event_id}


@router.get("/attendance/modules")
def list_modules(event_id: int = None):
    db = SessionLocal()

    query = db.query(AttendanceModule)

    if event_id is not None:
        query = query.filter(AttendanceModule.event_id == event_id)

    modules = query.order_by(AttendanceModule.position).all()

    courses = db.query(Course).all()
    course_titles = {c.course_code: c.title for c in courses}

    result = []

    for module in modules:
        parts = db.query(AttendanceModulePart).filter(
            AttendanceModulePart.module_id == module.id
        ).order_by(AttendanceModulePart.position).all()

        result.append({
            "id": module.id,
            "name": module.name,
            "event_id": module.event_id,
            "position": module.position,
            "parts": [_serialize_part(p, course_titles) for p in parts]
        })

    db.close()
    return result


@router.put("/attendance/modules/{module_id}")
def update_module(module_id: int, data: AttendanceModuleUpdateRequest):
    db = SessionLocal()

    module = db.query(AttendanceModule).filter(
        AttendanceModule.id == module_id
    ).first()

    if not module:
        db.close()
        return {"success": False, "message": "Módulo não encontrado."}

    if data.name is not None:
        module.name = data.name

    if data.event_id is not None:
        module.event_id = None if data.event_id == 0 else data.event_id

    if data.position is not None:
        module.position = data.position

    db.commit()
    db.close()

    return {"success": True}


@router.delete("/attendance/modules/{module_id}")
def delete_module(module_id: int):
    db = SessionLocal()

    part_ids = [
        p.id for p in db.query(AttendanceModulePart).filter(
            AttendanceModulePart.module_id == module_id
        ).all()
    ]

    if part_ids:
        db.query(AttendanceRecord).filter(
            AttendanceRecord.part_id.in_(part_ids)
        ).delete(synchronize_session=False)

    db.query(AttendanceModulePart).filter(
        AttendanceModulePart.module_id == module_id
    ).delete()

    db.query(AttendanceModule).filter(
        AttendanceModule.id == module_id
    ).delete()

    db.commit()
    db.close()

    return {"success": True}


@router.post("/attendance/modules/{module_id}/parts")
def create_part(module_id: int, data: AttendanceModulePartCreateRequest):
    db = SessionLocal()

    module = db.query(AttendanceModule).filter(
        AttendanceModule.id == module_id
    ).first()

    if not module:
        db.close()
        return {"success": False, "message": "Módulo não encontrado."}

    part = AttendanceModulePart(
        module_id=module_id,
        course_code=data.course_code,
        label=data.label,
        date=_parse_date(data.date),
        position=data.position or 0
    )

    db.add(part)
    db.commit()
    db.refresh(part)
    db.close()

    return {"success": True, "id": part.id}


@router.put("/attendance/parts/{part_id}")
def update_part(part_id: int, data: AttendanceModulePartUpdateRequest):
    db = SessionLocal()

    part = db.query(AttendanceModulePart).filter(
        AttendanceModulePart.id == part_id
    ).first()

    if not part:
        db.close()
        return {"success": False, "message": "Parte não encontrada."}

    if data.course_code is not None:
        part.course_code = data.course_code

    if data.label is not None:
        part.label = data.label

    if data.date is not None:
        part.date = _parse_date(data.date)

    if data.position is not None:
        part.position = data.position

    db.commit()
    db.close()

    return {"success": True}


@router.delete("/attendance/parts/{part_id}")
def delete_part(part_id: int):
    db = SessionLocal()

    db.query(AttendanceRecord).filter(
        AttendanceRecord.part_id == part_id
    ).delete()

    db.query(AttendanceModulePart).filter(
        AttendanceModulePart.id == part_id
    ).delete()

    db.commit()
    db.close()

    return {"success": True}


def _compute_stats(statuses):
    presentes = sum(1 for s in statuses if s in ("presente", "justificada"))
    faltas = sum(1 for s in statuses if s == "falta")
    a_realizar = sum(1 for s in statuses if s == "a_realizar")

    realizados = presentes + faltas
    frequencia = round((presentes / realizados) * 100) if realizados > 0 else None

    return {
        "frequencia": frequencia,
        "presencas": presentes,
        "faltas": faltas,
        "a_realizar": a_realizar
    }


@router.get("/attendance/students/{student_code}")
def get_student_attendance(student_code: str):
    db = SessionLocal()

    student = db.query(Student).filter(
        Student.student_code == student_code
    ).first()

    if not student:
        db.close()
        return {"success": False, "message": "Aluno não encontrado."}

    student_event = get_event_for_email(db, student.email)
    student_event_id = student_event["id"] if student_event else None

    # Aluno vê os módulos globais (sem evento) e, se for de um evento,
    # também os módulos criados especificamente pra esse evento.
    query = db.query(AttendanceModule).filter(
        (AttendanceModule.event_id.is_(None)) |
        (AttendanceModule.event_id == student_event_id)
    )

    modules = query.order_by(AttendanceModule.position).all()

    courses = db.query(Course).all()
    course_titles = {c.course_code: c.title for c in courses}

    records = db.query(AttendanceRecord).filter(
        AttendanceRecord.student_code == student_code
    ).all()

    records_by_part = {r.part_id: r.status for r in records}

    all_statuses = []
    result_modules = []

    for module in modules:
        parts = db.query(AttendanceModulePart).filter(
            AttendanceModulePart.module_id == module.id
        ).order_by(AttendanceModulePart.position).all()

        part_results = []
        module_statuses = []

        for part in parts:
            status = records_by_part.get(part.id, "a_realizar")
            module_statuses.append(status)
            all_statuses.append(status)

            part_data = _serialize_part(part, course_titles)
            part_data["status"] = status
            part_results.append(part_data)

        module_stats = _compute_stats(module_statuses)

        result_modules.append({
            "id": module.id,
            "name": module.name,
            "parts": part_results,
            "percent": module_stats["frequencia"]
        })

    db.close()

    overall_stats = _compute_stats(all_statuses)

    return {
        "success": True,
        "student": {
            "name": student.name,
            "email": student.email
        },
        "stats": overall_stats,
        "modules": result_modules
    }


@router.put("/attendance/students/{student_code}/parts/{part_id}")
def set_attendance_status(
    student_code: str,
    part_id: int,
    data: AttendanceRecordUpdateRequest
):
    valid_statuses = ("presente", "falta", "justificada", "a_realizar")

    if data.status not in valid_statuses:
        return {"success": False, "message": "Status inválido."}

    db = SessionLocal()

    record = db.query(AttendanceRecord).filter(
        AttendanceRecord.student_code == student_code,
        AttendanceRecord.part_id == part_id
    ).first()

    if record:
        record.status = data.status
        record.updated_at = datetime.utcnow()
    else:
        record = AttendanceRecord(
            student_code=student_code,
            part_id=part_id,
            status=data.status,
            updated_at=datetime.utcnow()
        )
        db.add(record)

    db.commit()
    db.close()

    return {"success": True}