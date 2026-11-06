import os

os.environ["JWT_SECRET"] = "test-secret-must-be-at-least-32-characters"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["COOKIE_SECURE"] = "false"
from app.core.db import Base, get_db
from app.main import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
import pytest


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    def override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    app.state.limiter.enabled = False
    with TestClient(app, headers={"Origin": "http://localhost:5173"}) as c:
        c.db_factory = factory
        yield c
    app.dependency_overrides.clear()
    engine.dispose()
