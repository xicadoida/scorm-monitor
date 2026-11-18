from datetime import datetime
import ftplib
import os
import re
import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import func

from database import SessionLocal
from models import Course, EmailVerificationToken, Event, EventEmail, EventMembership, ScormPublication
from catalog_utils import touch_catalog
from schemas import (
    EventCreateRequest,
    EventUpdateRequest,
    EventAddEmailsRequest
)
from auth_utils import CurrentUser, require_admin

router = APIRouter()

FTP_HOST = "147.93.37.72"
FTP_USER = "u124251760.lms.iaclube.help"
FTP_PASS = os.getenv("FTP_PASSWORD")
FTP_LOGO_DIR = "/public_html/event-logos"
PUBLIC_LOGO_URL = "https://lms.iaclube.help/event-logos"


def _normalize_slug(value):
    if not value:
        return None
    slug = re.sub(r"[^a-z0-9-]+", "-", value.strip().lower()).strip("-")
    return slug or None


def _serialize_event(event):
    return {
        "id": event.id,
        "name": event.name,
        "slug": event.slug,
        "logo_url": event.logo_url,
        "color_primary": event.color_primary,
        "color_secondary": event.color_secondary,
        "item_name": event.item_name,
        "show_progress": event.show_progress,
        "show_footer": event.show_footer,
        "active": event.active,
        "archived_at": event.archived_at,
    }


@router.post("/events")
def create_event(data: EventCreateRequest, _: CurrentUser = Depends(require_admin)):
    db = SessionLocal()
    slug = _normalize_slug(data.slug)

    if slug and db.query(Event).filter(Event.slug == slug).first():
        db.close()
        return {"success": False, "message": "Esse endereço do evento já está em uso."}

    event = Event(
        name=data.name,
        logo_url=data.logo_url,
        slug=slug,
        color_primary=data.color_primary,
        color_secondary=data.color_secondary,
        item_name=data.item_name,
        show_progress=data.show_progress if data.show_progress is not None else True,
        show_footer=data.show_footer if data.show_footer is not None else False,
        created_at=datetime.utcnow()
    )

    db.add(event)
    touch_catalog(db)
    db.commit()
    db.refresh(event)
    db.close()

    return _serialize_event(event)


@router.get("/events")
def list_events(_: CurrentUser = Depends(require_admin)):
    db = SessionLocal()
    events = db.query(Event).all()

    result = [
        {**_serialize_event(e), "created_at": e.created_at}
        for e in events
    ]

    db.close()
    return result


@router.get("/events/slug/{slug}")
def get_event_by_slug(slug: str):
    db = SessionLocal()
    event = db.query(Event).filter(
        Event.slug == _normalize_slug(slug),
        Event.active.is_(True),
    ).first()

    if not event or not event.active:
        db.close()
        return {"success": False, "message": "Evento não encontrado."}

    result = _serialize_event(event)
    db.close()
    return {"success": True, "event": result}


@router.put("/events/{event_id}")
def update_event(event_id: int, data: EventUpdateRequest, _: CurrentUser = Depends(require_admin)):
    db = SessionLocal()

    event = db.query(Event).filter(Event.id == event_id).first()

    if not event or not event.active:
        db.close()
        return {"success": False, "message": "Evento não encontrado."}

    if data.name is not None:
        event.name = data.name

    if data.logo_url is not None:
        event.logo_url = data.logo_url

    if data.slug is not None:
        slug = _normalize_slug(data.slug)
        duplicate = db.query(Event).filter(Event.slug == slug, Event.id != event_id).first()
        if duplicate:
            db.close()
            return {"success": False, "message": "Esse endereço do evento já está em uso."}
        event.slug = slug

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

    touch_catalog(db)
    db.commit()
    db.close()

    return {"success": True}


@router.post("/events/{event_id}/logo")
async def upload_event_logo(
    event_id: int,
    file: UploadFile = File(...),
    _: CurrentUser = Depends(require_admin),
):
    allowed_types = {"image/png", "image/jpeg", "image/webp", "image/svg+xml", "image/x-icon"}
    if file.content_type not in allowed_types:
        return {"success": False, "message": "Envie uma imagem PNG, JPG, WEBP, SVG ou ICO."}

    db = SessionLocal()
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event or not event.active:
        db.close()
        return {"success": False, "message": "Evento não encontrado."}

    extension = os.path.splitext(file.filename or "")[1].lower() or ".png"
    filename = f"evento-{event_id}-{uuid.uuid4().hex[:12]}{extension}"
    data = await file.read()

    try:
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, 21, timeout=15)
        ftp.login(FTP_USER, FTP_PASS)
        try:
            ftp.mkd(FTP_LOGO_DIR)
        except ftplib.error_perm:
            pass
        from io import BytesIO
        ftp.storbinary(f"STOR {FTP_LOGO_DIR}/{filename}", BytesIO(data))
        ftp.quit()
    except Exception as error:
        db.close()
        return {"success": False, "message": f"Não foi possível enviar a logo: {error}"}

    logo_url = f"{PUBLIC_LOGO_URL}/{filename}"
    event.logo_url = logo_url
    touch_catalog(db)
    db.commit()
    db.close()
    return {"success": True, "logo_url": logo_url}


