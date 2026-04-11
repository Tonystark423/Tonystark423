"""
Tests for the meal planning API endpoints (app.py).

NOTE: All test modules share the same app.py module instance (Python module caching).
test_app.py is imported first alphabetically and fixes LEDGER_USER="testuser"/
LEDGER_PASS="testpass". All modules use those credentials for compatibility.
"""

import json
import os
import sqlite3
import tempfile

import pytest

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DB_PATH"] = _db_path
os.environ["LEDGER_USER"] = "testuser"
os.environ["LEDGER_PASS"] = "testpass"
os.environ["FLASK_SECRET_KEY"] = "test-secret"

import app as app_module  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def init_database():
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
    with open(schema_path) as f:
        schema = f.read()
    conn = sqlite3.connect(app_module.DB_PATH)
    conn.executescript(schema)
    conn.close()
    yield
    os.close(_db_fd)
    try:
        os.unlink(_db_path)
    except FileNotFoundError:
        pass


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def auth():
    return (app_module.LEDGER_USER, app_module.LEDGER_PASS)


@pytest.fixture()
def seed_meal(client, auth):
    """Insert one business meal and return its dict."""
    payload = {
        "name": "Sushi Business Dinner",
        "description": "Client entertainment at Nobu",
        "estimated_cost": 150.0,
        "cuisine_type": "Japanese",
        "meal_category": "business",
        "notes": "Receipt required for deduction",
    }
    resp = client.post(
        "/api/meals",
        data=json.dumps(payload),
        content_type="application/json",
        auth=auth,
    )
    assert resp.status_code == 201
    return resp.get_json()


@pytest.fixture()
def seed_cheap_meal(client, auth):
    """Insert a cheap meal well within the default travel budget."""
    payload = {
        "name": "Office Lunch Budget Test",
        "estimated_cost": 15.0,
        "meal_category": "business",
    }
    resp = client.post(
        "/api/meals",
        data=json.dumps(payload),
        content_type="application/json",
        auth=auth,
    )
    assert resp.status_code == 201
    return resp.get_json()


@pytest.fixture()
def seed_expensive_meal(client, auth):
    """Insert a meal that costs more than the full Travel budget ($2500)."""
    payload = {
        "name": "Michelin Star Banquet Budget Test",
        "estimated_cost": 9999.0,
        "meal_category": "business",
    }
    resp = client.post(
        "/api/meals",
        data=json.dumps(payload),
        content_type="application/json",
        auth=auth,
    )
    assert resp.status_code == 201
    return resp.get_json()


# ---------------------------------------------------------------------------
# POST /api/meals — create_meal
# ---------------------------------------------------------------------------

