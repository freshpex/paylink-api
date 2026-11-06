"""Durable receipt outbox. Run a single worker, or use PostgreSQL SKIP LOCKED."""

import logging
import time
import httpx
from sqlalchemy import select
from app.core.config import settings
from app.core.db import SessionLocal
from app.models.entities import Outbox, Payment

log = logging.getLogger(__name__)


def deliver_batch():
    config = settings()
    if not config.mailjet_api_key:
        return
    with SessionLocal() as db:
        rows = db.scalars(
            select(Outbox)
            .where(Outbox.sent.is_(False), Outbox.attempts < 12)
            .with_for_update(skip_locked=True)
            .limit(20)
        ).all()
        for item in rows:
            payment = db.get(Payment, item.payment_id)
            snapshot = payment.receipt_snapshot
            item.attempts += 1
            try:
                response = httpx.post(
                    "https://api.mailjet.com/v3.1/send",
                    auth=(config.mailjet_api_key, config.mailjet_secret_key),
                    timeout=20,
                    json={
                        "Messages": [
                            {
                                "From": {"Email": config.mail_from, "Name": snapshot["company"]},
                                "To": [{"Email": payment.email, "Name": payment.name}],
                                "Subject": f"Payment receipt — {snapshot['title']}",
                                "TextPart": f"Thank you. Your payment of {payment.currency} {payment.amount / 100:.2f} to {snapshot['company']} is confirmed. Reference: {payment.id}. Download your receipt: {config.frontend_url}/receipt/{payment.id}",
                                "CustomID": payment.id,
                            }
                        ]
                    },
                )
                response.raise_for_status()
                item.sent = response.json()["Messages"][0]["Status"] == "success"
            except (httpx.HTTPError, KeyError, ValueError, IndexError):
                log.warning("Receipt delivery deferred for outbox %s", item.id)
        db.commit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    while True:
        deliver_batch()
        time.sleep(30)
