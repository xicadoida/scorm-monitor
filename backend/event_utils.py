"""Regras de escopo de evento aplicadas no servidor.

``EventEmail`` e uma lista de convidados, nunca uma autorizacao por si so.
O acesso a um evento depende de ``EventMembership`` confirmada para a conta
e do endereco que ela comprovou controlar.
"""

from sqlalchemy import func

from models import Event, EventEmail, EventMembership


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def serialize_event(event: Event | None) -> dict | None:
    if not event:
        return None
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
    }


def get_event_by_slug(db, slug: str | None) -> Event | None:
    normalized_slug = (slug or "").strip().lower()
    if not normalized_slug:
        return None
    return db.query(Event).filter(func.lower(Event.slug) == normalized_slug).first()


def is_email_invited_to_event(db, email: str | None, event_id: int | None) -> bool:
    """Retorna apenas elegibilidade administrativa, sem conceder acesso."""

    normalized_email = normalize_email(email)
    if not normalized_email or event_id is None:
        return False
    return db.query(EventEmail.id).filter(
        EventEmail.event_id == event_id,
        func.lower(EventEmail.email) == normalized_email,
    ).first() is not None


def has_any_event_invitation(db, email: str | None) -> bool:
    normalized_email = normalize_email(email)
    if not normalized_email:
        return False
    return db.query(EventEmail.id).filter(
        func.lower(EventEmail.email) == normalized_email,
    ).first() is not None


def student_has_active_event_membership(db, student, event_id: int | None) -> bool:
    """Confere o vinculo explicito, o convite atual e a posse do e-mail.

    Esta funcao e deliberadamente usada tanto ao emitir como ao consumir uma
    sessao. Assim, remover um convidado ou trocar o e-mail da conta derruba o
    acesso mesmo que ainda exista um token de sessao assinado e valido.
    """

    if not student or not student.email_verified_at or event_id is None:
        return False
    normalized_email = normalize_email(student.email)
    membership = db.query(EventMembership).filter(
        EventMembership.student_code == student.student_code,
        EventMembership.event_id == event_id,
        EventMembership.status == "confirmed",
        EventMembership.revoked_at.is_(None),
        func.lower(EventMembership.email) == normalized_email,
    ).first()
    return membership is not None and is_email_invited_to_event(db, normalized_email, event_id)


def get_event_for_student(db, student, event_id: int | None) -> dict | None:
    if not student_has_active_event_membership(db, student, event_id):
        return None
    return serialize_event(db.query(Event).filter(Event.id == event_id).first())


def get_confirmed_events_for_student(db, student) -> list[dict]:
    """Lista todos os eventos efetivamente autorizados para exibicao admin."""

    if not student or not student.email_verified_at:
        return []
    memberships = db.query(EventMembership).filter(
        EventMembership.student_code == student.student_code,
        EventMembership.status == "confirmed",
        EventMembership.revoked_at.is_(None),
        func.lower(EventMembership.email) == normalize_email(student.email),
    ).all()
    result = []
    for membership in memberships:
        event = get_event_for_student(db, student, membership.event_id)
        if event:
            result.append(event)
    return result


def has_event_scope(db, student) -> bool:
    """Indica se a conta deve entrar pelo ambiente de evento, nao pelo padrao."""

    if not student:
        return False
    if has_any_event_invitation(db, student.email):
        return True
    return bool(get_confirmed_events_for_student(db, student))


def course_is_available_for_event(course, event_id: int | None) -> bool:
    """Mantem a separacao entre catalogo padrao e catalogos de evento."""

    return bool(course and course.active and course.event_id == event_id)


def student_can_access_course(db, student, course, active_event_id: int | None = None) -> bool:
    """Aplica identidade, vinculo de evento e estado do curso no servidor."""

    if not student or student.email_verified_at is None:
        return False
    if active_event_id is not None:
        return (
            student_has_active_event_membership(db, student, active_event_id)
            and course_is_available_for_event(course, active_event_id)
        )
    return not has_event_scope(db, student) and course_is_available_for_event(course, None)
