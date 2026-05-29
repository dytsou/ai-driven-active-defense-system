import time
import uuid
from dataclasses import dataclass

import redis
from sqlalchemy.orm import Session

from app.core.security import DUMMY_HASH, verify_password
from app.db.models import BehavioralProfile, LoginAttempt, ThreatSignal, User
from app.schemas.auth import KeystrokePayload, LoginRequest, LoginResponse, RiskBreakdown
from app.schemas.risk import RiskDecision, RiskSignals
from app.services.behavior_service import BehaviorService
from app.services.blocklist_manager import BlocklistManager
from app.services.event_service import EventService
from app.services.rate_limiter import RateLimiter
from app.services.session_manager import SessionManager
from app.services.threat_analyzer import ThreatAnalyzer


@dataclass
class LoginResult:
    response: LoginResponse
    session_id: str | None = None
    status_code: int = 200


class AuthService:
    def __init__(
        self,
        db: Session,
        sessions: SessionManager,
        blocklist: BlocklistManager,
        rate_limiter: RateLimiter,
        threat_analyzer: ThreatAnalyzer,
        redis: redis.Redis,
        behavior: BehaviorService | None = None,
    ):
        self.db = db
        self.sessions = sessions
        self.blocklist = blocklist
        self.rate_limiter = rate_limiter
        self.threat_analyzer = threat_analyzer
        self.redis = redis
        self.behavior = behavior or BehaviorService()

    def login(self, payload: LoginRequest, ip_address: str, attempt_id: str) -> LoginResult:
        started = time.perf_counter()

        if self.blocklist.is_blocked(ip_address):
            self._record_attempt(payload.username, ip_address, success=False, action="blocked")
            return LoginResult(
                response=LoginResponse(status="blocked", message="IP address is blocked"),
                status_code=403,
            )

        if not self.rate_limiter.check_and_increment(ip_address):
            return LoginResult(
                response=LoginResponse(status="rate_limited", message="Too many login attempts"),
                status_code=429,
            )

        user = self.db.query(User).filter(User.username == payload.username).one_or_none()
        password_hash = user.password_hash if user else DUMMY_HASH
        credentials_valid = user is not None and verify_password(payload.password, password_hash)

        if not credentials_valid:
            self._track_failure(ip_address, payload.username)
            keystroke = self._normalize_keystroke(payload.keystroke or KeystrokePayload())
            signals = self._collect_signals(ip_address)
            risk = self.threat_analyzer.analyze(
                username=payload.username,
                ip_address=ip_address,
                attempt_id=attempt_id,
                keystroke_present=keystroke.present,
                signals=signals,
                baseline_exists=False,
                baseline_deviation=0.0,
            )
            self._maybe_record_threat(ip_address, payload.username, risk)
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            if risk.recommended_action == "block":
                self.blocklist.block_ip(ip_address)
                self._record_attempt(
                    payload.username,
                    ip_address,
                    success=False,
                    action="block",
                    risk=risk,
                )
                self._audit(
                    "login_blocked",
                    payload.username,
                    ip_address,
                    attempt_id,
                    risk,
                    keystroke.present,
                    latency_ms=latency_ms,
                )
                return LoginResult(
                    response=LoginResponse(
                        status="blocked",
                        message="Login blocked due to risk assessment",
                        risk_score=risk.risk_score,
                        risk_level=risk.risk_level,
                        action="block",
                    ),
                    status_code=403,
                )
            self._record_attempt(payload.username, ip_address, success=False, action="invalid", risk=risk)
            return LoginResult(
                response=LoginResponse(status="invalid_credentials", message="Invalid username or password"),
                status_code=401,
            )

        keystroke = self._normalize_keystroke(payload.keystroke or KeystrokePayload())
        baseline_exists, baseline_deviation = self._baseline_context(user, keystroke)
        signals = self._collect_signals(ip_address)
        risk = self.threat_analyzer.analyze(
            username=payload.username,
            ip_address=ip_address,
            attempt_id=attempt_id,
            keystroke_present=keystroke.present,
            signals=signals,
            baseline_exists=baseline_exists,
            baseline_deviation=baseline_deviation,
        )
        self._maybe_record_threat(ip_address, payload.username, risk)

        breakdown = RiskBreakdown(
            ml_score=risk.ml_score,
            rules_score=risk.rules_score,
            behavior_deviation=baseline_deviation if baseline_exists else None,
            ml_source=risk.scorer,
        )

        latency_ms = round((time.perf_counter() - started) * 1000, 2)

        if risk.recommended_action == "block":
            self.blocklist.block_ip(ip_address)
            self._record_attempt(
                payload.username,
                ip_address,
                success=False,
                action="block",
                risk=risk,
            )
            self._audit(
                "login_blocked",
                payload.username,
                ip_address,
                attempt_id,
                risk,
                keystroke.present,
                latency_ms=latency_ms,
            )
            return LoginResult(
                response=LoginResponse(
                    status="blocked",
                    message="Login blocked due to risk assessment",
                    risk_score=risk.risk_score,
                    risk_level=risk.risk_level,
                    action="block",
                    breakdown=breakdown,
                ),
                status_code=403,
            )

        if risk.recommended_action == "step_up_mfa":
            self._record_attempt(
                payload.username,
                ip_address,
                success=False,
                action="step_up_mfa",
                risk=risk,
            )
            from app.services.mfa_service import MfaService

            MfaService(self.redis).store_challenge(attempt_id, user, ip_address)
            self._audit(
                "mfa_required",
                payload.username,
                ip_address,
                attempt_id,
                risk,
                keystroke.present,
                latency_ms=latency_ms,
            )
            return LoginResult(
                response=LoginResponse(
                    status="mfa_required",
                    message="Multi-factor authentication required",
                    risk_score=risk.risk_score,
                    risk_level=risk.risk_level,
                    action="step_up_mfa",
                    mfa_required=True,
                    mfa_method=user.mfa_method,
                    challenge_id=attempt_id,
                    breakdown=breakdown,
                ),
                status_code=200,
            )

        self._record_attempt(payload.username, ip_address, success=True, action="allow", risk=risk)
        self._audit(
            "login_success",
            payload.username,
            ip_address,
            attempt_id,
            risk,
            keystroke.present,
            baseline_created=not baseline_exists and keystroke.present,
            latency_ms=latency_ms,
        )
        if self.behavior.should_create_baseline(risk.recommended_action) and keystroke.present:
            if not baseline_exists:
                self.behavior.update_baseline(self.db, user, keystroke)
        session_id = self.sessions.create_session(str(user.id), user.username)
        return LoginResult(
            response=LoginResponse(
                status="success",
                message="Login successful",
                risk_score=risk.risk_score,
                risk_level=risk.risk_level,
                action="allow",
                breakdown=breakdown,
            ),
            session_id=session_id,
            status_code=200,
        )

    def get_current_user(self, session_id: str | None) -> User | None:
        if not session_id:
            return None
        data = self.sessions.get_session(session_id)
        if not data:
            return None
        user_id = uuid.UUID(data["user_id"])
        return self.db.query(User).filter(User.id == user_id).one_or_none()

    def _baseline_context(self, user: User, keystroke: KeystrokePayload) -> tuple[bool, float]:
        profile = (
            self.db.query(BehavioralProfile).filter(BehavioralProfile.user_id == user.id).one_or_none()
        )
        if not profile or not profile.keystroke_baseline:
            return False, 0.0
        deviation = self.behavior.compute_deviation(keystroke, profile.keystroke_baseline)
        return True, deviation

    def _normalize_keystroke(self, keystroke: KeystrokePayload) -> KeystrokePayload:
        timing = keystroke.timing
        dwell = timing.dwell_times if timing and timing.dwell_times else []
        if not keystroke.present or len(dwell) < 3:
            return KeystrokePayload(present=False, timing=timing)
        return keystroke

    def _collect_signals(self, ip_address: str) -> RiskSignals:
        failures = int(self.redis.get(f"failures:ip:{ip_address}") or 0)
        login_rate = float(self.rate_limiter.current_count(ip_address))
        distinct = int(self.redis.scard(f"usernames:ip:{ip_address}") or 0)
        return RiskSignals(
            failures_last_5m=failures,
            distinct_usernames=distinct,
            login_rate_per_min=login_rate,
        )

    def _track_failure(self, ip_address: str, username: str) -> None:
        fail_key = f"failures:ip:{ip_address}"
        count = self.redis.incr(fail_key)
        if count == 1:
            self.redis.expire(fail_key, 300)
        self.redis.sadd(f"usernames:ip:{ip_address}", username)
        self.redis.expire(f"usernames:ip:{ip_address}", 300)

    def _maybe_record_threat(self, ip_address: str, username: str, risk: RiskDecision) -> None:
        if risk.recommended_action == "allow":
            return
        self.db.add(
            ThreatSignal(
                signal_type=risk.reasons[0] if risk.reasons else "elevated_risk",
                source_ip=ip_address,
                username=username,
                severity=risk.risk_level,
                details={"reasons": risk.reasons, "scorer": risk.scorer, "risk_score": risk.risk_score},
            )
        )
        self.db.commit()

    def _audit(
        self,
        event_type: str,
        username: str,
        ip_address: str,
        attempt_id: str,
        risk: RiskDecision,
        keystroke_present: bool,
        *,
        baseline_created: bool = False,
        latency_ms: float | None = None,
    ) -> None:
        payload = {
            "attempt_id": attempt_id,
            "scorer": risk.scorer,
            "risk_score": risk.risk_score,
            "recommended_action": risk.recommended_action,
            "risk_reasons": risk.reasons,
            "keystroke_present": keystroke_present,
            "baseline_created": baseline_created,
            "api_result": risk.scorer,
        }
        if latency_ms is not None:
            payload["latency_ms"] = latency_ms
        EventService(self.db).record(
            event_type=event_type,
            actor_username=username,
            ip_address=ip_address,
            payload=payload,
        )

    def _record_attempt(
        self,
        username: str,
        ip_address: str,
        *,
        success: bool,
        action: str,
        risk: RiskDecision | None = None,
    ) -> None:
        self.db.add(
            LoginAttempt(
                username=username,
                ip_address=ip_address,
                success=success,
                action_taken=action,
                risk_score=risk.risk_score if risk else None,
                risk_level=risk.risk_level if risk else None,
                ml_source=risk.scorer if risk else None,
            )
        )
        self.db.commit()
