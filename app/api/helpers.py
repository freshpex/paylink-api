from app.core.config import settings
from app.core.security import token
from app.models.entities import Audit


def user_view(user):
    return {"id": user.id, "name": user.name, "email": user.email}


def company_view(company):
    return {"id": company.id, "name": company.name, "logo_url": company.logo_url, "accent": company.accent}


def link_view(link, private=False):
    fields = [
        "id",
        "title",
        "description",
        "category",
        "amount",
        "currency",
        "methods",
        "receipt_heading",
        "receipt_footer",
        "theme",
        "hero_url",
        "note",
        "active",
        "created_at",
    ]
    if private:
        fields += ["recipient_name", "recipient_email"]
    return {k: getattr(link, k) for k in fields}


def audit(db, user, company, action, target):
    db.add(Audit(company_id=company, user_id=user.id, action=action, target_id=target))


def set_session(response, user):
    response.set_cookie(
        "session",
        token(user.id),
        httponly=True,
        secure=settings().cookie_secure,
        samesite="lax",
        max_age=28800,
        path="/",
    )
