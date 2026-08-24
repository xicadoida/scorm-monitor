from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from catalog_utils import touch_catalog
from database import SessionLocal
from models import CatalogState, Course, Event

router = APIRouter()

CATALOG_STATUSES = {"active", "coming_soon", "completed"}
SAO_PAULO = ZoneInfo("America/Sao_Paulo")
PUBLIC_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def public_catalog_response(payload):
    """O catálogo é público e pode ser consumido por qualquer site."""
    return JSONResponse(content=payload, headers=PUBLIC_CORS_HEADERS)


def catalog_datetime(value):
    """Converte os datetimes UTC armazenados no SQLite para ISO-8601 -03:00."""
    value = value or datetime.utcnow()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(SAO_PAULO).isoformat(timespec="seconds")


def serialize_catalog_course(course, events):
    status = course.catalog_status or ("active" if course.active else "completed")
    if status not in CATALOG_STATUSES:
        status = "active"

    return {
        "event": events.get(course.event_id),
        "title": course.title,
        "tool": course.tool,
        "added_at": course.created_at.date().isoformat() if course.created_at else None,
        "duration_hours": course.duration_hours,
        "url": course.catalog_url or f"/courses/{course.course_code}",
        "status": status,
        "thumbnail_url": course.thumbnail_url,
        "short_description": course.short_description,
    }


def get_catalog_state(db):
    state = db.query(CatalogState).filter(CatalogState.id == 1).first()
    if state is None:
        state = touch_catalog(db)
        db.commit()
        db.refresh(state)
    return state


@router.get("/catalog")
def get_catalog():
    db = SessionLocal()
    try:
        state = get_catalog_state(db)
        events = {event.id: event.name for event in db.query(Event).all()}
        courses = db.query(Course).order_by(Course.created_at.desc()).all()
        return public_catalog_response({
            "updated_at": catalog_datetime(state.updated_at),
            "courses": [serialize_catalog_course(course, events) for course in courses],
        })
    finally:
        db.close()


@router.get("/catalog/last-update")
def get_catalog_last_update():
    db = SessionLocal()
    try:
        state = get_catalog_state(db)
        return public_catalog_response({"updated_at": catalog_datetime(state.updated_at)})
    finally:
        db.close()


@router.options("/catalog")
@router.options("/catalog/last-update")
def catalog_options():
    return Response(status_code=204, headers=PUBLIC_CORS_HEADERS)
