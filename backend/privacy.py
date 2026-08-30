"""Utilitários de privacidade para auditoria sem persistir IPs reais."""
import hashlib
import hmac
import ipaddress
import os
from datetime import datetime, timedelta

from fastapi import Request

from models import AccessEvent


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "sim"}


def _normalized_client_ip(request: Request | None) -> str | None:
    """Usa X-Forwarded-For somente quando o proxy foi explicitamente confiado."""
    if request is None:
        return None
    raw_ip = None
    if _truthy(os.getenv("TRUST_PROXY_HEADERS")):
        raw_ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if not raw_ip and request.client:
        raw_ip = request.client.host

    try:
        return str(ipaddress.ip_address(raw_ip)) if raw_ip else None
    except ValueError:
        return None


def anonymized_ip_hash(request: Request | None) -> str | None:
    secret = os.getenv("IP_HASH_SECRET", "")
    if len(secret) < 32:
        return None

    ip = _normalized_client_ip(request)
    if not ip:
        return None
    return hmac.new(secret.encode("utf-8"), ip.encode("utf-8"), hashlib.sha256).hexdigest()


def record_access_event(
    db,
    request: Request | None,
    event_type: str,
    *,
    success: bool,
    student_code: str | None = None,
    event_id: int | None = None,
    route: str | None = None,
) -> None:
    """Nunca impede o fluxo principal se a auditoria não estiver configurada."""
    try:
        db.add(AccessEvent(
            event_type=event_type,
            success=success,
            student_code=student_code,
            event_id=event_id,
            ip_hash=anonymized_ip_hash(request),
            user_agent=((request.headers.get("user-agent") or "")[:500] if request else None),
            route=route,
            created_at=datetime.utcnow(),
        ))
    except Exception:
        # Não registra IP em logs de exceção e não quebra login/cadastro.
        return


def prune_expired_access_events(db) -> None:
    """Retenção configurável; 180 dias por padrão."""
    try:
        retention_days = max(1, int(os.getenv("ACCESS_LOG_RETENTION_DAYS", "180")))
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        db.query(AccessEvent).filter(AccessEvent.created_at < cutoff).delete(synchronize_session=False)
    except Exception:
        return
