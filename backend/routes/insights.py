from datetime import datetime, timedelta

from fastapi import APIRouter, Depends

from auth_utils import CurrentUser, require_admin
from database import SessionLocal
from models import AccessEvent, Event, RegistrationProfile, Student


router = APIRouter(prefix="/admin/insights", tags=["admin-insights"])


def _parse_datetime(value: str | None, *, end_of_day: bool = False):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if len(value) == 10 and end_of_day:
            return parsed + timedelta(days=1)
        return parsed
    except ValueError:
        return None


def _apply_access_filters(query, start_date, end_date, event_id, person_type, profiles):
    start = _parse_datetime(start_date)
    end = _parse_datetime(end_date, end_of_day=True)
    if start:
        query = query.filter(AccessEvent.created_at >= start)
    if end:
        query = query.filter(AccessEvent.created_at < end)
    if event_id is not None:
        query = query.filter(AccessEvent.event_id == event_id)
    if person_type:
        allowed_codes = [
            profile.student_code for profile in profiles.values()
            if profile.person_type == person_type
        ]
        query = query.filter(AccessEvent.student_code.in_(allowed_codes))
    return query


def _profile_maps(db):
    profiles = {profile.student_code: profile for profile in db.query(RegistrationProfile).all()}
    students = {student.student_code: student for student in db.query(Student).all()}
    events = {event.id: event for event in db.query(Event).all()}
    return profiles, students, events


@router.get("/summary")
def get_summary(
    start_date: str | None = None,
    end_date: str | None = None,
    event_id: int | None = None,
    person_type: str | None = None,
    _: CurrentUser = Depends(require_admin),
):
    db = SessionLocal()
    try:
        profiles, students, events = _profile_maps(db)
        filtered_profiles = list(profiles.values())
        if event_id is not None:
            filtered_profiles = [profile for profile in filtered_profiles if profile.event_id == event_id]
        if person_type:
            filtered_profiles = [profile for profile in filtered_profiles if profile.person_type == person_type]

        start = _parse_datetime(start_date)
        end = _parse_datetime(end_date, end_of_day=True)
        if start:
            filtered_profiles = [profile for profile in filtered_profiles if profile.created_at and profile.created_at >= start]
        if end:
            filtered_profiles = [profile for profile in filtered_profiles if profile.created_at and profile.created_at < end]

        accesses = _apply_access_filters(
            db.query(AccessEvent), start_date, end_date, event_id, person_type, profiles
        ).all()
        successful_logins = [event for event in accesses if event.event_type == "login" and event.success]
        unique_accessors = {event.student_code for event in successful_logins if event.student_code}
        latest_by_student = {}
        for event in successful_logins:
            if event.student_code not in latest_by_student or latest_by_student[event.student_code].created_at < event.created_at:
                latest_by_student[event.student_code] = event

        return {
            "success": True,
            "summary": {
                "total_registrations": len(filtered_profiles),
                "total_successful_logins": len(successful_logins),
                "unique_people_accessed": len(unique_accessors),
                "last_accesses": [
                    {
                        "student_code": access.student_code,
                        "name": students.get(access.student_code).name if access.student_code in students else None,
                        "email": students.get(access.student_code).email if access.student_code in students else None,
                        "at": access.created_at,
                    }
                    for access in sorted(latest_by_student.values(), key=lambda item: item.created_at, reverse=True)[:10]
                ],
            },
        }
    finally:
        db.close()


@router.get("/profile-stats")
def get_profile_stats(
    event_id: int | None = None,
    _: CurrentUser = Depends(require_admin),
):
    db = SessionLocal()
    try:
        profiles, _, events = _profile_maps(db)
        rows = list(profiles.values())
        if event_id is not None:
            rows = [profile for profile in rows if profile.event_id == event_id]

        by_person_type = {"pf": 0, "pj": 0, "not_informed": 0}
        by_event = {}
        for profile in rows:
            by_person_type[profile.person_type] = by_person_type.get(profile.person_type, 0) + 1
            label = events.get(profile.event_id).name if profile.event_id in events else "Plataforma padrão / legado"
            by_event[label] = by_event.get(label, 0) + 1

        return {
            "success": True,
            "total": len(rows),
            "by_person_type": by_person_type,
            "by_event": [
                {"event": name, "count": count}
                for name, count in sorted(by_event.items(), key=lambda item: item[1], reverse=True)
            ],
        }
    finally:
        db.close()


@router.get("/access-log")
def get_access_log(
    start_date: str | None = None,
    end_date: str | None = None,
    event_id: int | None = None,
    person_type: str | None = None,
    success: bool | None = None,
    limit: int = 100,
    _: CurrentUser = Depends(require_admin),
):
    db = SessionLocal()
    try:
        profiles, students, events = _profile_maps(db)
        query = _apply_access_filters(
            db.query(AccessEvent), start_date, end_date, event_id, person_type, profiles
        )
        if success is not None:
            query = query.filter(AccessEvent.success == success)
        entries = query.order_by(AccessEvent.created_at.desc()).limit(min(max(limit, 1), 500)).all()

        return {
            "success": True,
            "entries": [
                {
                    "id": entry.id,
                    "event_type": entry.event_type,
                    "success": entry.success,
                    "student_code": entry.student_code,
                    "name": students.get(entry.student_code).name if entry.student_code in students else None,
                    "email": students.get(entry.student_code).email if entry.student_code in students else None,
                    "person_type": profiles.get(entry.student_code).person_type if entry.student_code in profiles else "not_informed",
                    "event": events.get(entry.event_id).name if entry.event_id in events else None,
                    "ip_hash": entry.ip_hash,
                    "user_agent": entry.user_agent,
                    "route": entry.route,
                    "created_at": entry.created_at,
                }
                for entry in entries
            ],
        }
    finally:
        db.close()


@router.get("/ip-activity")
def get_ip_activity(
    start_date: str | None = None,
    end_date: str | None = None,
    threshold: int = 10,
    _: CurrentUser = Depends(require_admin),
):
    db = SessionLocal()
    try:
        query = db.query(AccessEvent).filter(AccessEvent.ip_hash.isnot(None))
        query = _apply_access_filters(query, start_date, end_date, None, None, {})
        grouped = {}
        for entry in query.all():
            grouped[entry.ip_hash] = grouped.get(entry.ip_hash, 0) + 1
        return {
            "success": True,
            "threshold": max(1, threshold),
            "hashes": [
                {"ip_hash": ip_hash, "count": count, "suspicious": count >= max(1, threshold)}
                for ip_hash, count in sorted(grouped.items(), key=lambda item: item[1], reverse=True)
            ],
        }
    finally:
        db.close()
