import statistics

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import BehavioralProfile, User
from app.schemas.auth import KeystrokePayload


class BehaviorService:
    def extract_features(self, keystroke: KeystrokePayload) -> dict:
        timing = keystroke.timing
        dwell = timing.dwell_times if timing and timing.dwell_times else []
        flight = timing.flight_times if timing and timing.flight_times else []
        dwell_mean = statistics.mean(dwell) if dwell else 0.0
        flight_mean = statistics.mean(flight) if flight else 0.0
        dwell_std = statistics.pstdev(dwell) if len(dwell) > 1 else 0.0
        flight_std = statistics.pstdev(flight) if len(flight) > 1 else 0.0
        hesitation_count = sum(1 for value in dwell if value > dwell_mean * 1.5) if dwell else 0
        return {
            "dwell_mean": round(dwell_mean, 2),
            "dwell_std": round(dwell_std, 2),
            "flight_mean": round(flight_mean, 2),
            "flight_std": round(flight_std, 2),
            "hesitation_count": hesitation_count,
        }

    def compute_deviation(self, keystroke: KeystrokePayload, baseline: dict | None) -> float:
        if not keystroke.present or not baseline:
            return 0.0
        features = self.extract_features(keystroke)
        dwell_delta = abs(features["dwell_mean"] - baseline.get("dwell_mean", 0))
        flight_delta = abs(features["flight_mean"] - baseline.get("flight_mean", 0))
        dwell_norm = dwell_delta / max(baseline.get("dwell_std", 1.0), 1.0)
        flight_norm = flight_delta / max(baseline.get("flight_std", 1.0), 1.0)
        return round(min(1.0, (dwell_norm + flight_norm) / 2), 3)

    def update_baseline(self, db: Session, user: User, keystroke: KeystrokePayload) -> BehavioralProfile:
        features = self.extract_features(keystroke)
        profile = db.query(BehavioralProfile).filter(BehavioralProfile.user_id == user.id).one_or_none()
        if profile is None:
            profile = BehavioralProfile(user_id=user.id, keystroke_baseline=features, sample_count=1)
            db.add(profile)
        else:
            profile.keystroke_baseline = features
            profile.sample_count += 1
        db.commit()
        db.refresh(profile)
        return profile

    def should_create_baseline(self, risk_action: str) -> bool:
        return risk_action == "allow"

    def exceeds_threshold(self, deviation: float) -> bool:
        return deviation >= settings.baseline_deviation_threshold
