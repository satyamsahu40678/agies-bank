from datetime import timedelta, timezone
import hashlib
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select, delete, func
from .config import ALLOWED_ORIGINS, PRODUCTION, SESSION_SECONDS
from .db import get_db
from .models import AuthSession, User, LoginAttempt, utcnow

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = hasher.hash("constant-timing-invalid-password")


def hash_password(password):
    return hasher.hash(password)


def verify_password(password, hashed):
    try:
        return hasher.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def origin_check(request: Request):
    origin = request.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        raise HTTPException(403, "Origin is not allowed")


def session_user(request: Request, db=Depends(get_db)):
    token = request.cookies.get("aegis_session", "")
    session = db.get(AuthSession, digest(token)) if token else None
    if not session:
        raise HTTPException(401, "Please sign in")
    expires = (
        session.expires_at.replace(tzinfo=timezone.utc)
        if session.expires_at.tzinfo is None
        else session.expires_at
    )
    if expires <= utcnow():
        db.delete(session)
        db.commit()
        raise HTTPException(401, "Session expired; please sign in again")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin_check(request)
        if not secrets.compare_digest(
            request.headers.get("X-CSRF-Token", ""), session.csrf_token
        ):
            raise HTTPException(403, "Invalid CSRF token")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "Please sign in")
    request.state.auth_session = session
    return user


def customer(user=Depends(session_user)):
    if user.role != "customer":
        raise HTTPException(403, "Customer role required")
    return user


def analyst(user=Depends(session_user)):
    if user.role != "analyst":
        raise HTTPException(403, "Analyst role required")
    return user


def create_session(db, user, request, response):
    old_token = request.cookies.get("aegis_session")
    if old_token:
        db.execute(delete(AuthSession).where(AuthSession.id == digest(old_token)))
    db.execute(delete(AuthSession).where(AuthSession.expires_at < utcnow()))
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            id=digest(token),
            user_id=user.id,
            csrf_token=csrf,
            expires_at=utcnow() + timedelta(seconds=SESSION_SECONDS),
        )
    )
    response.set_cookie(
        "aegis_session",
        token,
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=PRODUCTION,
        samesite="lax",
        path="/",
    )
    return {"user": user_json(user), "csrf_token": csrf}


def user_json(user):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


def throttle_login(db, request, email):
    cutoff = utcnow() - timedelta(minutes=15)
    ip = request.client.host if request.client else "unknown"
    keys = [digest("email:" + email + ":" + ip), digest("ip:" + ip)]
    for key in keys:
        count = db.scalar(
            select(func.count())
            .select_from(LoginAttempt)
            .where(
                LoginAttempt.key == key,
                LoginAttempt.success.is_(False),
                LoginAttempt.created_at > cutoff,
            )
        )
        if count >= 8:
            raise HTTPException(
                429, "Too many failed sign-in attempts; try again in 15 minutes"
            )
    db.execute(
        delete(LoginAttempt).where(
            LoginAttempt.created_at < utcnow() - timedelta(days=1)
        )
    )
    return keys
