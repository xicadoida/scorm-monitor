from datetime import datetime

from fastapi import APIRouter

from database import SessionLocal
from models import CourseSession
from schemas import (
    SessionStartRequest,
    SessionUpdateRequest
)

router = APIRouter()


@router.post("/sessions/start")
def start_session(data: SessionStartRequest):
    db = SessionLocal()

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
def update_session(session_id: int, data: SessionUpdateRequest):
    db = SessionLocal()

    session = db.query(CourseSession).filter(CourseSession.id == session_id).first()

    if not session:
        db.close()
        return {"error": "Session not found"}

    if data.status is not None:
        session.status = data.status

        if data.status in ["completed", "passed"]:
            session.completed = True
            session.completed_at = datetime.utcnow()

    if data.session_time is not None:
        session.session_time = data.session_time

    if data.completed is not None:
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
def list_sessions():
    db = SessionLocal()

    sessions = db.query(CourseSession).all()

    result = [
        {
            "suspend_data": s.suspend_data,
            "lesson_location": s.lesson_location,
            "id": s.id,
            "student_id": s.student_id,
            "course_id": s.course_id,
            "status": s.status,
            "completed": s.completed,
            "session_time": s.session_time,
            "started_at": s.started_at,
            "updated_at": s.updated_at,
            "completed_at": s.completed_at,
        }
        for s in sessions
    ]

    db.close()

    return result

@router.get("/progress/{student_id}/{course_id}")
def get_progress(student_id: str, course_id: str):
    db = SessionLocal()

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
            "total_session_time": ""
        }

    latest_session = sessions[-1]

    completed = any(s.completed for s in sessions)

    result = {
        "suspend_data": latest_session.suspend_data,
        "lesson_location": latest_session.lesson_location,
        "student_id": student_id,
        "course_id": course_id,
        "completed": completed,
        "last_status": latest_session.status,
        "sessions_count": len(sessions),
        "total_session_time": latest_session.session_time
    }

    db.close()

    return result
@router.post("/sessions/{session_id}/finish")
def finish_session(session_id: int):
    db = SessionLocal()

    session = db.query(CourseSession).filter(
        CourseSession.id == session_id
    ).first()

    if not session:
        db.close()
        return {"error": "Session not found"}

    session.ended_at = datetime.utcnow()
    session.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(session)
    db.close()

    return {"message": "Session finished"}
