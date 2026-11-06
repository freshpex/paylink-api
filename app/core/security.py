from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.db import get_db
from app.models.entities import User, Membership

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash("constant-time-nonexistent-user")


def token(user_id):
    return jwt.encode(
        {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
        settings().jwt_secret,
        algorithm="HS256",
    )


def current_user(request: Request, db: Session = Depends(get_db)):
    try:
        claims = jwt.decode(request.cookies.get("session", ""), settings().jwt_secret, algorithms=["HS256"])
        user = db.get(User, claims["sub"])
        if not user:
            raise ValueError()
        return user
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "Please sign in")


def membership(db, user_id, company_id, owner=False):
    member = db.query(Membership).filter_by(user_id=user_id, company_id=company_id).first()
    if not member or (owner and member.role != "owner"):
        raise HTTPException(403, "Company access denied")
    return member
