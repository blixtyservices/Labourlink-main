from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Header
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt as pyjwt

import re as _re

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGO = 'HS256'
JWT_EXPIRE_DAYS = 7
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

PUBLIC_WORKER_EXCLUDE = {"_id": 0, "phone": 0, "user_id": 0}
FULL_WORKER_EXCLUDE = {"_id": 0}

app = FastAPI(title="Labour Connect API")
api_router = APIRouter(prefix="/api")

@app.get("/")
async def root():
    return {
        "status": "success",
        "message": "LabourLink Backend is Live 🚀"
    }
# ============ Helpers ============
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False

def create_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid auth header")
    token = authorization.split(" ", 1)[1]
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        user_id = payload["user_id"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# ============ Models ============

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    phone: Optional[str] = None
    role: Literal["customer", "worker"] = "customer"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict


class AdminLogin(BaseModel):
    email: EmailStr
    password: str
   
class WorkerProfileInput(BaseModel):
    category: str
    skills: List[str] = []
    experience_years: int = 0
    daily_wage: int = 500
    hourly_wage: int = 100
    languages: List[str] = ["Hindi", "English"]
    city: str = "Mumbai"
    bio: Optional[str] = ""
    profile_pic: Optional[str] = None
    cover_pic: Optional[str] = None
    available: bool = True

class WorkerStatusUpdate(BaseModel):
    status: Literal["online", "offline", "busy", "working", "break", "unavailable"]

class WithdrawRequest(BaseModel):
    amount: int = Field(gt=0)
    method: Literal["upi", "bank"] = "upi"
    upi_id: Optional[str] = None
    bank_account: Optional[str] = None
    ifsc: Optional[str] = None

class BookingCreate(BaseModel):
    worker_id: str
    date: str  # ISO date
    time: str  # "09:00"
    hours: int = 8
    days: int = 1
    address: str
    payment_method: Literal["cash", "upi", "card"] = "cash"
    notes: Optional[str] = ""

class BookingStatusUpdate(BaseModel):
    status: Literal["accepted", "rejected", "started", "completed", "completed_by_worker", "cancelled"]

class ReviewCreate(BaseModel):
    booking_id: str
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = ""

class MessageCreate(BaseModel):
    to_user_id: str
    content: str

# ============ Categories ============
CATEGORIES = [
    {"id": "mason", "name": "Mason", "icon": "wall", "color": "#E6F5F0"},
    {"id": "electrician", "name": "Electrician", "icon": "bolt", "color": "#FFF4E1"},
    {"id": "plumber", "name": "Plumber", "icon": "wrench", "color": "#E1F0FF"},
    {"id": "carpenter", "name": "Carpenter", "icon": "hammer", "color": "#F5EBE0"},
    {"id": "painter", "name": "Painter", "icon": "brush", "color": "#FFE8E8"},
    {"id": "welder", "name": "Welder", "icon": "flame", "color": "#FFEDD5"},
    {"id": "cleaner", "name": "Cleaner", "icon": "broom", "color": "#E6F5F0"},
    {"id": "driver", "name": "Driver", "icon": "car", "color": "#E1F0FF"},
    {"id": "helper", "name": "Helper", "icon": "person", "color": "#F5F0E6"},
    {"id": "maid", "name": "House Maid", "icon": "house", "color": "#FFE8F0"},
    {"id": "construction", "name": "Construction Labour", "icon": "hardhat", "color": "#FFF4E1"},
    {"id": "ac_tech", "name": "AC Technician", "icon": "snowflake", "color": "#E1F5FE"},
    {"id": "tiles", "name": "Tiles Worker", "icon": "grid", "color": "#F0EBE0"},
    {"id": "pop", "name": "POP Worker", "icon": "layers", "color": "#F5EBE0"},
    {"id": "security", "name": "Security Guard", "icon": "shield", "color": "#E8E8F0"},
    {"id": "gardener", "name": "Gardener", "icon": "leaf", "color": "#E6F5E6"},
]

# ============ AUTH ============
@api_router.post("/auth/register", response_model=AuthResponse)
async def register(body: UserRegister):
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": body.email.lower(),
        "password_hash": hash_password(body.password),
        "name": body.name,
        "phone": body.phone,
        "role": body.role,
        "created_at": now_iso(),
        "avatar": None,
        "city": "Mumbai",
    }
    await db.users.insert_one(user_doc)
    user_doc.pop("password_hash", None)
    user_doc.pop("_id", None)
    return {"token": create_token(user_id), "user": user_doc}

