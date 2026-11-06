from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import current_user, passwords, DUMMY_HASH
from app.models.entities import User, Company, Membership
from app.schemas.contracts import (
    Register,
    Login,
)

from app.core.limiter import limiter
from app.api.helpers import user_view, set_session

router = APIRouter()


@router.post("/auth/register", status_code=201)
@limiter.limit("5/minute")
def register(request: Request, data: Register, response: Response, db: Session = Depends(get_db)):
    user = User(name=data.name, email=data.email.lower(), password_hash=passwords.hash(data.password))
    db.add(user)
    try:
        db.flush()
        company = Company(name=data.company_name)
        db.add(company)
        db.flush()
        db.add(Membership(user_id=user.id, company_id=company.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Unable to register with that email")
    set_session(response, user)
    return user_view(user)


@router.post("/auth/login")
@limiter.limit("10/minute")
def login(request: Request, data: Login, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=data.email.lower()).first()
    valid = passwords.verify(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, "Invalid email or password")
    set_session(response, user)
    return user_view(user)


@router.post("/auth/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie("session", path="/")


@router.get("/auth/me")
def me(user=Depends(current_user)):
    return user_view(user)
