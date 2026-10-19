from app.rate_limiter import SlidingWindow, TokenBucket
from app.shortener import URLShortener


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_base62_round_trip() -> None:
    for value in [0, 1, 61, 62, 3844, 123456789]:
        assert URLShortener.decode_id(URLShortener.encode_id(value)) == value


def test_duplicate_urls_return_same_code() -> None:
    shortener = URLShortener()
    assert shortener.shorten("https://example.com") == shortener.shorten(
        "https://example.com"
    )


def test_sliding_window_allows_burst_then_blocks() -> None:
    clock = FakeClock()
    limiter = SlidingWindow(limit=2, window_seconds=10, clock=clock)
    assert limiter.allow("ip")
    assert limiter.allow("ip")
    assert not limiter.allow("ip")


def test_sliding_window_boundary_expires_old_request() -> None:
    clock = FakeClock()
    limiter = SlidingWindow(limit=1, window_seconds=10, clock=clock)
    assert limiter.allow("ip")
    clock.now = 10
    assert limiter.allow("ip")


def test_rate_limit_is_separate_per_ip() -> None:
    limiter = SlidingWindow(limit=1, window_seconds=10)
    assert limiter.allow("first")
    assert limiter.allow("second")


def test_token_bucket_refills() -> None:
    clock = FakeClock()
    limiter = TokenBucket(capacity=1, refill_rate=0.5, clock=clock)
    assert limiter.allow("ip")
    assert not limiter.allow("ip")
    clock.now = 2
    assert limiter.allow("ip")


def test_cleanup_removes_idle_keys() -> None:
    clock = FakeClock()
    limiter = SlidingWindow(limit=1, window_seconds=10, clock=clock)
    assert limiter.allow("idle")
    clock.now = 10
    assert limiter.cleanup() == 1
