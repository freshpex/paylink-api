from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import current_user, membership
from app.models.entities import Company, PaymentLink, Payment, Outbox, now
from app.schemas.contracts import (
    ReviewInput,
)

from app.api.helpers import audit

router = APIRouter()


@router.get("/companies/{cid}/payments")
def payments(cid: str, user=Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user.id, cid)
    return [
        {
            k: getattr(p, k)
            for k in [
                "id",
                "link_id",
                "name",
                "email",
                "amount",
                "currency",
                "provider",
                "transfer_reference",
                "status",
                "created_at",
            ]
        }
        for p in db.query(Payment).filter_by(company_id=cid).order_by(Payment.created_at.desc()).limit(200)
    ]


@router.post("/companies/{cid}/payments/{pid}/review")
def review(cid: str, pid: str, data: ReviewInput, user=Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user.id, cid, owner=True)
    payment = db.query(Payment).filter_by(id=pid, company_id=cid).with_for_update().first()
    if not payment:
        raise HTTPException(404, "Payment not found")
    if payment.status != "pending":
        raise HTTPException(409, "This payment has already been reviewed")
    payment.status = data.decision
    if data.decision == "paid":
        company, link = db.get(Company, cid), db.get(PaymentLink, payment.link_id)
        payment.confirmed_at = now()
        payment.receipt_snapshot = {
            "company": company.name,
            "logo_url": company.logo_url,
            "accent": company.accent,
            "title": link.title,
            "heading": link.receipt_heading,
            "footer": link.receipt_footer,
            "theme": link.theme,
            "payer": payment.name,
            "email": payment.email,
            "amount": payment.amount,
            "currency": payment.currency,
            "method": payment.provider,
            "reference": payment.transfer_reference,
            "confirmed_at": payment.confirmed_at.isoformat(),
        }
        db.add(Outbox(payment_id=payment.id))
    audit(db, user, cid, f"payment.{data.decision}", pid)
    db.commit()
    return {"status": payment.status}
