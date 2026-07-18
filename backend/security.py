"""Controles leves de segurança para bordas HTTP."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from fastapi import HTTPException, Request, status

from backend.settings import is_production_environment, setting

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
LOCAL_DEVELOPMENT_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}
PRODUCTION_ORIGINS = {
    "https://healthai.net.br",
    "https://www.healthai.net.br",
}
LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}
_rate_limit_lock = threading.Lock()
_rate_limit_hits: dict[str, deque[float]] = defaultdict(deque)


def is_production() -> bool:
    return is_production_environment()


def docs_enabled() -> bool:
    configured = setting("HEALTHAI_ENABLE_DOCS").strip().lower()
    if configured:
        return configured in {"1", "true", "yes", "on"}
    return not is_production()


def secure_cookie_enabled() -> bool:
    if is_production():
        return True
    configured = setting("HEALTHAI_SECURE_COOKIE").strip().lower()
    if configured:
        return configured in {"1", "true", "yes", "on"}
    return False


def trusted_origins() -> set[str]:
    production = is_production()
    origins = set(PRODUCTION_ORIGINS if production else LOCAL_DEVELOPMENT_ORIGINS)
    configured_frontend = setting("HEALTHAI_FRONTEND_URL").strip().rstrip("/")
    if configured_frontend:
        origins.add(configured_frontend)
    configured_origins = setting("HEALTHAI_TRUSTED_ORIGINS").split(",")
    origins.update(origin.strip().rstrip("/") for origin in configured_origins)
    if production:
        return {
            origin
            for origin in origins
            if origin and not is_local_origin(origin)
        }
    return {origin for origin in origins if origin}


def is_local_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    hostname = parsed.hostname or ""
    return hostname.lower() in LOCAL_HOSTNAMES


def request_origin(request: Request) -> str | None:
    origin = request.headers.get("origin")
    if origin:
        return origin.rstrip("/")
    referer = request.headers.get("referer")
    if not referer:
        return None
    parsed = urlparse(referer)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def validate_unsafe_request_origin(request: Request) -> None:
    if request.method.upper() not in UNSAFE_METHODS:
        return

    sec_fetch_site = request.headers.get("sec-fetch-site", "").lower()
    if sec_fetch_site == "cross-site":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origem da requisição não autorizada.",
        )

    origin = request_origin(request)
    if is_production() and not origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origem da requisição não autorizada.",
        )
    if origin and origin not in trusted_origins():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origem da requisição não autorizada.",
        )


def client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(
    request: Request,
    *,
    scope: str,
    limit: int,
    window_seconds: int,
    identifier: str = "",
) -> None:
    """Aplica limite simples por IP, escopo e identificador opcional."""
    # Rate limit em memória é adequado só para protótipo/processo único.
    # Em produção escalável, use um backend compartilhado como Redis.
    if setting("HEALTHAI_RATE_LIMIT_ENABLED", "true").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return

    now = time.monotonic()
    cutoff = now - window_seconds
    key = f"{scope}:{client_ip(request)}:{identifier.lower()}"
    with _rate_limit_lock:
        hits = _rate_limit_hits[key]
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas. Aguarde alguns minutos e tente novamente.",
            )
        hits.append(now)
