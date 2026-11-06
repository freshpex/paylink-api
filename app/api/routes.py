from fastapi import APIRouter
from app.api import auth, companies, links, payments, public

router = APIRouter(prefix="/api/v1")
for module in (auth, companies, links, payments, public):
    router.include_router(module.router)
