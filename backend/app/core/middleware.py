"""
HTTP middleware: request correlation IDs and rate limiting.
"""
import logging
import time
import uuid
from collections import defaultdict, deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
logger = logging.getLogger(__name__)
class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique ID to every request for log correlation.
    The ID is:
      - read from an inbound ``X-Request-ID`` header if present (so an
        upstream load balancer / API gateway ID is preserved end-to-end),
      - otherwise generated as a UUID4,
      - stored on ``request.state.request_id`` for use by route handlers,
      - bound to the logging context so every log line during this request
        includes it,
      - echoed back on the response so a client can quote it when reporting
        an issue ("error ref: <request_id>").
    """
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        # Bind request_id onto every log record emitted during this request.
        old_factory = logging.getLogRecordFactory()
        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.request_id = request_id
            return record
        logging.setLogRecordFactory(record_factory)
        try:
            response = await call_next(request)
        finally:
            logging.setLogRecordFactory(old_factory)
        response.headers["X-Request-ID"] = request_id
        return response
class RateLimitMiddleware(BaseHTTPMiddleware):
    """A simple fixed-window rate limiter, keyed by client IP.
    This is intentionally dependency-free (no Redis) so the assessment runs
    with `docker compose up` and nothing else. It is suitable for a single
    backend instance.
    Trade-off: state is held in-process, so:
      - it resets if the process restarts, and
      - with multiple gunicorn workers or replicas, each one tracks its own
        counters, so the *effective* limit is `limit * worker_count`.
    For production with multiple instances, replace the in-memory `_hits`
    store with a Redis-backed counter (e.g. `INCR` + `EXPIRE`), keeping the
    same middleware interface. See ARCHITECTURE.md.
    """
    def __init__(self, app, max_requests: int, window_seconds: int, enabled: bool = True):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.enabled = enabled
        self._hits: dict[str, deque[float]] = defaultdict(deque)
    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self._hits[client_ip]
        # Drop timestamps outside the current window.
        cutoff = now - self.window_seconds
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= self.max_requests:
            retry_after = max(0, int(self.window_seconds - (now - window[0])))
            logger.warning("Rate limit exceeded for %s", client_ip)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please slow down and try again."},
                headers={"Retry-After": str(retry_after)},
            )
        window.append(now)
        return await call_next(request)