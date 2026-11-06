import time
import cloudinary.utils
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.db import get_db
from app.core.security import current_user, membership
from app.models.entities import Company, Membership, Audit
from app.schemas.contracts import (
    CompanyInput,
)

from app.core.limiter import limiter
from app.api.helpers import company_view, audit

router = APIRouter()


@router.get("/companies")
def companies(user=Depends(current_user), db: Session = Depends(get_db)):
    return [
        company_view(c)
        for c in db.query(Company).join(Membership).filter(Membership.user_id == user.id).all()
    ]


@router.post("/companies", status_code=201)
def add_company(data: CompanyInput, user=Depends(current_user), db: Session = Depends(get_db)):
    company = Company(**data.model_dump())
    db.add(company)
    db.flush()
    db.add(Membership(user_id=user.id, company_id=company.id))
    audit(db, user, company.id, "company.created", company.id)
    db.commit()
    return company_view(company)


@router.put("/companies/{cid}")
def edit_company(cid: str, data: CompanyInput, user=Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user.id, cid, owner=True)
    company = db.get(Company, cid)
    for key, value in data.model_dump().items():
        setattr(company, key, value)
    audit(db, user, cid, "company.updated", cid)
    db.commit()
    return company_view(company)


@router.post("/companies/{cid}/media-signature")
@limiter.limit("30/minute")
def media_signature(cid: str, request: Request, user=Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user.id, cid, owner=True)
    config = settings()
    if not config.cloudinary_api_secret:
        raise HTTPException(503, "Cloudinary is not configured")
    params = {
        "timestamp": int(time.time()),
        "folder": f"paylink/{cid}",
        "allowed_formats": "jpg,png,webp,mp4,webm",
        "overwrite": "false",
    }
    return {
        "params": params,
        "signature": cloudinary.utils.api_sign_request(params, config.cloudinary_api_secret),
        "api_key": config.cloudinary_api_key,
        "cloud_name": config.cloudinary_cloud_name,
    }


@router.get("/companies/{cid}/audit")
def audit_list(cid: str, user=Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user.id, cid, owner=True)
    return [
        {k: getattr(a, k) for k in ["id", "action", "target_id", "created_at"]}
        for a in db.query(Audit).filter_by(company_id=cid).order_by(Audit.created_at.desc()).limit(100)
    ]
