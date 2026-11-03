import os

os.environ["DEBUG"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-which-is-long-enough"
os.environ["AUTO_SEED"] = "false"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_PASSWORD"] = ""
os.environ["PASSWORD_HASH_ROUNDS"] = "4"
os.environ["APP_ENV"] = "test"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.domain.enums import Role
from app.main import app
from app.models.identity import User

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


@event.listens_for(engine, "connect")
def _fk(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = TestingSession()
    yield db
    db.close()


@pytest.fixture
def client(session):
    def override():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_user(session, email, role, password="Password1"):
    user = User(
        email=email,
        full_name=email.split("@")[0],
        hashed_password=hash_password(password),
        role=role.value if isinstance(role, Role) else role,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def admin(session):
    return make_user(session, "admin@ngo.local", Role.SUPER_ADMIN, "Admin@12345")


@pytest.fixture
def admin_headers(client, admin):
    response = client.post("/api/v1/auth/login", json={"email": "admin@ngo.local", "password": "Admin@12345"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def auth_header(client, email, password="Password1"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
