"""FastAPI endpoints for the URL shortener."""

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from starlette.middleware.base import RequestResponseEndpoint

from app.rate_limiter import SlidingWindow, TokenBucket
from app.shortener import URLShortener

RATE_LIMITER_BACKEND = "sliding_window"


class ShortenRequest(BaseModel):
    """Payload for creating a short URL."""

    url: str


def create_app() -> FastAPI:
    """Create an app with fresh in-memory storage and rate-limit state."""
    # Time: O(1); Space: O(1).
    app = FastAPI(title="Simple URL Shortener")
    shortener = URLShortener()
    if RATE_LIMITER_BACKEND == "sliding_window":
        limiter = SlidingWindow()
    elif RATE_LIMITER_BACKEND == "token_bucket":
        limiter = TokenBucket()
    else:
        raise ValueError(f"Unknown rate limiter backend: {RATE_LIMITER_BACKEND}")

    @app.middleware("http")
    async def rate_limit(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Reject requests exceeding the per-IP limit."""
        # Time: O(1) amortized; Space: O(1) per request.
        key = request.client.host if request.client else "unknown"
        if not limiter.allow(key):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(limiter.retry_after(key))},
            )
        return await call_next(request)

    @app.post("/shorten")
    def shorten(payload: ShortenRequest) -> dict[str, str]:
        """Create or retrieve a URL's short code."""
        # Time: O(len(url)) for a new URL; Space: O(len(url)).
        return {"code": shortener.shorten(payload.url)}

    @app.get("/stats/{code}")
    def stats(code: str) -> dict[str, int]:
        """Read a code's click count."""
        # Time: O(1) average; Space: O(1).
        clicks = shortener.get_clicks(code)
        if clicks is None:
            raise HTTPException(status_code=404, detail="Unknown code")
        return {"clicks": clicks}

    @app.get("/top")
    def top(k: int = Query(default=5, ge=1)) -> list[dict[str, str | int]]:
        """Return the most-clicked links."""
        # Time: O(n log k); Space: O(k).
        return shortener.top(k)

    @app.get("/{code}")
    def redirect(code: str) -> RedirectResponse:
        """Count a click and redirect to the original URL."""
        # Time: O(1) average; Space: O(1).
        url = shortener.record_click(code)
        if url is None:
            raise HTTPException(status_code=404, detail="Unknown code")
        return RedirectResponse(url=url, status_code=307)

    return app


app = create_app()