@api_router.post("/auth/login", response_model=AuthResponse)
async def login(body: UserLogin):
    user = await db.users.find_one({"email": body.email.lower()})

    if not user or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    user.pop("password_hash", None)
    user.pop("_id", None)

    return {
        "token": create_token(user["id"]),
        "user": user
    }


# ===========================
# ADMIN LOGIN
# ===========================

@api_router.post("/admin/login")
async def admin_login(body: AdminLogin):

    admin_email = "admin@gmail.com"
    admin_password = "admin123"

    if body.email != admin_email or body.password != admin_password:
        raise HTTPException(
            status_code=401,
            detail="Invalid Credentials"
        )

    return {
        "token": create_token("admin"),
        "admin": {
            "id": "admin",
            "name": "Administrator",
            "email": admin_email,
            "role": "admin"
        }
    }
    
@api_router.get("/auth/me")
async def me(current=Depends(get_current_user)):
    return current

# ============ Categories ============
@api_router.get("/categories")
async def list_categories():
    return CATEGORIES

# ============ Workers ============
@api_router.get("/workers")
async def list_workers(
    category: Optional[str] = None,
    min_rating: Optional[float] = None,
    max_price: Optional[int] = None,
    search: Optional[str] = None,
    sort: Optional[str] = "rating",  # rating, price_asc, price_desc, experience
    limit: int = 50,
):
    query = {}
    if category:
        query["category"] = category
    if min_rating is not None:
        query["rating"] = {"$gte": min_rating}
    if max_price is not None:
        query["daily_wage"] = {"$lte": max_price}
    if search:
        safe = _re.escape(search[:50])
        query["$or"] = [
            {"name": {"$regex": safe, "$options": "i"}},
            {"category": {"$regex": safe, "$options": "i"}},
            {"skills": {"$regex": safe, "$options": "i"}},
        ]
    sort_map = {
        "rating": [("rating", -1)],
        "price_asc": [("daily_wage", 1)],
        "price_desc": [("daily_wage", -1)],
        "experience": [("experience_years", -1)],
    }
    limit = max(1, min(limit, 100))
    cursor = db.workers.find(query, PUBLIC_WORKER_EXCLUDE).sort(sort_map.get(sort, [("rating", -1)])).limit(limit)
    return await cursor.to_list(length=limit)

@api_router.get("/workers/popular")
async def popular_workers(limit: int = 8):
    limit = max(1, min(limit, 50))
    cursor = db.workers.find({}, PUBLIC_WORKER_EXCLUDE).sort([("rating", -1), ("jobs_completed", -1)]).limit(limit)
    return await cursor.to_list(length=limit)

