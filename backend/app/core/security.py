"""
Lightweight API key authentication.

Design notes
------------
This assessment's frontend is a simple upload + chat UI with no user
accounts, so a full OAuth/JWT system would be over-engineering for the
stated scope. Instead we use a single shared API key checked via the
``X-API-Key`` header, applied to *write* operations (upload, delete).

- If ``API_KEY`` is not set (the default for local development), auth is
  skipped entirely so the assessment's frontend works out of the box.
- If ``API_KEY`` is set (recommended for any non-local environment), every
  protected request must include a matching ``X-API-Key`` header or it is
  rejected with 401.

Trade-off: a single shared secret has no per-user accountability and cannot
be revoked for one client without rotating it for everyone. For a system
with real user accounts, this should be replaced with per-user JWTs (e.g.
issued after login against LMH's identity provider) — see ARCHITECTURE.md.
"""

import hmac

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency that enforces the configured API key, if any.

    Uses ``hmac.compare_digest`` for a constant-time comparison so the
    response timing doesn't leak information about how many characters of
    the key were correct.
    """
    if not settings.api_key:
        # Auth disabled — local/dev mode.
        return

    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key. Include it as the 'X-API-Key' header.",
        )