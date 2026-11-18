from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from database import SessionLocal
from models import CourseSession, Student, Course, Enrollment, Event
from schemas import (
    SessionStartRequest,
    SessionUpdateRequest
)
from auth_utils import CurrentUser, get_current_user, require_admin
from event_utils import student_can_access_course

router = APIRouter()


def _has_active_course_access(
    db, student_code: str, course_code: str, active_event_id: int | None
) -> bool:
    """Confere matrícula, curso ativo e escopo de evento no servidor."""

    student = db.query(Student).filter(
        Student.student_code == student_code
    ).first()
    course = db.query(Course).filter(
        Course.course_code == course_code
    ).first()
    if not student_can_access_course(db, student, course, active_event_id):
        return False

    enrollment = db.query(Enrollment).filter(
        Enrollment.student_code == student_code,
        Enrollment.course_code == course_code,
        Enrollment.active == True,
    ).first()
    return enrollment is not None


def _has_active_session_entities(db, student_code: str, course_code: str) -> bool:
    """Impede que uma sessão nova seja criada para identificadores soltos."""

    student = db.query(Student).filter(
        Student.student_code == student_code,
        Student.active.is_(True),
    ).first()
    course = db.query(Course).filter(
        Course.course_code == course_code,
        Course.active.is_(True),
    ).first()
    if not student or not course:
        return False
    return course.event_id is None or db.query(Event.id).filter(
        Event.id == course.event_id,
        Event.active.is_(True),
    ).first() is not None