@api_router.get("/workers/recommendations")
async def ai_recommendations(category: Optional[str] = None, current=Depends(get_current_user)):
    """Use Claude to rank top workers based on user profile + category."""
    q = {"category": category} if category else {}
    workers = await db.workers.find(q, PUBLIC_WORKER_EXCLUDE).limit(30).to_list(length=30)
    if not workers:
        return {"recommendations": [], "reasoning": "No workers available"}
    # Try AI ranking; fallback to rating-based sort
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        worker_brief = [
            {"id": w["id"], "name": w["name"], "category": w["category"],
             "rating": w.get("rating", 0), "jobs": w.get("jobs_completed", 0),
             "exp": w.get("experience_years", 0), "wage": w.get("daily_wage", 0)}
            for w in workers
        ]
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"reco-{current['id']}-{category or 'all'}",
            system_message="You are a smart hiring assistant for a daily-wage worker marketplace. Pick the top 5 workers from a JSON list based on rating, jobs completed, experience, and value-for-money. Respond ONLY with a JSON array of worker IDs in best-to-worst order, like [\"id1\",\"id2\",\"id3\",\"id4\",\"id5\"]. No other text."
        ).with_model("anthropic", "claude-sonnet-4-6")
        import json
        msg = UserMessage(text=f"Customer in {current.get('city','Mumbai')}. Workers: {json.dumps(worker_brief)}. Return top 5 IDs as JSON array.")
        response = await chat.send_message(msg)
        # Parse JSON array out of response
        import re
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        if match:
            ids = json.loads(match.group(0))
            id_map = {w["id"]: w for w in workers}
            top = [id_map[i] for i in ids if i in id_map][:5]
            if top:
                return {"recommendations": top, "reasoning": "AI-ranked best matches for you"}
    except Exception as e:
        logging.warning(f"AI reco failed: {e}")
    # Fallback
    workers.sort(key=lambda w: (w.get("rating", 0), w.get("jobs_completed", 0)), reverse=True)
    return {"recommendations": workers[:5], "reasoning": "Top-rated workers"}

@api_router.get("/workers/{worker_id}")
async def get_worker(worker_id: str):
    worker = await db.workers.find_one({"id": worker_id}, PUBLIC_WORKER_EXCLUDE)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    # Attach recent reviews
    reviews = await db.reviews.find({"worker_id": worker_id}, {"_id": 0}).sort([("created_at", -1)]).limit(10).to_list(length=10)
    worker["reviews"] = reviews
    return worker

@api_router.post("/worker/onboard")
async def worker_onboard(body: WorkerProfileInput, current=Depends(get_current_user)):
    # Make this user a worker and create/update worker profile
    await db.users.update_one({"id": current["id"]}, {"$set": {"role": "worker"}})
    existing = await db.workers.find_one({"user_id": current["id"]})
    profile = {
        "id": existing["id"] if existing else str(uuid.uuid4()),
        "user_id": current["id"],
        "name": current["name"],
        "phone": current.get("phone"),
        "category": body.category,
        "skills": body.skills,
        "experience_years": body.experience_years,
        "daily_wage": body.daily_wage,
        "hourly_wage": body.hourly_wage,
        "languages": body.languages,
        "city": body.city,
        "bio": body.bio,
        "profile_pic": body.profile_pic or "https://images.unsplash.com/photo-1679679811837-c28b2586f533?w=400",
        "cover_pic": body.cover_pic or "https://images.unsplash.com/photo-1541140134513-85a161dc4a00?w=800",
        "available": body.available,
        "rating": existing.get("rating", 0) if existing else 0,
        "jobs_completed": existing.get("jobs_completed", 0) if existing else 0,
        "review_count": existing.get("review_count", 0) if existing else 0,
        # Only admin (or KYC service) can set verified=True. Self-onboard is unverified.
        "verified": existing.get("verified", False) if existing else False,
        "created_at": existing.get("created_at", now_iso()) if existing else now_iso(),
    }
    if existing:
        await db.workers.update_one({"id": existing["id"]}, {"$set": profile})
    else:
        await db.workers.insert_one(profile)
    profile.pop("_id", None)
    return profile

@api_router.get("/worker/me")
async def my_worker_profile(current=Depends(get_current_user)):
    w = await db.workers.find_one({"user_id": current["id"]}, {"_id": 0})
    if not w:
        raise HTTPException(status_code=404, detail="Not a worker yet")
    return w

