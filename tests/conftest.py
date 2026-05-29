import pytest
import fakeredis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Session:
    session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def fake_redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture()
def mock_ml_client():
    from app.schemas.risk import RiskDecision
    from app.services.ml_client import MLClient

    class InlineMockML(MLClient):
        def score(self, *, keystroke_present: bool, baseline_deviation: float = 0.0, **kwargs):
            if not keystroke_present:
                return RiskDecision(
                    risk_score=0.85,
                    risk_level="high",
                    recommended_action="step_up_mfa",
                    reasons=["missing_keystroke"],
                    scorer="ml_aggregate",
                    ml_score=0.85,
                )
            if baseline_deviation >= 0.35:
                return RiskDecision(
                    risk_score=0.75,
                    risk_level="high",
                    recommended_action="step_up_mfa",
                    reasons=["baseline_deviation"],
                    scorer="ml_aggregate",
                    ml_score=0.75,
                )
            return RiskDecision(
                risk_score=0.2,
                risk_level="low",
                recommended_action="allow",
                reasons=["normal_keystroke"],
                scorer="ml_aggregate",
                ml_score=0.2,
            )

    return InlineMockML()


@pytest.fixture()
def client(db_session: Session, fake_redis):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.state.redis = fake_redis
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    app.state.redis = None


@pytest.fixture()
def auth_client(client: TestClient, mock_ml_client):
    from app.services.threat_analyzer import ThreatAnalyzer

    app.state.threat_analyzer = ThreatAnalyzer(ml_client=mock_ml_client)
    yield client
    app.state.threat_analyzer = None


@pytest.fixture()
def seeded_db(db_session: Session):
    from scripts.seed_db import seed_database

    seed_database(db_session, settings)
    return db_session