@router.post("/sessions/start")
def start_session(data: SessionStartRequest, current_user: CurrentUser = Depends(get_current_user)):
    if not current_user.is_admin and current_user.student_code != data.student_id:
        raise HTTPException(status_code=403, detail="Você não pode iniciar uma sessão para outra pessoa.")

    db = SessionLocal()
    if current_user.is_admin:
        if not _has_active_session_entities(db, data.student_id, data.course_id):
            db.close()
            return {"error": "Student or course not found or inactive"}
    elif not _has_active_course_access(
        db,
        current_user.student_code,
        data.course_id,
        current_user.active_event_id,
    ):
        db.close()
        raise HTTPException(status_code=403, detail="Você não tem acesso a este curso.")

    session = CourseSession(
        student_id=data.student_id,
        course_id=data.course_id,
        status="incomplete",
        completed=False,
        started_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db.add(session)
    db.commit()
    db.refresh(session)
    db.close()

    return {
        "session_id": session.id,
        "student_id": session.student_id,
        "course_id": session.course_id
    }


@router.post("/sessions/{session_id}/update")
def update_session(
    session_id: int,
    data: SessionUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    db = SessionLocal()

    session = db.query(CourseSession).filter(CourseSession.id == session_id).first()

    if not session:
        db.close()
        return {"error": "Session not found"}

    if not current_user.is_admin and current_user.student_code != session.student_id:
        db.close()
        raise HTTPException(status_code=403, detail="Você não pode alterar esta sessão.")

    if not current_user.is_admin and not _has_active_course_access(
        db,
        current_user.student_code,
        session.course_id,
        current_user.active_event_id,
    ):
        db.close()
        raise HTTPException(status_code=403, detail="Você não tem acesso a este curso.")

    if data.status is not None:
        # O SCORM pode informar "completed" antes de o questionário ser
        # corrigido. Somente aprovação encerra o acesso do aluno ao curso.
        if data.status == "passed":
            session.status = "passed"
            session.completed = True
            session.completed_at = datetime.utcnow()
        elif data.status == "failed":
            session.completed = False
            session.completed_at = None
            if session.status != "passed":
                session.status = "failed"
        elif not (data.status == "completed" and session.status == "passed"):
            session.status = data.status

    if data.session_time is not None:
        session.session_time = data.session_time

    if data.score_raw is not None:
        session.score_raw = data.score_raw
        course = db.query(Course).filter(Course.course_code == session.course_id).first()
        passing_score = course.passing_score if course and course.passing_score is not None else 80
        # Esses SCORMs enviam nota em uma escala de 0 a 100. Como não enviam
        # "failed", a nota mínima configurada no curso decide o resultado.
        if data.score_raw >= passing_score:
            session.status = "passed"
            session.completed = True
            session.completed_at = datetime.utcnow()
        else:
            session.status = "failed"
            session.completed = False
            session.completed_at = None

    if data.completed is not None and not (session.status == "passed" and not data.completed):
        session.completed = data.completed
        if data.completed:
            session.completed_at = datetime.utcnow()

    if data.suspend_data is not None:
        session.suspend_data = data.suspend_data

    if data.lesson_location is not None:
        session.lesson_location = data.lesson_location

    session.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(session)
    db.close()

    return {"message": "Session updated"}


@router.get("/sessions")
def list_sessions(_: CurrentUser = Depends(require_admin)):
    db = SessionLocal()

    sessions = db.query(CourseSession).all()
    students = {student.student_code: student for student in db.query(Student).all()}

    result = [
        {
            "suspend_data": s.suspend_data,
            "lesson_location": s.lesson_location,
            "id": s.id,
            "student_id": s.student_id,
            "student_name": students.get(s.student_id).name if s.student_id in students else s.student_id,
            "student_email": students.get(s.student_id).email if s.student_id in students else "",
            "course_id": s.course_id,
            "status": s.status,
            "completed": s.completed,
            "session_time": s.session_time,
            "score_raw": s.score_raw,
            "started_at": s.started_at,
            "updated_at": s.updated_at,
            "completed_at": s.completed_at,
        }
        for s in sessions
    ]

    db.close()

    return result

@router.get("/progress/{student_id}/{course_id}")
def get_progress(
    student_id: str,
    course_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    if not current_user.is_admin and current_user.student_code != student_id:
        raise HTTPException(status_code=403, detail="Você não tem acesso ao progresso de outra pessoa.")

    db = SessionLocal()

    if not current_user.is_admin and not _has_active_course_access(
        db,
        current_user.student_code,
        course_id,
        current_user.active_event_id,
    ):
        db.close()
        raise HTTPException(status_code=403, detail="Você não tem acesso a este curso.")

    sessions = db.query(CourseSession).filter(
        CourseSession.student_id == student_id,
        CourseSession.course_id == course_id
    ).all()

    if not sessions:
        db.close()

        return {
            "suspend_data": "",
            "lesson_location": "",
            "student_id": student_id,
            "course_id": course_id,
            "completed": False,
            "last_status": "not_attempted",
            "sessions_count": 0,
            "access_count": 0,
            "total_session_time": ""
        }

    latest_session = max(
        sessions,
        key=lambda session: session.updated_at or session.started_at
    )

    # "completed" histórico não pode vencer uma reprovação posterior.
    # A aprovação é o único estado que libera o cartão como concluído.
    # Uma aprovação anterior permanece válida quando o aluno reabre o curso
    # para revisar ou inicia uma nova tentativa.
    completed = any(session.status == "passed" for session in sessions)

    result = {
        "suspend_data": latest_session.suspend_data,
        "lesson_location": latest_session.lesson_location,
        "student_id": student_id,
        "course_id": course_id,
        "completed": completed,
        "last_status": latest_session.status,
        "sessions_count": len(sessions),
        # Nome explícito para integrações externas. Cada sessão criada quando
        # o aluno abre o curso representa um acesso ao pacote SCORM.
        "access_count": len(sessions),
        "total_session_time": latest_session.session_time
    }

    db.close()

    return result
@router.post("/sessions/{session_id}/finish")
def finish_session(session_id: int, current_user: CurrentUser = Depends(get_current_user)):
    db = SessionLocal()

    session = db.query(CourseSession).filter(
        CourseSession.id == session_id
    ).first()

    if not session:
        db.close()
        return {"error": "Session not found"}

    if not current_user.is_admin and current_user.student_code != session.student_id:
        db.close()
        raise HTTPException(status_code=403, detail="Você não pode encerrar esta sessão.")

    if not current_user.is_admin and not _has_active_course_access(
        db,
        current_user.student_code,
        session.course_id,
        current_user.active_event_id,
    ):
        db.close()
        raise HTTPException(status_code=403, detail="Você não tem acesso a este curso.")

    session.ended_at = datetime.utcnow()
    session.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(session)
    db.close()

    return {"message": "Session finished"}
