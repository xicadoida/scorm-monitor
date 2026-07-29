from datetime import datetime

from fastapi import APIRouter

from database import SessionLocal
from models import Event, EventEmail
from schemas import (
    EventCreateRequest,
    EventUpdateRequest,
    EventAddEmailsRequest
)

router = APIRouter()


@router.post("/events")
def create_event(data: EventCreateRequest):
    db = SessionLocal()

    event = Event(
        name=data.name,
        logo_url=data.logo_url,
        color_primary=data.color_primary,
        color_secondary=data.color_secondary,
        item_name=data.item_name,
        show_progress=data.show_progress if data.show_progress is not None else True,
        show_footer=data.show_footer if data.show_footer is not None else False,
        created_at=datetime.utcnow()
    )

    db.add(event)
    db.commit()
    db.refresh(event)
    db.close()

    return {
        "id": event.id,
        "name": event.name,
        "logo_url": event.logo_url,
        "color_primary": event.color_primary,
        "color_secondary": event.color_secondary,
        "item_name": event.item_name,
        "show_progress": event.show_progress,
        "show_footer": event.show_footer
    }


@router.get("/events")
def list_events():
    db = SessionLocal()
    events = db.query(Event).all()

    result = [
        {
            "id": e.id,
            "name": e.name,
            "logo_url": e.logo_url,
            "color_primary": e.color_primary,
            "color_secondary": e.color_secondary,
            "item_name": e.item_name,
            "show_progress": e.show_progress,
            "show_footer": e.show_footer,
            "created_at": e.created_at
        }
        for e in events
    ]

    db.close()
    return result


@router.put("/events/{event_id}")
def update_event(event_id: int, data: EventUpdateRequest):
    db = SessionLocal()

    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        db.close()
        return {"success": False, "message": "Evento não encontrado."}

    if data.name is not None:
        event.name = data.name

    if data.logo_url is not None:
        event.logo_url = data.logo_url

    if data.color_primary is not None:
        event.color_primary = data.color_primary

    if data.color_secondary is not None:
        event.color_secondary = data.color_secondary

    if data.item_name is not None:
        event.item_name = data.item_name

    if data.show_progress is not None:
        event.show_progress = data.show_progress

    if data.show_footer is not None:
        event.show_footer = data.show_footer

    db.commit()
    db.close()

    return {"success": True}


@router.delete("/events/{event_id}")
def delete_event(event_id: int):
    db = SessionLocal()

    db.query(EventEmail).filter(EventEmail.event_id == event_id).delete()
    db.query(Event).filter(Event.id == event_id).delete()

    db.commit()
    db.close()

    return {"success": True, "message": "Evento excluído."}


@router.get("/events/{event_id}/emails")
def list_event_emails(event_id: int):
    db = SessionLocal()

    emails = db.query(EventEmail).filter(
        EventEmail.event_id == event_id
    ).all()

    result = [
        {"id": e.id, "email": e.email}
        for e in emails
    ]

    db.close()
    return result


@router.post("/events/{event_id}/emails")
def add_event_emails(event_id: int, data: EventAddEmailsRequest):
    db = SessionLocal()

    added = []

    for raw_email in data.emails:
        email = raw_email.lower().strip()

        if not email:
            continue

        existing = db.query(EventEmail).filter(
            EventEmail.event_id == event_id,
            EventEmail.email == email
        ).first()

        if existing:
            continue

        entry = EventEmail(
            event_id=event_id,
            email=email,
            created_at=datetime.utcnow()
        )

        db.add(entry)
        added.append(email)

    db.commit()
    db.close()

    return {"success": True, "added": added}


@router.delete("/events/{event_id}/emails/{email}")
def remove_event_email(event_id: int, email: str):
    db = SessionLocal()

    db.query(EventEmail).filter(
        EventEmail.event_id == event_id,
        EventEmail.email == email.lower().strip()
    ).delete()

    db.commit()
    db.close()

    return {"success": True}