@api_router.patch("/worker/status")
async def update_worker_status(body: WorkerStatusUpdate, current=Depends(get_current_user)):
    w = await db.workers.find_one({"user_id": current["id"]})
    if not w:
        raise HTTPException(status_code=404, detail="Worker profile not found")
    await db.workers.update_one(
        {"id": w["id"]},
        {"$set": {"status": body.status, "available": body.status == "online", "last_active": now_iso()}}
    )
    return {"ok": True, "status": body.status}

@api_router.get("/worker/earnings")
async def worker_earnings(current=Depends(get_current_user)):
    w = await db.workers.find_one({"user_id": current["id"]})
    if not w:
        raise HTTPException(status_code=404, detail="Not a worker")
    bookings = await db.bookings.find({"worker_id": w["id"], "status": "completed"}, {"_id": 0}).to_list(length=1000)
    pending = await db.bookings.find({"worker_id": w["id"], "status": {"$in": ["accepted", "started"]}}, {"_id": 0}).to_list(length=1000)
    today = datetime.now(timezone.utc).date().isoformat()
    week_start = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    month_start = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    total = sum(b["total"] for b in bookings)
    today_amt = sum(b["total"] for b in bookings if b.get("updated_at", b["created_at"]).startswith(today))
    week_amt = sum(b["total"] for b in bookings if b.get("updated_at", b["created_at"]) >= week_start)
    month_amt = sum(b["total"] for b in bookings if b.get("updated_at", b["created_at"]) >= month_start)
    pending_amt = sum(b["total"] for b in pending)
    # Withdrawals
    withdrawals = await db.withdrawals.find({"worker_id": w["id"]}, {"_id": 0}).to_list(length=1000)
    withdrawn = sum(wd["amount"] for wd in withdrawals if wd.get("status") == "completed")
    balance = total - withdrawn
    return {
        "today": today_amt, "week": week_amt, "month": month_amt, "total": total,
        "pending": pending_amt, "balance": balance, "withdrawn": withdrawn,
        "jobs_completed": len(bookings), "jobs_pending": len(pending),
    }

@api_router.post("/worker/withdraw")
async def create_withdrawal(body: WithdrawRequest, current=Depends(get_current_user)):
    w = await db.workers.find_one({"user_id": current["id"]})
    if not w:
        raise HTTPException(status_code=404, detail="Not a worker")
    # Server-side balance check — cannot withdraw more than verified completed earnings minus prior withdrawals
    completed = await db.bookings.find(
        {"worker_id": w["id"], "status": "completed"}, {"_id": 0, "total": 1}
    ).to_list(length=10000)
    earned = sum(b["total"] for b in completed)
    prior = await db.withdrawals.find(
        {"worker_id": w["id"], "status": {"$in": ["pending", "completed"]}}, {"_id": 0, "amount": 1}
    ).to_list(length=10000)
    locked = sum(x["amount"] for x in prior)
    balance = earned - locked
    if body.amount > balance:
        raise HTTPException(status_code=400, detail=f"Amount exceeds available balance (₹{balance})")
    wd = {
        "id": str(uuid.uuid4()),
        "worker_id": w["id"],
        "amount": body.amount,
        "method": body.method,
        "upi_id": body.upi_id,
        "bank_account": body.bank_account,
        "ifsc": body.ifsc,
        "status": "pending",
        "created_at": now_iso(),
    }
    await db.withdrawals.insert_one(wd)
    wd.pop("_id", None)
    return wd

@api_router.get("/worker/withdrawals")
async def list_withdrawals(current=Depends(get_current_user)):
    w = await db.workers.find_one({"user_id": current["id"]})
    if not w:
        return []
    cursor = db.withdrawals.find({"worker_id": w["id"]}, {"_id": 0}).sort([("created_at", -1)])
    return await cursor.to_list(length=200)