@router.delete("/events/{event_id}")
def delete_event(event_id: int, _: CurrentUser = Depends(require_admin)):
    db = SessionLocal()
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event or not event.active:
        db.close()
        return {"success": False, "message": "Evento não encontrado."}

    # Uma substituição SCORM em curso ainda pode gravar o caminho do pacote no
    # Course. Arquivar o evento nesse intervalo criaria um curso novo/alterado
    # em escopo desativado. A publicação deve ser recuperada ou concluída antes
    # do arquivamento; novos cursos também são revalidados no journal.
    pending_publication = db.query(ScormPublication.course_code).join(
        Course, Course.course_code == ScormPublication.course_code
    ).filter(Course.event_id == event_id).first()
    if pending_publication:
        db.close()
        return {
            "success": False,
            "message": "Há uma publicação SCORM pendente para este evento.",
        }

    # Course, AttendanceModule, RegistrationProfile e AccessEvent guardam o
    # event_id como relação legada sem FK. Arquivar preserva esse contexto e
    # evita deixar todos eles apontando para um evento inexistente.
    now = datetime.utcnow()
    try:
        event.active = False
        event.archived_at = now
        db.query(EventMembership).filter(
            EventMembership.event_id == event_id,
            EventMembership.revoked_at.is_(None),
        ).update(
            {EventMembership.status: "revoked", EventMembership.revoked_at: now},
            synchronize_session=False,
        )
        db.query(EmailVerificationToken).filter(
            EmailVerificationToken.event_id == event_id,
            EmailVerificationToken.used_at.is_(None),
        ).update({EmailVerificationToken.used_at: now}, synchronize_session=False)
        # O evento inativo já bloqueia a elegibilidade do convite. Mantemos a
        # linha ativa para a conta continuar identificada como de evento e não
        # migrar silenciosamente para o catálogo padrão.
        touch_catalog(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return {"success": True, "message": "Evento desativado e histórico preservado."}


@router.get("/events/{event_id}/emails")
def list_event_emails(event_id: int, _: CurrentUser = Depends(require_admin)):
    db = SessionLocal()

    emails = db.query(EventEmail).filter(
        EventEmail.event_id == event_id,
        EventEmail.active.is_(True),
    ).all()

    result = [
        {"id": e.id, "email": e.email}
        for e in emails
    ]

    db.close()
    return result


@router.post("/events/{event_id}/emails")
def add_event_emails(
    event_id: int,
    data: EventAddEmailsRequest,
    _: CurrentUser = Depends(require_admin),
):
    db = SessionLocal()

    event = db.query(Event).filter(
        Event.id == event_id,
        Event.active.is_(True),
    ).first()
    if not event:
        db.close()
        return {"success": False, "message": "Evento não encontrado."}

    added = []

    for raw_email in data.emails:
        email = raw_email.lower().strip()

        if not email:
            continue

        existing = db.query(EventEmail).filter(
            EventEmail.event_id == event_id,
            func.lower(EventEmail.email) == email,
        ).first()

        if existing:
            if not existing.active:
                # Reativar um convite não restaura a membership revogada. A
                # pessoa precisa confirmar novamente o e-mail para ter acesso.
                existing.active = True
                existing.revoked_at = None
                added.append(email)
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
def remove_event_email(event_id: int, email: str, _: CurrentUser = Depends(require_admin)):
    db = SessionLocal()

    event = db.query(Event).filter(
        Event.id == event_id,
        Event.active.is_(True),
    ).first()
    if not event:
        db.close()
        return {"success": False, "message": "Evento não encontrado."}

    normalized_email = email.lower().strip()
    now = datetime.utcnow()
    # Remover o convite tambem revoga o vinculo confirmado. Recolocar o e-mail
    # posteriormente exigira uma nova confirmacao; nao ha restauracao oculta.
    db.query(EventMembership).filter(
        EventMembership.event_id == event_id,
        func.lower(func.trim(EventMembership.email)) == normalized_email,
        EventMembership.status == "confirmed",
        EventMembership.revoked_at.is_(None),
    ).update(
        {EventMembership.status: "revoked", EventMembership.revoked_at: now},
        synchronize_session=False,
    )

    db.query(EventEmail).filter(
        EventEmail.event_id == event_id,
        func.lower(EventEmail.email) == normalized_email,
        EventEmail.active.is_(True),
    ).update(
        {EventEmail.active: False, EventEmail.revoked_at: now},
        synchronize_session=False,
    )

    # Um link emitido antes da remoção do convite não pode sobreviver à
    # revogação e restaurar o vínculo caso o e-mail seja adicionado de novo.
    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.event_id == event_id,
        func.lower(func.trim(EmailVerificationToken.email)) == normalized_email,
        EmailVerificationToken.used_at.is_(None),
    ).update({EmailVerificationToken.used_at: now}, synchronize_session=False)

    db.commit()
    db.close()

    return {"success": True}
