from fastapi.testclient import TestClient

from app.main import create_app


def test_shortening_redirecting_and_stats() -> None:
    client = TestClient(create_app(), client=("198.51.100.1", 5000))
    response = client.post("/shorten", json={"url": "https://example.com/page"})
    assert response.status_code == 200
    code = response.json()["code"]

    redirect = client.get(f"/{code}", follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == "https://example.com/page"
    assert client.get(f"/stats/{code}").json() == {"clicks": 1}
    assert client.get("/unknown").status_code == 404


def test_top_k_returns_most_clicked_first() -> None:
    client = TestClient(create_app(), client=("198.51.100.2", 5000))
    first = client.post("/shorten", json={"url": "https://example.com/1"}).json()["code"]
    second = client.post("/shorten", json={"url": "https://example.com/2"}).json()["code"]
    for _ in range(2):
        client.get(f"/{second}", follow_redirects=False)
    client.get(f"/{first}", follow_redirects=False)
    result = client.get("/top?k=1").json()
    assert result == [{"code": second, "url": "https://example.com/2", "clicks": 2}]


def test_rate_limit_returns_429_and_retry_after() -> None:
    client = TestClient(create_app(), client=("198.51.100.3", 5000))
    for _ in range(10):
        assert client.get("/top").status_code == 200
    response = client.get("/top")
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0
