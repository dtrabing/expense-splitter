import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_index_renders_the_form(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Expense Splitter" in response.data
    assert b'name="expenses"' in response.data


def test_form_post_shows_who_pays_whom(client):
    response = client.post("/", data={"expenses": "Alice 60\nBob 20", "participants": ""})
    assert response.status_code == 200
    assert b"<strong>Bob</strong> pays <strong>Alice</strong> $20.00" in response.data


def test_form_post_shows_a_helpful_error(client):
    response = client.post("/", data={"expenses": "Alice lots"})
    assert response.status_code == 400
    assert b"line 1" in response.data


def test_api_split_with_records(client):
    response = client.post(
        "/api/split",
        json={"expenses": [{"payer": "Alice", "amount": 30}, {"payer": "Bob", "amount": 10}]},
    )
    assert response.status_code == 200
    assert response.get_json()["transfers"] == [
        {"from": "Bob", "to": "Alice", "cents": 1000, "amount": "10.00"}
    ]


def test_api_split_with_text_and_participants(client):
    response = client.post(
        "/api/split",
        json={"expenses": "Alice 30\nBob 10", "participants": "Alice, Bob, Carol"},
    )
    body = response.get_json()
    assert response.status_code == 200
    assert body["total"] == "40.00"
    assert [person["name"] for person in body["people"]] == ["Alice", "Bob", "Carol"]


def test_api_rejects_bad_expense_lines(client):
    response = client.post("/api/split", json={"expenses": "Alice ten"})
    assert response.status_code == 400
    assert "line 1" in response.get_json()["error"]


def test_api_rejects_non_json_bodies(client):
    response = client.post("/api/split", data="not json")
    assert response.status_code == 400
    assert "JSON" in response.get_json()["error"]


def test_health(client):
    assert client.get("/api/health").get_json() == {"status": "ok"}