# ============ Bookings ============
@api_router.post("/bookings")
async def create_booking(body: BookingCreate, current=Depends(get_current_user)):
    worker = await db.workers.find_one({"id": body.worker_id}, {"_id": 0})
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    total = worker["daily_wage"] * body.days
    booking = {
        "id": str(uuid.uuid4()),
        "customer_id": current["id"],
        "customer_name": current["name"],
        "worker_id": body.worker_id,
        "worker_name": worker["name"],
        "worker_category": worker["category"],
        "worker_avatar": worker.get("profile_pic"),
        "date": body.date,
        "time": body.time,
        "hours": body.hours,
        "days": body.days,
        "address": body.address,
        "payment_method": body.payment_method,
        "notes": body.notes,
        "total": total,
        "status": "pending",
        "created_at": now_iso(),
    }
    await db.bookings.insert_one(booking)
    booking.pop("_id", None)
    return booking

@api_router.get("/bookings")
async def my_bookings(current=Depends(get_current_user)):
    if current["role"] == "worker":
        w = await db.workers.find_one({"user_id": current["id"]})
        if not w:
            return []
        cursor = db.bookings.find({"worker_id": w["id"]}, {"_id": 0}).sort([("created_at", -1)])
    else:
        cursor = db.bookings.find({"customer_id": current["id"]}, {"_id": 0}).sort([("created_at", -1)])
    return await cursor.to_list(length=200)

# ==========================
# ADMIN - ALL BOOKINGS
# ==========================

@api_router.get("/admin/bookings")
async def admin_bookings():

    cursor = db.bookings.find({}, {"_id": 0}).sort("created_at", -1)

    bookings = await cursor.to_list(length=500)

    return bookings

@api_router.patch("/bookings/{booking_id}")
async def update_booking(booking_id: str, body: BookingStatusUpdate, current=Depends(get_current_user)):
    booking = await db.bookings.find_one({"id": booking_id})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    is_customer = booking["customer_id"] == current["id"]
    worker = await db.workers.find_one({"user_id": current["id"]})
    is_worker = worker and booking["worker_id"] == worker["id"]
    if not (is_customer or is_worker):
        raise HTTPException(status_code=403, detail="Not allowed")

    # Authorization & state machine — workers cannot self-complete to fabricate earnings.
    current_status = booking.get("status", "pending")
    new_status = body.status
    role_allowed = {
        "worker":   {"pending": {"accepted", "rejected"}, "accepted": {"started"}, "started": {"completed_by_worker"}},
        "customer": {"pending": {"cancelled"}, "accepted": {"cancelled"}, "started": {"cancelled"}, "completed_by_worker": {"completed"}},
    }
    # Map external API state -> internal allowed transition
    requested_role = "customer" if is_customer else "worker"
    # Worker requests "completed" -> map to intermediate "completed_by_worker"
    effective_new = new_status
    if requested_role == "worker" and new_status == "completed":
        effective_new = "completed_by_worker"

    allowed_next = role_allowed.get(requested_role, {}).get(current_status, set())
    if effective_new not in allowed_next:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {requested_role} cannot move from '{current_status}' to '{new_status}'",
        )

    await db.bookings.update_one({"id": booking_id}, {"$set": {"status": effective_new, "updated_at": now_iso()}})
    # Increment worker jobs_completed only when CUSTOMER confirms completion
    if effective_new == "completed":
        await db.workers.update_one({"id": booking["worker_id"]}, {"$inc": {"jobs_completed": 1}})
    return {"ok": True, "status": effective_new}

