from datetime import datetime, date as date_cls

from fastapi import APIRouter

from database import SessionLocal
from models import (
    AttendanceModule,
    AttendanceModulePart,
    AttendanceRecord,
    Course,
    CourseSession,
    EventEmail,
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
    presentes = sum(1 for s in statuses if s in ("presente", "justificada", "atividade_substitutiva"))
    faltas = sum(1 for s in statuses if s == "falta")
    a_realizar = sum(1 for s in statuses if s == "a_realizar")

    # Aulas ainda pendentes entram no total esperado, mas nunca como presença.
    # Assim, 1 presença e 1 aula a realizar resultam em 50% de frequência.
    total_partes = presentes + faltas + a_realizar
    frequencia = round((presentes / total_partes) * 100) if total_partes > 0 else None

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
    passed_course_codes = {
        session.course_id for session in db.query(CourseSession).filter(
            CourseSession.student_id == student_code,
            CourseSession.status == "passed"
        ).all()
    }

    all_statuses = []
    result_modules = []

    for module in modules:
        parts = db.query(AttendanceModulePart).filter(
            AttendanceModulePart.module_id == module.id
        ).order_by(AttendanceModulePart.position).all()

        part_results = []
        module_statuses = []

        for part in parts:
            # A presença lançada pela equipe sempre tem prioridade. Sem ela,
            # aprovação no curso vinculado à parte vale como atividade
            # substitutiva, mas não altera o registro manual no banco.
            manual_status = records_by_part.get(part.id, "a_realizar")
            if manual_status in ("presente", "justificada", "falta"):
                status = manual_status
            elif part.course_code and part.course_code in passed_course_codes:
                status = "atividade_substitutiva"
            else:
                status = manual_status
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


@router.get("/attendance/event-progress")
def get_event_progress(event_id: int):
    """Acompanhamento de atividades substitutivas por aluno e módulo."""
    db = SessionLocal()
    event_emails = {
        entry.email.lower() for entry in db.query(EventEmail).filter(
            EventEmail.event_id == event_id
        ).all()
    }
    students = [student for student in db.query(Student).all() if student.email.lower() in event_emails]
    student_codes = [student.student_code for student in students]

    modules = db.query(AttendanceModule).filter(
        (AttendanceModule.event_id.is_(None)) |
        (AttendanceModule.event_id == event_id)
    ).order_by(AttendanceModule.position).all()
    parts_with_courses = []
    for module in modules:
        for part in db.query(AttendanceModulePart).filter(
            AttendanceModulePart.module_id == module.id,
            AttendanceModulePart.course_code.isnot(None)
        ).order_by(AttendanceModulePart.position).all():
            parts_with_courses.append((module, part))

    course_codes = [part.course_code for _, part in parts_with_courses]
    sessions = db.query(CourseSession).filter(
        CourseSession.student_id.in_(student_codes),
        CourseSession.course_id.in_(course_codes)
    ).all() if student_codes and course_codes else []
    sessions_by_student_course = {}
    for session in sessions:
        key = (session.student_id, session.course_id)
        sessions_by_student_course.setdefault(key, []).append(session)

    part_ids = [part.id for _, part in parts_with_courses]
    records = db.query(AttendanceRecord).filter(
        AttendanceRecord.student_code.in_(student_codes),
        AttendanceRecord.part_id.in_(part_ids)
    ).all() if student_codes and part_ids else []
    records_by_key = {(record.student_code, record.part_id): record.status for record in records}

    rows = []
    for student in students:
        for module, part in parts_with_courses:
            attempts = sessions_by_student_course.get((student.student_code, part.course_code), [])
            if not attempts:
                continue
            state = "concluído" if any(attempt.status == "passed" for attempt in attempts) else "em andamento"
            manual_status = records_by_key.get((student.student_code, part.id), "a_realizar")
            rows.append({
                "student_code": student.student_code,
                "name": student.name,
                "email": student.email,
                "module": module.name,
                "date": part.date.isoformat() if part.date else None,
                "state": state,
                "attendance_class": "presente" if manual_status in ("presente", "justificada") else "não lançada"
            })

    db.close()
    return {"success": True, "rows": rows}


@router.get("/attendance/reports")
def get_attendance_report(
    event_id: int = None,
    start_date: str = None,
    end_date: str = None
):
    """Relatório consolidado de presença para alunos e partes de um período."""
    db = SessionLocal()
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    students_query = db.query(Student)
    if event_id is not None:
        event_emails = [
            entry.email.lower() for entry in db.query(EventEmail).filter(
                EventEmail.event_id == event_id
            ).all()
        ]
        students = [
            student for student in students_query.all()
            if student.email.lower() in event_emails
        ]
    else:
        students = students_query.all()

    modules_query = db.query(AttendanceModule)
    if event_id is not None:
        modules_query = modules_query.filter(
            (AttendanceModule.event_id.is_(None)) |
            (AttendanceModule.event_id == event_id)
        )
    modules = modules_query.order_by(AttendanceModule.position).all()

    report_parts = []
    for module in modules:
        parts = db.query(AttendanceModulePart).filter(
            AttendanceModulePart.module_id == module.id
        ).order_by(AttendanceModulePart.position).all()
        for part in parts:
            if start and part.date and part.date < start:
                continue
            if end and part.date and part.date > end:
                continue
            report_parts.append((module, part))

    student_codes = [student.student_code for student in students]
    part_ids = [part.id for _, part in report_parts]
    records = db.query(AttendanceRecord).filter(
        AttendanceRecord.student_code.in_(student_codes),
        AttendanceRecord.part_id.in_(part_ids)
    ).all() if student_codes and part_ids else []
    records_by_key = {(record.student_code, record.part_id): record for record in records}
    course_codes = [part.course_code for _, part in report_parts if part.course_code]
    passed_sessions = db.query(CourseSession).filter(
        CourseSession.student_id.in_(student_codes),
        CourseSession.course_id.in_(course_codes),
        CourseSession.status == "passed"
    ).all() if student_codes and course_codes else []
    passed_courses_by_student = {}
    for session in passed_sessions:
        key = (session.student_id, session.course_id)
        existing = passed_courses_by_student.get(key)
        if not existing or (session.completed_at or session.updated_at) > (existing.completed_at or existing.updated_at):
            passed_courses_by_student[key] = session

    rows = []
    for student in students:
        row_attendance = []
        manual_count = 0
        substitute_count = 0
        for module, part in report_parts:
            record = records_by_key.get((student.student_code, part.id))
            manual_status = record.status if record else "a_realizar"
            passed_session = passed_courses_by_student.get((student.student_code, part.course_code)) if part.course_code else None
            presence_entries = []
            if manual_status in ("presente", "justificada"):
                manual_date = datetime.combine(part.date, datetime.min.time()) if part.date else record.updated_at
                presence_entries.append({
                    "source": "manual",
                    "received_at": manual_date.isoformat() if manual_date else None
                })
            if passed_session:
                # O relatório é organizado pela data da aula/parte. Se ela
                # não foi configurada, cai para a data da conclusão.
                automatic_date = (
                    datetime.combine(part.date, datetime.min.time())
                    if part.date else (passed_session.completed_at or passed_session.updated_at)
                )
                presence_entries.append({
                    "source": "atividade_substitutiva",
                    "received_at": automatic_date.isoformat() if automatic_date else None
                })
            if manual_status in ("presente", "justificada", "falta"):
                status = manual_status
                source = "manual" if manual_status in ("presente", "justificada") else None
                # Para presença manual, a data relevante no relatório é a
                # data da aula/parte. O horário do lançamento só é usado
                # quando a parte ainda não tem uma data configurada.
                received_at = (
                    datetime.combine(part.date, datetime.min.time())
                    if source and part.date
                    else (record.updated_at if source else None)
                )
            elif passed_session:
                status = "atividade_substitutiva"
                source = "atividade_substitutiva"
                passed_session = passed_courses_by_student[(student.student_code, part.course_code)]
                received_at = passed_session.completed_at or passed_session.updated_at
            else:
                status = manual_status
                source = None
                received_at = None
            manual_count += source == "manual"
            substitute_count += source == "atividade_substitutiva"
            row_attendance.append({
                "module": module.name,
                "part_id": part.id,
                "label": part.label,
                "date": part.date.isoformat() if part.date else None,
                "status": status,
                "source": source,
                "received_at": received_at.isoformat() if received_at else None,
                "presence_entries": presence_entries
            })

        row_statuses = [item["status"] for item in row_attendance]
        rows.append({
            "student_code": student.student_code,
            "name": student.name,
            "email": student.email,
            "stats": _compute_stats(row_statuses),
            "sources": {"manual": manual_count, "atividade_substitutiva": substitute_count},
            "attendance": row_attendance
        })

    db.close()
    return {
        "success": True,
        "period": {"start_date": start_date, "end_date": end_date},
        "parts": [
            {"module": module.name, "id": part.id, "label": part.label, "date": part.date.isoformat() if part.date else None}
            for module, part in report_parts
        ],
        "students": rows
    }
