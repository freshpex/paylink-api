from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import current_user, membership
from app.models.entities import PaymentLink
from app.schemas.contracts import (
    LinkInput,
    ActiveInput,
)

from app.api.helpers import link_view, audit

router = APIRouter()


@router.get("/companies/{cid}/links")
def links(cid: str, user=Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user.id, cid)
    return [
        link_view(x, True)
        for x in db.query(PaymentLink)
        .filter_by(company_id=cid)
        .order_by(PaymentLink.created_at.desc())
        .limit(200)
    ]


@router.post("/companies/{cid}/links", status_code=201)
def add_link(cid: str, data: LinkInput, user=Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user.id, cid, owner=True)
    link = PaymentLink(company_id=cid, **data.model_dump(mode="json"))
    db.add(link)
    db.flush()
    audit(db, user, cid, "link.created", link.id)
    db.commit()
    return link_view(link, True)


@router.patch("/companies/{cid}/links/{lid}")
def toggle_link(
    cid: str, lid: str, data: ActiveInput, user=Depends(current_user), db: Session = Depends(get_db)
):
    membership(db, user.id, cid, owner=True)
    link = db.query(PaymentLink).filter_by(id=lid, company_id=cid).first()
    if not link:
        raise HTTPException(404, "Link not found")
    link.active = data.active
    audit(db, user, cid, "link.status_changed", lid)
    db.commit()
    return link_view(link, True)
