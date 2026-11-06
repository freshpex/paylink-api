from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.entities import Company, PaymentLink, Payment
from app.schemas.contracts import (
    CheckoutInput,
)

from app.core.limiter import limiter
from app.api.helpers import link_view

router = APIRouter()


@router.get("/public/links/{lid}")
@limiter.limit("120/minute")
def public_link(lid: str, request: Request, db: Session = Depends(get_db)):
    link = db.get(PaymentLink, lid)
    if not link or not link.active:
        raise HTTPException(404, "This payment link is unavailable")
    company = db.get(Company, link.company_id)
    return {**link_view(link), "company": {k: getattr(company, k) for k in ["name", "logo_url", "accent"]}}


@router.post("/public/links/{lid}/claims", status_code=201)
@limiter.limit("10/minute")
def claim(lid: str, data: CheckoutInput, request: Request, db: Session = Depends(get_db)):
    link = db.get(PaymentLink, lid)
    if not link or not link.active:
        raise HTTPException(404, "This payment link is unavailable")
    if data.method_index >= len(link.methods):
        raise HTTPException(422, "Payment method is not enabled")
    existing = db.query(Payment).filter_by(link_id=lid, request_key=str(data.request_key)).first()
    if existing:
        if (
            existing.email != data.email
            or existing.name != data.name
            or existing.provider != link.methods[data.method_index]["label"]
            or existing.transfer_reference != data.transfer_reference
        ):
            raise HTTPException(409, "Request key already used")
        return {"payment_id": existing.id, "status": existing.status}
    payment = Payment(
        link_id=lid,
        company_id=link.company_id,
        request_key=str(data.request_key),
        provider=link.methods[data.method_index]["label"],
        email=data.email,
        name=data.name,
        transfer_reference=data.transfer_reference,
        amount=link.amount,
        currency=link.currency,
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Claim already submitted; retry")
    return {"payment_id": payment.id, "status": payment.status}


@router.get("/public/payments/{pid}/status")
@limiter.limit("60/minute")
def payment_status(pid: str, request: Request, db: Session = Depends(get_db)):
    payment = db.get(Payment, pid)
    if not payment:
        raise HTTPException(404, "Payment not found")
    return {"status": payment.status}


@router.get("/public/receipts/{pid}")
@limiter.limit("60/minute")
def receipt(pid: str, request: Request, db: Session = Depends(get_db)):
    payment = db.get(Payment, pid)
    if not payment or payment.status != "paid":
        raise HTTPException(404, "A confirmed receipt is not available")
    return {"id": payment.id, **payment.receipt_snapshot}
