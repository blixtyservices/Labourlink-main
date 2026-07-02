"""LabourLink AI - Security Audit Fix Verification.

Verifies SEC-001..SEC-005 fixes:
 - Booking state machine (worker cannot self-complete)
 - Withdrawal balance cap
 - jobs_completed only on customer confirm
 - JWT secret strength + 7-day expiry
 - Worker public endpoints exclude phone/user_id
 - Duplicate reviews blocked (unique index)
 - Self-onboarded worker NOT auto-verified
 - Search regex escaping
 - Existing flows still pass
"""
import os
import re
import time
import uuid
import base64
import json
import pytest
import requests

BASE_URL = os.environ.get(
    "EXPO_PUBLIC_BACKEND_URL",
    "https://skill-match-252.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@labour.app"
DEMO_PASS = "demo1234"


# ---------------- Fixtures ----------------
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
def customer_token(s, seeded):
    r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASS}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def customer_headers(customer_token):
    return {"Authorization": f"Bearer {customer_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def fresh_worker(s):
    """Register a NEW worker user + onboard them. Returns (token, worker_profile)."""
    email = f"TEST_worker_{uuid.uuid4().hex[:10]}@example.com"
    r = s.post(f"{API}/auth/register", json={
        "email": email, "password": "Worker@123", "name": "Test Worker SEC",
        "phone": "+919800000000", "role": "worker",
    }, timeout=15)
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r2 = s.post(f"{API}/worker/onboard", headers=headers, json={
        "category": "plumber", "skills": ["Pipe fitting"], "experience_years": 3,
        "daily_wage": 700, "hourly_wage": 120, "languages": ["Hindi", "English"],
        "city": "Mumbai", "bio": "test", "available": True,
    }, timeout=15)
    assert r2.status_code == 200, r2.text
    return {"token": token, "headers": headers, "profile": r2.json(), "email": email}


# ---------------- SEC-002: JWT secret + expiry ----------------
class TestSEC002JWT:
    def test_jwt_secret_strength(self):
        """JWT_SECRET must not be the default and must be >=40 chars."""
        env_path = "/app/backend/.env"
        with open(env_path) as f:
            content = f.read()
        m = re.search(r'JWT_SECRET\s*=\s*"?([^"\n]+)"?', content)
        assert m, "JWT_SECRET not found in .env"
        secret = m.group(1).strip().strip('"')
        assert "change-in-prod" not in secret.lower(), "JWT_SECRET still default"
        assert len(secret) >= 40, f"JWT_SECRET too short ({len(secret)} chars)"

    def test_jwt_expiry_7_days(self, customer_token):
        """Decode JWT (without verifying) and check exp is ~7 days from now."""
        parts = customer_token.split(".")
        assert len(parts) == 3
        # base64 url-safe decode
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload["exp"]
        iat = payload["iat"]
        delta_days = (exp - iat) / 86400.0
        assert 6.9 <= delta_days <= 7.1, f"JWT expiry should be ~7 days, got {delta_days:.2f}"


# ---------------- SEC-003: Public worker endpoints exclude phone/user_id ----------------
class TestSEC003WorkerPII:
    def _assert_no_pii(self, obj):
        if isinstance(obj, dict):
            assert "phone" not in obj, f"phone leaked in payload: keys={list(obj.keys())}"
            assert "user_id" not in obj, f"user_id leaked in payload: keys={list(obj.keys())}"

    def test_list_workers_no_pii(self, s, seeded):
        r = s.get(f"{API}/workers?limit=20", timeout=10)
        assert r.status_code == 200
        workers = r.json()
        assert isinstance(workers, list) and len(workers) > 0
        for w in workers:
            self._assert_no_pii(w)

    def test_popular_workers_no_pii(self, s, seeded):
        r = s.get(f"{API}/workers/popular?limit=8", timeout=10)
        assert r.status_code == 200
        for w in r.json():
            self._assert_no_pii(w)

    def test_worker_detail_no_pii(self, s, seeded):
        wlist = s.get(f"{API}/workers?limit=1", timeout=10).json()
        wid = wlist[0]["id"]
        r = s.get(f"{API}/workers/{wid}", timeout=10)
        assert r.status_code == 200
        self._assert_no_pii(r.json())

    def test_recommendations_no_pii(self, s, customer_headers):
        r = s.get(f"{API}/workers/recommendations?category=plumber", headers=customer_headers, timeout=60)
        assert r.status_code == 200
        for w in r.json().get("recommendations", []):
            self._assert_no_pii(w)


# ---------------- SEC-005: Search regex escaping ----------------
class TestSEC005SearchRegex:
    def test_regex_special_chars_escaped(self, s, seeded):
        # Total count baseline
        total = len(s.get(f"{API}/workers?limit=100", timeout=10).json())
        assert total > 0
        # .* would match everything if NOT escaped
        r = s.get(f"{API}/workers?search=.*&limit=100", timeout=10)
        assert r.status_code == 200
        matched = r.json()
        # No worker should literally contain '.*' in name/category/skills
        assert len(matched) < total, (
            f"search='.*' matched {len(matched)} of {total} workers — regex NOT escaped"
        )
        # Ideally zero matches (no real data has '.*')
        assert len(matched) == 0, f"search='.*' should match 0 (literal), got {len(matched)}"


# ---------------- SEC-004 (b): Self-onboarded worker not auto-verified ----------------
class TestSEC004SelfOnboardUnverified:
    def test_fresh_worker_not_verified(self, fresh_worker):
        prof = fresh_worker["profile"]
        assert prof.get("verified") is False, f"Self-onboarded worker should be unverified, got {prof.get('verified')}"


# ---------------- SEC-001: Booking state machine + SEC-004(a) duplicate reviews ----------------
class TestSEC001BookingStateMachine:
    @pytest.fixture(scope="class")
    def booking_ctx(self, s, customer_headers, fresh_worker):
        """Customer creates a booking against the fresh worker."""
        worker_id = fresh_worker["profile"]["id"]
        r = s.post(f"{API}/bookings", headers=customer_headers, json={
            "worker_id": worker_id,
            "date": "2026-02-01",
            "time": "09:00",
            "hours": 8,
            "days": 1,
            "address": "Test Address 123",
            "payment_method": "cash",
            "notes": "sec test",
        }, timeout=15)
        assert r.status_code == 200, r.text
        booking = r.json()
        assert booking["status"] == "pending"
        return {"booking_id": booking["id"], "worker_id": worker_id}

    def test_01_worker_accepts(self, s, fresh_worker, booking_ctx):
        r = s.patch(f"{API}/bookings/{booking_ctx['booking_id']}",
                    headers=fresh_worker["headers"],
                    json={"status": "accepted"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "accepted"

    def test_02_worker_starts(self, s, fresh_worker, booking_ctx):
        r = s.patch(f"{API}/bookings/{booking_ctx['booking_id']}",
                    headers=fresh_worker["headers"],
                    json={"status": "started"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "started"

    def test_03_worker_cannot_self_complete(self, s, fresh_worker, booking_ctx):
        """SEC-001: Worker sends status='completed', server must map to 'completed_by_worker'."""
        r = s.patch(f"{API}/bookings/{booking_ctx['booking_id']}",
                    headers=fresh_worker["headers"],
                    json={"status": "completed"}, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "completed_by_worker", (
            f"Worker self-complete must map to completed_by_worker, got {body['status']}"
        )
        # Verify persisted state
        bookings = s.get(f"{API}/bookings", headers=fresh_worker["headers"], timeout=10).json()
        match = next((b for b in bookings if b["id"] == booking_ctx["booking_id"]), None)
        assert match and match["status"] == "completed_by_worker"

    def test_04_jobs_completed_not_incremented_yet(self, s, fresh_worker, booking_ctx):
        """jobs_completed must NOT increment when worker marks completed_by_worker."""
        r = s.get(f"{API}/workers/{booking_ctx['worker_id']}", timeout=10)
        assert r.status_code == 200
        assert r.json().get("jobs_completed", 0) == 0, (
            "jobs_completed leaked before customer confirmation"
        )

    def test_05_customer_confirms_completed(self, s, customer_headers, booking_ctx):
        r = s.patch(f"{API}/bookings/{booking_ctx['booking_id']}",
                    headers=customer_headers,
                    json={"status": "completed"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "completed"

    def test_06_jobs_completed_incremented(self, s, booking_ctx):
        r = s.get(f"{API}/workers/{booking_ctx['worker_id']}", timeout=10)
        assert r.status_code == 200
        assert r.json().get("jobs_completed", 0) == 1, "jobs_completed should be 1 after customer confirm"

    def test_07_review_succeeds_once(self, s, customer_headers, booking_ctx):
        r = s.post(f"{API}/reviews", headers=customer_headers, json={
            "booking_id": booking_ctx["booking_id"],
            "rating": 5,
            "comment": "sec test review",
        }, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["rating"] == 5

    def test_08_duplicate_review_blocked(self, s, customer_headers, booking_ctx):
        """SEC-004: second review for same booking must 400."""
        r = s.post(f"{API}/reviews", headers=customer_headers, json={
            "booking_id": booking_ctx["booking_id"],
            "rating": 4,
            "comment": "dup",
        }, timeout=15)
        assert r.status_code == 400, f"Duplicate review must be blocked, got {r.status_code}: {r.text}"


# ---------------- SEC-001(b): Withdrawal balance cap ----------------
class TestSEC001Withdrawal:
    def test_withdraw_above_balance_rejected(self, s, fresh_worker):
        """A fresh worker with completed earnings should not be able to withdraw > balance."""
        # Get earnings first
        e = s.get(f"{API}/worker/earnings", headers=fresh_worker["headers"], timeout=10).json()
        balance = e.get("balance", 0)
        r = s.post(f"{API}/worker/withdraw", headers=fresh_worker["headers"],
                   json={"amount": balance + 100000, "method": "upi", "upi_id": "test@upi"}, timeout=15)
        assert r.status_code == 400, f"Expected 400 over-balance, got {r.status_code}: {r.text}"
        assert "exceeds available balance" in r.text.lower()

    def test_withdraw_valid_amount(self, s, fresh_worker):
        """If balance > 0 after the booking test, a valid withdrawal succeeds; else expect 400."""
        e = s.get(f"{API}/worker/earnings", headers=fresh_worker["headers"], timeout=10).json()
        balance = e.get("balance", 0)
        if balance <= 0:
            pytest.skip(f"No earnings to withdraw (balance={balance}); booking test order may differ")
        r = s.post(f"{API}/worker/withdraw", headers=fresh_worker["headers"],
                   json={"amount": min(100, balance), "method": "upi", "upi_id": "test@upi"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending"


# ---------------- Existing-flow smoke: favorites + chat ----------------
class TestExistingFlows:
    def test_favorites_add_list_remove(self, s, customer_headers):
        wid = s.get(f"{API}/workers?limit=1", timeout=10).json()[0]["id"]
        r1 = s.post(f"{API}/favorites/{wid}", headers=customer_headers, timeout=10)
        assert r1.status_code == 200
        r2 = s.get(f"{API}/favorites", headers=customer_headers, timeout=10).json()
        assert any(w["id"] == wid for w in r2)
        r3 = s.delete(f"{API}/favorites/{wid}", headers=customer_headers, timeout=10)
        assert r3.status_code == 200

    def test_chat_send_and_receive(self, s, customer_headers, fresh_worker):
        # customer -> worker user_id
        worker_user = s.get(f"{API}/auth/me", headers=fresh_worker["headers"], timeout=10).json()
        peer_id = worker_user["id"]
        r1 = s.post(f"{API}/messages", headers=customer_headers,
                    json={"to_user_id": peer_id, "content": "hello from sec test"}, timeout=10)
        assert r1.status_code == 200
        r2 = s.get(f"{API}/messages/{peer_id}", headers=customer_headers, timeout=10)
        assert r2.status_code == 200
        contents = [m["content"] for m in r2.json()]
        assert "hello from sec test" in contents
