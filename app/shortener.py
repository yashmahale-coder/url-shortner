"""Thread-safe in-memory URL storage."""

import heapq
from threading import Lock


class URLShortener:
    """Store URLs under base62-encoded, auto-incrementing IDs."""

    _ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def __init__(self) -> None:
        # Time: O(1); Space: O(1) initially.
        self._lock = Lock()
        self._next_id = 1
        self._url_to_code: dict[str, str] = {}
        self._code_to_url: dict[str, str] = {}
        self._clicks: dict[str, int] = {}

    @classmethod
    def encode_id(cls, value: int) -> str:
        """Encode a non-negative integer as base62."""
        # Time: O(log_62(value)); Space: O(log_62(value)).
        if value < 0:
            raise ValueError("ID must be non-negative")
        if value == 0:
            return cls._ALPHABET[0]
        encoded = []
        while value:
            value, remainder = divmod(value, 62)
            encoded.append(cls._ALPHABET[remainder])
        return "".join(reversed(encoded))

    @classmethod
    def decode_id(cls, code: str) -> int:
        """Decode a base62 code to its integer ID."""
        # Time: O(len(code)); Space: O(1).
        if not code:
            raise ValueError("Code must not be empty")
        value = 0
        for char in code:
            try:
                digit = cls._ALPHABET.index(char)
            except ValueError as exc:
                raise ValueError(f"Invalid base62 character: {char}") from exc
            value = value * 62 + digit
        return value

    def shorten(self, url: str) -> str:
        """Return the stable code for a URL, creating one if needed."""
        # Time: O(len(url)) for a new URL; Space: O(len(url)).
        with self._lock:
            existing = self._url_to_code.get(url)
            if existing is not None:
                return existing
            code = self.encode_id(self._next_id)
            self._next_id += 1
            self._url_to_code[url] = code
            self._code_to_url[code] = url
            self._clicks[code] = 0
            return code

    def record_click(self, code: str) -> str | None:
        """Increment a known code's click count and return its URL."""
        # Time: O(1) average; Space: O(1).
        with self._lock:
            url = self._code_to_url.get(code)
            if url is not None:
                self._clicks[code] += 1
            return url

    def get_clicks(self, code: str) -> int | None:
        """Return a code's click count, or None if it is unknown."""
        # Time: O(1) average; Space: O(1).
        with self._lock:
            return self._clicks.get(code)

    def top(self, k: int) -> list[dict[str, str | int]]:
        """Return up to k links ordered by descending click count."""
        # Time: O(n log k); Space: O(k), where n is the number of URLs.
        with self._lock:
            top_items = heapq.nlargest(max(0, k), self._clicks.items(), key=lambda item: item[1])
            return [
                {"code": code, "url": self._code_to_url[code], "clicks": clicks}
                for code, clicks in top_items
            ]