# ============ Reviews ============
@api_router.post("/reviews")
async def add_review(body: ReviewCreate, current=Depends(get_current_user)):
    booking = await db.bookings.find_one({"id": body.booking_id})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking["customer_id"] != current["id"]:
        raise HTTPException(status_code=403, detail="Only customer can review")
    if booking["status"] != "completed":
        raise HTTPException(status_code=400, detail="Booking not completed yet")
    # One review per booking (idempotent)
    if await db.reviews.find_one({"booking_id": body.booking_id, "customer_id": current["id"]}):
        raise HTTPException(status_code=400, detail="You have already reviewed this booking")
    review = {
        "id": str(uuid.uuid4()),
        "booking_id": body.booking_id,
        "worker_id": booking["worker_id"],
        "customer_id": current["id"],
        "customer_name": current["name"],
        "rating": body.rating,
        "comment": body.comment,
        "created_at": now_iso(),
    }
    await db.reviews.insert_one(review)
    # Recompute worker rating
    all_reviews = await db.reviews.find({"worker_id": booking["worker_id"]}).to_list(length=1000)
    avg = sum(r["rating"] for r in all_reviews) / len(all_reviews)
    await db.workers.update_one(
        {"id": booking["worker_id"]},
        {"$set": {"rating": round(avg, 1), "review_count": len(all_reviews)}}
    )
    review.pop("_id", None)
    return review

@api_router.get("/reviews/worker/{worker_id}")
async def worker_reviews(worker_id: str):
    cursor = db.reviews.find({"worker_id": worker_id}, {"_id": 0}).sort([("created_at", -1)])
    return await cursor.to_list(length=100)

# ============ Favorites ============
@api_router.post("/favorites/{worker_id}")
async def add_favorite(worker_id: str, current=Depends(get_current_user)):
    await db.favorites.update_one(
        {"customer_id": current["id"], "worker_id": worker_id},
        {"$set": {"customer_id": current["id"], "worker_id": worker_id, "created_at": now_iso()}},
        upsert=True,
    )
    return {"ok": True}

@api_router.delete("/favorites/{worker_id}")
async def remove_favorite(worker_id: str, current=Depends(get_current_user)):
    await db.favorites.delete_one({"customer_id": current["id"], "worker_id": worker_id})
    return {"ok": True}

@api_router.get("/favorites")
async def list_favorites(current=Depends(get_current_user)):
    favs = await db.favorites.find({"customer_id": current["id"]}, {"_id": 0}).to_list(length=200)
    worker_ids = [f["worker_id"] for f in favs]
    if not worker_ids:
        return []
    workers = await db.workers.find({"id": {"$in": worker_ids}}, {"_id": 0}).to_list(length=200)
    return workers

# ============ Chat (simple polling) ============
@api_router.post("/messages")
async def send_message(body: MessageCreate, current=Depends(get_current_user)):
    msg = {
        "id": str(uuid.uuid4()),
        "from_user_id": current["id"],
        "from_user_name": current["name"],
        "to_user_id": body.to_user_id,
        "content": body.content,
        "created_at": now_iso(),
        "read": False,
    }
    await db.messages.insert_one(msg)
    msg.pop("_id", None)
    return msg

@api_router.get("/messages/{other_user_id}")
async def get_thread(other_user_id: str, current=Depends(get_current_user)):
    cursor = db.messages.find({
        "$or": [
            {"from_user_id": current["id"], "to_user_id": other_user_id},
            {"from_user_id": other_user_id, "to_user_id": current["id"]},
        ]
    }, {"_id": 0}).sort([("created_at", 1)])
    msgs = await cursor.to_list(length=500)
    # Mark received as read
    await db.messages.update_many(
        {"from_user_id": other_user_id, "to_user_id": current["id"], "read": False},
        {"$set": {"read": True}}
    )
    return msgs

