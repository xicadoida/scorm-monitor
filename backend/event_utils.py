from models import Event, EventEmail


def get_event_for_email(db, email):
    """
    Retorna o dicionário do evento ao qual esse email pertence,
    ou None se o email não estiver em nenhuma lista de evento.
    """
    if not email:
        return None

    event_email = db.query(EventEmail).filter(
        EventEmail.email == email.lower().strip()
    ).first()

    if not event_email:
        return None

    event = db.query(Event).filter(
        Event.id == event_email.event_id
    ).first()

    if not event:
        return None

    return {
        "id": event.id,
        "name": event.name,
        "logo_url": event.logo_url,
        "color_primary": event.color_primary,
        "color_secondary": event.color_secondary
    }