class TestCreateMeal:
    def test_missing_name_returns_400(self, client, auth):
        resp = client.post(
            "/api/meals",
            data=json.dumps({"cuisine_type": "Italian"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 400
        assert "name" in resp.get_json()["error"]

    def test_empty_name_returns_400(self, client, auth):
        resp = client.post(
            "/api/meals",
            data=json.dumps({"name": "   "}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 400

    def test_valid_minimal_payload_returns_201(self, client, auth):
        resp = client.post(
            "/api/meals",
            data=json.dumps({"name": "Simple Bowl"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Simple Bowl"
        assert data["id"] is not None

    def test_full_payload_all_fields_stored(self, client, auth):
        payload = {
            "name": "Steak Dinner",
            "description": "NY Strip at Smith and Wollensky",
            "estimated_cost": 200.0,
            "cuisine_type": "American Steakhouse",
            "meal_category": "business",
            "notes": "Client meeting",
        }
        resp = client.post(
            "/api/meals",
            data=json.dumps(payload),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == payload["name"]
        assert data["cuisine_type"] == payload["cuisine_type"]
        assert data["meal_category"] == payload["meal_category"]
        assert data["notes"] == payload["notes"]

    def test_zero_estimated_cost_returns_400(self, client, auth):
        resp = client.post(
            "/api/meals",
            data=json.dumps({"name": "Free Lunch", "estimated_cost": 0.0}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 400
        assert "estimated_cost" in resp.get_json()["error"]

    def test_negative_estimated_cost_returns_400(self, client, auth):
        resp = client.post(
            "/api/meals",
            data=json.dumps({"name": "Negative Meal", "estimated_cost": -10.0}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 400
        assert "estimated_cost" in resp.get_json()["error"]

    def test_nonnumeric_estimated_cost_returns_400(self, client, auth):
        resp = client.post(
            "/api/meals",
            data=json.dumps({"name": "Bad Cost Meal", "estimated_cost": "lots"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 400

    def test_cost_stored_as_decimal_string(self, client, auth):
        """estimated_cost should be stored as a 4dp Decimal string in the DB."""
        resp = client.post(
            "/api/meals",
            data=json.dumps({"name": "Decimal Test Meal", "estimated_cost": 99.5}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 201
        meal_id = resp.get_json()["id"]

        conn = sqlite3.connect(app_module.DB_PATH)
        row = conn.execute("SELECT estimated_cost FROM meals WHERE id = ?", (meal_id,)).fetchone()
        conn.close()
        assert row[0] == "99.5000"

    def test_requires_auth(self, client):
        resp = client.post(
            "/api/meals",
            data=json.dumps({"name": "Unauth Meal"}),
            content_type="application/json",
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/meals — list_meals
# ---------------------------------------------------------------------------

class TestListMeals:
    def test_returns_list(self, client, auth, seed_meal):
        resp = client.get("/api/meals", auth=auth)
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_list_contains_seeded_meal(self, client, auth, seed_meal):
        resp = client.get("/api/meals", auth=auth)
        meals = resp.get_json()
        assert any(m["name"] == seed_meal["name"] for m in meals)

    def test_category_filter_business(self, client, auth, seed_meal):
        resp = client.get("/api/meals?category=business", auth=auth)
        assert resp.status_code == 200
        for meal in resp.get_json():
            assert meal["meal_category"] == "business"

    def test_category_filter_general(self, client, auth):
        client.post(
            "/api/meals",
            data=json.dumps({"name": "General Category Meal", "meal_category": "general"}),
            content_type="application/json",
            auth=auth,
        )
        resp = client.get("/api/meals?category=general", auth=auth)
        assert resp.status_code == 200
        for meal in resp.get_json():
            assert meal["meal_category"] == "general"

    def test_requires_auth(self, client):
        resp = client.get("/api/meals")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/meals/<id> — get_meal
# ---------------------------------------------------------------------------

class TestGetMeal:
    def test_existing_id_returns_meal(self, client, auth, seed_meal):
        meal_id = seed_meal["id"]
        resp = client.get(f"/api/meals/{meal_id}", auth=auth)
        assert resp.status_code == 200
        assert resp.get_json()["id"] == meal_id

    def test_nonexistent_id_returns_404(self, client, auth):
        resp = client.get("/api/meals/999999", auth=auth)
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_requires_auth(self, client):
        resp = client.get("/api/meals/1")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /api/meals/<id> — delete_meal
# ---------------------------------------------------------------------------

class TestDeleteMeal:
    def test_nonexistent_id_returns_404(self, client, auth):
        resp = client.delete("/api/meals/999999", auth=auth)
        assert resp.status_code == 404

    def test_existing_meal_deleted_returns_204(self, client, auth):
        create_resp = client.post(
            "/api/meals",
            data=json.dumps({"name": "Temp Meal To Delete"}),
            content_type="application/json",
            auth=auth,
        )
        meal_id = create_resp.get_json()["id"]
        del_resp = client.delete(f"/api/meals/{meal_id}", auth=auth)
        assert del_resp.status_code == 204

    def test_deleted_meal_not_retrievable(self, client, auth):
        create_resp = client.post(
            "/api/meals",
            data=json.dumps({"name": "Gone Meal"}),
            content_type="application/json",
            auth=auth,
        )
        meal_id = create_resp.get_json()["id"]
        client.delete(f"/api/meals/{meal_id}", auth=auth)
        get_resp = client.get(f"/api/meals/{meal_id}", auth=auth)
        assert get_resp.status_code == 404

    def test_requires_auth(self, client):
        resp = client.delete("/api/meals/1")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/meals/suggestions — meal_suggestions
# ---------------------------------------------------------------------------

class TestMealSuggestions:
    def test_requires_auth(self, client):
        resp = client.get("/api/meals/suggestions")
        assert resp.status_code == 401

    def test_returns_200(self, client, auth):
        resp = client.get("/api/meals/suggestions", auth=auth)
        assert resp.status_code == 200

    def test_response_has_required_fields(self, client, auth):
        resp = client.get("/api/meals/suggestions", auth=auth)
        data = resp.get_json()
        assert "budget_remaining" in data
        assert "suggestions" in data
        assert "currency" in data

    def test_budget_remaining_is_float(self, client, auth):
        resp = client.get("/api/meals/suggestions", auth=auth)
        data = resp.get_json()
        assert isinstance(data["budget_remaining"], (int, float))

    def test_currency_field_is_usd(self, client, auth):
        resp = client.get("/api/meals/suggestions", auth=auth)
        assert resp.get_json()["currency"] == "USD"

    def test_cheap_meal_appears_in_suggestions(self, client, auth, seed_cheap_meal):
        """A $15 meal should be affordable within the default Travel budget."""
        resp = client.get("/api/meals/suggestions", auth=auth)
        assert resp.status_code == 200
        suggestions = resp.get_json()["suggestions"]
        assert any(m["id"] == seed_cheap_meal["id"] for m in suggestions)

    def test_expensive_meal_excluded_from_suggestions(self, client, auth, seed_expensive_meal):
        """A $9999 meal exceeds the $2500 Travel budget."""
        resp = client.get("/api/meals/suggestions", auth=auth)
        suggestions = resp.get_json()["suggestions"]
        assert not any(m["id"] == seed_expensive_meal["id"] for m in suggestions)

    def test_limit_param_respected(self, client, auth):
        for i in range(5):
            client.post(
                "/api/meals",
                data=json.dumps({"name": f"Limit Test Meal {i}", "estimated_cost": 10.0}),
                content_type="application/json",
                auth=auth,
            )
        resp = client.get("/api/meals/suggestions?limit=2", auth=auth)
        assert resp.status_code == 200
        assert len(resp.get_json()["suggestions"]) <= 2