@api_router.get("/chats")
async def my_chats(current=Depends(get_current_user)):
    # Return distinct conversation peers with last message
    pipeline = [
        {"$match": {"$or": [{"from_user_id": current["id"]}, {"to_user_id": current["id"]}]}},
        {"$sort": {"created_at": -1}},
    ]
    msgs = await db.messages.aggregate(pipeline).to_list(length=500)
    seen = {}
    for m in msgs:
        peer = m["to_user_id"] if m["from_user_id"] == current["id"] else m["from_user_id"]
        if peer not in seen:
            seen[peer] = m
    # Enrich with peer name from users or workers
    out = []
    for peer_id, last_msg in seen.items():
        user = await db.users.find_one({"id": peer_id}, {"_id": 0, "password_hash": 0})
        worker = await db.workers.find_one({"user_id": peer_id}, {"_id": 0})
        out.append({
            "peer_id": peer_id,
            "peer_name": (worker or user or {}).get("name", "User"),
            "peer_avatar": (worker or {}).get("profile_pic") or (user or {}).get("avatar"),
            "last_message": last_msg["content"],
            "last_at": last_msg["created_at"],
        })
    return out

# ============ Seed ============
@api_router.post("/seed")
async def seed_data():
    """Seed sample workers and a demo customer."""
    # Demo customer
    demo_email = "demo@labour.app"
    if not await db.users.find_one({"email": demo_email}):
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": demo_email,
            "password_hash": hash_password("demo1234"),
            "name": "Demo Customer",
            "phone": "+919999999999",
            "role": "customer",
            "city": "Mumbai",
            "created_at": now_iso(),
            "avatar": None,
        })

    if await db.workers.count_documents({}) >= 20:
        return {"ok": True, "msg": "already seeded"}

    # Sample data per category
    avatar_pool = [
        "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400",
        "https://images.unsplash.com/photo-1607990281513-2c110a25bd8c?w=400",
        "https://images.unsplash.com/photo-1531123897727-8f129e1688ce?w=400",
        "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400",
        "https://images.unsplash.com/photo-1614283233556-f35b0c801ef1?w=400",
        "https://images.unsplash.com/photo-1542178243-bc20204b769f?w=400",
        "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=400",
        "https://images.unsplash.com/photo-1492562080023-ab3db95bfbce?w=400",
        "https://images.unsplash.com/photo-1545167622-3a6ac756afa4?w=400",
        "https://images.unsplash.com/photo-1463453091185-61582044d556?w=400",
    ]
    covers = [
        "https://images.unsplash.com/photo-1541140134513-85a161dc4a00?w=800",
        "https://images.unsplash.com/photo-1621905251189-08b45d6a269e?w=800",
        "https://images.unsplash.com/photo-1589939705384-5185137a7f0f?w=800",
    ]
    first_names = ["Ramesh", "Suresh", "Mahesh", "Dinesh", "Rakesh", "Vinod", "Anil", "Sanjay", "Prakash", "Kishore",
                   "Mohan", "Sohan", "Rahul", "Amit", "Vikram", "Ashok", "Rajesh", "Manoj", "Naveen", "Deepak",
                   "Lakshmi", "Sunita", "Kavita", "Geeta", "Priya"]
    cities = ["Mumbai", "Delhi", "Bangalore", "Pune", "Hyderabad", "Chennai"]
    cats = [c["id"] for c in CATEGORIES]
    skills_map = {
        "mason": ["Brick laying", "Plastering", "Stone work"],
        "electrician": ["Wiring", "Switch installation", "Fan repair", "Inverter setup"],
        "plumber": ["Pipe fitting", "Leak repair", "Tap installation", "Drain cleaning"],
        "carpenter": ["Furniture", "Door fitting", "Wood polish", "Repairs"],
        "painter": ["Interior painting", "Texture", "Wall prep", "Exterior"],
        "welder": ["Arc welding", "Gas welding", "Gate fabrication"],
        "cleaner": ["Deep cleaning", "Bathroom cleaning", "Kitchen scrubbing"],
        "driver": ["Light vehicle", "Highway driving", "City navigation"],
        "helper": ["Lifting", "Loading", "Site assistance"],
        "maid": ["Sweeping", "Mopping", "Utensils", "Laundry"],
        "construction": ["Excavation", "Concrete mixing", "Reinforcement"],
        "ac_tech": ["AC service", "Gas refill", "Installation"],
        "tiles": ["Floor tiles", "Wall tiles", "Grouting"],
        "pop": ["False ceiling", "POP designs", "Cornices"],
        "security": ["Night duty", "Premises patrol", "Visitor check"],
        "gardener": ["Lawn care", "Plant care", "Pruning"],
    }
    import random
    random.seed(42)
    docs = []
    for i in range(32):
        cat = cats[i % len(cats)]
        name = f"{first_names[i % len(first_names)]} {chr(65 + (i%10))}."
        docs.append({
            "id": str(uuid.uuid4()),
            "user_id": None,
            "name": name,
            "phone": f"+9198{random.randint(10000000, 99999999)}",
            "category": cat,
            "skills": skills_map.get(cat, []),
            "experience_years": random.randint(2, 18),
            "daily_wage": random.choice([500, 600, 700, 800, 900, 1000, 1200, 1500]),
            "hourly_wage": random.choice([80, 100, 120, 150, 180, 200]),
            "languages": random.choice([["Hindi"], ["Hindi", "English"], ["Hindi", "English", "Marathi"], ["Hindi", "Tamil"]]),
            "city": random.choice(cities),
            "bio": f"Experienced {cat.replace('_',' ')} with proven track record. Punctual, honest, and skilled.",
            "profile_pic": random.choice(avatar_pool),
            "cover_pic": random.choice(covers),
            "available": random.choice([True, True, True, False]),
            "rating": round(random.uniform(3.8, 5.0), 1),
            "jobs_completed": random.randint(15, 280),
            "review_count": random.randint(5, 120),
            "verified": True,
            "status": random.choice(["online", "online", "online", "offline", "busy"]),
            "last_active": now_iso(),
            "distance_km": round(random.uniform(0.5, 8.5), 1),
            "created_at": now_iso(),
        })
    await db.workers.insert_many(docs)
    return {"ok": True, "workers_seeded": len(docs)}

