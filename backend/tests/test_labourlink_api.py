"""LabourLink AI - Backend API regression tests.

Covers: seed, auth (register/login/me), categories, workers list/filter/search/sort,
popular, AI recommendations, worker detail, worker onboarding/status/earnings/withdraw,
bookings flow, reviews, favorites, messaging/chats, _id leakage check.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://skill-match-252.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@labour.app"
DEMO_PASS = "demo1234"


def _no_underscore_id(obj):
    """Recursively assert no '_id' key in any dict/list structure."""
    if isinstance(obj, dict):
        assert "_id" not in obj, f"_id leaked in payload: keys={list(obj.keys())}"
        for v in obj.values():
            _no_underscore_id(v)
    elif isinstance(obj, list):
        for item in obj:
            _no_underscore_id(item)


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="session")
def seeded(s):
    r = s.post(f"{API}/seed", timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="session")
def demo_token(s, seeded):
    r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASS}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def demo_auth(demo_token):
    return {"Authorization": f"Bearer {demo_token}", "Content-Type": "application/json"}


# ============ Health & Seed ============
class TestHealth:
    def test_root(self, s):
        r = s.get(f"{API}/", timeout=10)
        assert r.status_code == 200
        assert "message" in r.json()

    def test_seed(self, seeded):
        assert seeded.get("ok") is True


# ============ Auth ============
class TestAuth:
    def test_register_new_user(self, s):
        email = f"test_{uuid.uuid4().hex[:8]}@labour.app"
        r = s.post(f"{API}/auth/register", json={
            "email": email, "password": "secret123", "name": "TEST User", "role": "customer"
        }, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "token" in data and "user" in data
        assert data["user"]["email"] == email
        _no_underscore_id(data)

    def test_register_duplicate(self, s):
        r = s.post(f"{API}/auth/register", json={
            "email": DEMO_EMAIL, "password": "anything", "name": "Dup"
        }, timeout=15)
        assert r.status_code == 400

    def test_login_demo(self, demo_token):
        assert isinstance(demo_token, str) and len(demo_token) > 10

    def test_login_bad_password(self, s):
        r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": "WRONG"}, timeout=15)
        assert r.status_code == 401

    def test_me(self, s, demo_auth):
        r = s.get(f"{API}/auth/me", headers=demo_auth, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == DEMO_EMAIL
        assert "password_hash" not in body
        _no_underscore_id(body)

    def test_me_no_token(self, s):
        r = s.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 401


# ============ Categories ============
class TestCategories:
    def test_list_categories(self, s):
        r = s.get(f"{API}/categories", timeout=10)
        assert r.status_code == 200
        cats = r.json()
        assert isinstance(cats, list) and len(cats) == 16
        assert all("id" in c and "name" in c for c in cats)


# ============ Workers ============
class TestWorkers:
    def test_list_workers(self, s, seeded):
        r = s.get(f"{API}/workers", timeout=15)
        assert r.status_code == 200
        workers = r.json()
        assert len(workers) >= 20
        _no_underscore_id(workers)

    def test_filter_by_category(self, s):
        r = s.get(f"{API}/workers?category=electrician", timeout=15)
        assert r.status_code == 200
        workers = r.json()
        assert len(workers) > 0
        assert all(w["category"] == "electrician" for w in workers)

    def test_sort_price_asc(self, s):
        r = s.get(f"{API}/workers?sort=price_asc&limit=10", timeout=15)
        assert r.status_code == 200
        ws = r.json()
        wages = [w["daily_wage"] for w in ws]
        assert wages == sorted(wages)

    def test_search(self, s):
        r = s.get(f"{API}/workers?search=ram", timeout=15)
        assert r.status_code == 200
        # search may or may not match Ramesh; just ensure no crash and list returned
        assert isinstance(r.json(), list)

    def test_popular(self, s):
        r = s.get(f"{API}/workers/popular", timeout=15)
        assert r.status_code == 200
        ws = r.json()
        assert isinstance(ws, list) and len(ws) > 0
        # popular should be sorted by rating desc
        ratings = [w.get("rating", 0) for w in ws]
        assert ratings == sorted(ratings, reverse=True)
        _no_underscore_id(ws)

    def test_recommendations(self, s, demo_auth):
        r = s.get(f"{API}/workers/recommendations", headers=demo_auth, timeout=45)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "recommendations" in body and "reasoning" in body
        assert isinstance(body["recommendations"], list)
        _no_underscore_id(body)

    def test_worker_detail(self, s):
        list_r = s.get(f"{API}/workers?limit=1", timeout=15).json()
        wid = list_r[0]["id"]
        r = s.get(f"{API}/workers/{wid}", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == wid
        assert "reviews" in body and isinstance(body["reviews"], list)
        _no_underscore_id(body)

    def test_worker_not_found(self, s):
        r = s.get(f"{API}/workers/does-not-exist", timeout=10)
        assert r.status_code == 404


# ============ Worker Onboarding & Earnings ============
class TestWorkerFlows:
    @pytest.fixture(scope="class")
    def worker_session(self, s):
        email = f"worker_{uuid.uuid4().hex[:8]}@labour.app"
        r = s.post(f"{API}/auth/register", json={
            "email": email, "password": "wkr12345", "name": "TEST Worker", "role": "worker"
        }, timeout=15)
        assert r.status_code == 200
        token = r.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def test_onboard(self, s, worker_session):
        r = s.post(f"{API}/worker/onboard", headers=worker_session, json={
            "category": "electrician", "skills": ["Wiring"], "experience_years": 5,
            "daily_wage": 800, "hourly_wage": 120, "city": "Mumbai"
        }, timeout=15)
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["category"] == "electrician"
        assert p["daily_wage"] == 800
        _no_underscore_id(p)

    def test_status_update(self, s, worker_session):
        r = s.patch(f"{API}/worker/status", headers=worker_session, json={"status": "online"}, timeout=10)
        assert r.status_code == 200
        assert r.json()["status"] == "online"
        r2 = s.patch(f"{API}/worker/status", headers=worker_session, json={"status": "offline"}, timeout=10)
        assert r2.status_code == 200

    def test_earnings(self, s, worker_session):
        r = s.get(f"{API}/worker/earnings", headers=worker_session, timeout=10)
        assert r.status_code == 200
        body = r.json()
        for k in ("today", "week", "month", "total", "balance", "withdrawn", "pending"):
            assert k in body

    def test_withdraw_create_and_list(self, s, worker_session):
        r = s.post(f"{API}/worker/withdraw", headers=worker_session, json={
            "amount": 500, "method": "upi", "upi_id": "test@upi"
        }, timeout=10)
        assert r.status_code == 200
        wd = r.json()
        assert wd["amount"] == 500 and wd["status"] == "pending"

        r2 = s.get(f"{API}/worker/withdrawals", headers=worker_session, timeout=10)
        assert r2.status_code == 200
        wds = r2.json()
        assert any(w["id"] == wd["id"] for w in wds)


# ============ Bookings → Reviews flow ============
class TestBookingReview:
    @pytest.fixture(scope="class")
    def worker_id(self, s):
        return s.get(f"{API}/workers?limit=1", timeout=10).json()[0]["id"]

    @pytest.fixture(scope="class")
    def booking(self, s, demo_auth, worker_id):
        r = s.post(f"{API}/bookings", headers=demo_auth, json={
            "worker_id": worker_id,
            "date": "2026-02-01",
            "time": "09:00",
            "hours": 8,
            "days": 1,
            "address": "TEST address 123",
            "payment_method": "cash",
            "notes": "TEST booking"
        }, timeout=15)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["status"] == "pending"
        _no_underscore_id(b)
        return b

    def test_booking_created(self, booking):
        assert "id" in booking and booking["total"] > 0

    def test_list_my_bookings(self, s, demo_auth, booking):
        r = s.get(f"{API}/bookings", headers=demo_auth, timeout=10)
        assert r.status_code == 200
        bs = r.json()
        assert any(b["id"] == booking["id"] for b in bs)

    def test_complete_booking_and_review(self, s, demo_auth, booking):
        # mark completed (demo is the customer, allowed)
        r = s.patch(f"{API}/bookings/{booking['id']}", headers=demo_auth,
                    json={"status": "completed"}, timeout=10)
        assert r.status_code == 200
        # add review
        rv = s.post(f"{API}/reviews", headers=demo_auth, json={
            "booking_id": booking["id"], "rating": 5, "comment": "TEST review excellent"
        }, timeout=10)
        assert rv.status_code == 200, rv.text
        body = rv.json()
        assert body["rating"] == 5
        _no_underscore_id(body)

        # list worker reviews
        rlist = s.get(f"{API}/reviews/worker/{booking['worker_id']}", timeout=10)
        assert rlist.status_code == 200
        assert any(r2["id"] == body["id"] for r2 in rlist.json())

    def test_review_requires_completion(self, s, demo_auth, worker_id):
        # create new pending booking; reviewing it should fail
        r = s.post(f"{API}/bookings", headers=demo_auth, json={
            "worker_id": worker_id, "date": "2026-02-02", "time": "10:00",
            "hours": 4, "days": 1, "address": "TEST", "payment_method": "cash"
        }, timeout=10)
        bid = r.json()["id"]
        rv = s.post(f"{API}/reviews", headers=demo_auth, json={
            "booking_id": bid, "rating": 4, "comment": "early"
        }, timeout=10)
        assert rv.status_code == 400


# ============ Favorites ============
class TestFavorites:
    def test_favorites_flow(self, s, demo_auth):
        wid = s.get(f"{API}/workers?limit=1", timeout=10).json()[0]["id"]
        r1 = s.post(f"{API}/favorites/{wid}", headers=demo_auth, timeout=10)
        assert r1.status_code == 200

        r2 = s.get(f"{API}/favorites", headers=demo_auth, timeout=10)
        assert r2.status_code == 200
        assert any(w["id"] == wid for w in r2.json())

        r3 = s.delete(f"{API}/favorites/{wid}", headers=demo_auth, timeout=10)
        assert r3.status_code == 200

        r4 = s.get(f"{API}/favorites", headers=demo_auth, timeout=10)
        assert not any(w["id"] == wid for w in r4.json())


# ============ Messaging ============
class TestMessaging:
    def test_send_and_fetch(self, s, demo_auth):
        # create a second user as the peer
        peer_email = f"peer_{uuid.uuid4().hex[:8]}@labour.app"
        rp = s.post(f"{API}/auth/register", json={
            "email": peer_email, "password": "secret123", "name": "TEST Peer"
        }, timeout=15)
        assert rp.status_code == 200
        peer_id = rp.json()["user"]["id"]

        m = s.post(f"{API}/messages", headers=demo_auth, json={
            "to_user_id": peer_id, "content": "TEST hello"
        }, timeout=10)
        assert m.status_code == 200
        msg = m.json()
        assert msg["content"] == "TEST hello"
        _no_underscore_id(msg)

        th = s.get(f"{API}/messages/{peer_id}", headers=demo_auth, timeout=10)
        assert th.status_code == 200
        assert any(x["id"] == msg["id"] for x in th.json())

        ch = s.get(f"{API}/chats", headers=demo_auth, timeout=10)
        assert ch.status_code == 200
        assert any(c["peer_id"] == peer_id for c in ch.json())
