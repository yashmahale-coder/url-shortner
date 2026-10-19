# Simple URL Shortener

A small FastAPI URL shortener with thread-safe in-memory storage and a per-IP
rate limiter. The limiter implementation is selected in `app/main.py` with
`RATE_LIMITER_BACKEND` (`"sliding_window"` or `"token_bucket"`).

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/docs> for interactive API documentation.

## Test

```powershell
pytest -q
```

## API

| Method | Path | Purpose | Response |
|---|---|---|---|
| POST | `/shorten` | Create or reuse a code for `{"url":"https://..."}` | `{"code":"1"}` |
| GET | `/{code}` | Count a click and redirect to the URL | 307 redirect; 404 if unknown |
| GET | `/stats/{code}` | Read the click count | `{"clicks":3}`; 404 if unknown |
| GET | `/top?k=5` | Return the most-clicked links | List of code, URL, and click count |

The code is the base62 representation of an auto-incrementing integer. Repeating
the same URL returns its existing code.

## Complexity

Let `n` be the number of stored URLs and `k` the requested top count.

| Operation | Time | Additional space |
|---|---|---|
| Encode/decode an ID | O(log₆₂ ID) / O(code length) | O(code length) / O(1) |
| Shorten or look up a URL | O(url length) for a new URL; O(1) average for lookups | O(url length) for a new URL |
| Record click / read stats | O(1) average | O(1) |
| Get top K | O(n log k) | O(k) |
| Sliding-window allow | O(1) amortized | O(1) per recorded request |
| Token-bucket allow | O(1) | O(1) per IP |
| Cleanup idle limiter keys | O(m), for `m` tracked IPs | O(1) auxiliary |

## Trade-offs

- **Base62 vs. hash:** Base62 IDs are short and easy to encode, with no collision
  handling, but sequential codes are guessable. A hash can obscure sequence and
  be deterministic, but requires collision handling or truncation.
- **Sliding window vs. fixed window vs. token bucket:** Sliding window enforces
  the request count over every rolling 60-second span, at the cost of storing
  request timestamps. A fixed window is cheaper to store but allows bursts on
  either side of a window boundary. Token bucket stores a small per-IP state
  and allows controlled bursts while smoothing traffic; it is not identical to
  a strict rolling-window limit.

## Limitations

Data and click counts are lost on restart; storage is process-local and cannot
be shared by multiple workers. The sequential codes can be enumerated. Rate
limiting uses the direct client IP and does not trust forwarded-IP headers.
There is no URL safety validation, authentication, persistence, or deletion
endpoint. Limiter cleanup is available through each limiter's `cleanup()` method
but is not automatically scheduled.

## Scale with Redis

For multiple processes or hosts, move URL/code mappings, counters, and click
counts into Redis and use atomic transactions or Lua scripts for assigning
unique IDs and incrementing clicks. Implement the limiter with Redis sorted
sets for sliding windows or hashes plus server-side timestamps for token
buckets; set expirations to remove idle IP state. Redis persistence and
replication can provide durability and availability beyond this in-memory
example.