# ============ Health ============

# ===========================
# ADMIN DASHBOARD
# ===========================

@api_router.get("/admin/dashboard")
async def admin_dashboard():

    total_users = await db.users.count_documents({"role": "customer"})
    total_workers = await db.users.count_documents({"role": "worker"})
    total_bookings = await db.bookings.count_documents({})
    pending_bookings = await db.bookings.count_documents({"status": "pending"})
    completed_bookings = await db.bookings.count_documents({"status": "completed"})
    total_withdrawals = await db.withdrawals.count_documents({})
    pending_withdrawals = await db.withdrawals.count_documents({"status": "pending"})

    return {
        "total_users": total_users,
        "total_workers": total_workers,
        "total_bookings": total_bookings,
        "pending_bookings": pending_bookings,
        "completed_bookings": completed_bookings,
        "total_withdrawals": total_withdrawals,
        "pending_withdrawals": pending_withdrawals
    }

# ============ Health ============


@api_router.get("/")
async def root():
    return {"message": "Labour Connect API"}

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup():
    print("=== STARTUP BEGIN ===")

    try:
        await db.command("ping")
        print("✅ MongoDB Connected Successfully")
    except Exception as e:
        print("❌ MongoDB Error:", e)
        raise

    print("Creating indexes...")

    await db.users.create_index("email", unique=True)
    print("users index created")

    await db.workers.create_index("category")
    print("workers category index created")

    await db.workers.create_index("rating")
    print("workers rating index created")

    await db.bookings.create_index("customer_id")
    print("booking customer index created")

    await db.bookings.create_index("worker_id")
    print("booking worker index created")

    await db.reviews.create_index(
        [("booking_id", 1), ("customer_id", 1)],
        unique=True
    )
    print("reviews index created")

    await db.messages.create_index(
        [("from_user_id", 1), ("to_user_id", 1), ("created_at", 1)]
    )
    print("messages index created")

    print("✅ STARTUP COMPLETE")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
    )
    
    