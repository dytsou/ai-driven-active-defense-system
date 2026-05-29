from dataclasses import dataclass

from app.core.config import settings
from app.schemas.risk import RiskDecision, RiskSignals


ACTION_RANK = {"allow": 0, "step_up_mfa": 1, "block": 2}


@dataclass
class RulesContext:
    keystroke_present: bool
    signals: RiskSignals
    baseline_deviation: float = 0.0


class RulesEngine:
    def evaluate(self, context: RulesContext) -> RiskDecision:
        score = 0.1
        reasons: list[str] = []

        if not context.keystroke_present:
            score = max(score, 0.85)
            reasons.append("missing_keystroke")

        if context.signals.failures_last_5m >= 5:
            score = max(score, 0.75)
            reasons.append("high_failure_rate")

        if context.signals.distinct_usernames >= 3:
            score = max(score, 0.85)
            reasons.append("credential_stuffing_pattern")

        if (
            context.signals.failures_last_5m >= 8
            and context.signals.distinct_usernames >= 3
        ):
            score = max(score, 0.95)
            reasons.append("brute_force_spray")

        if context.signals.login_rate_per_min >= 20:
            score = max(score, 0.8)
            reasons.append("high_login_rate")

        if context.baseline_deviation >= settings.baseline_deviation_threshold:
            score = max(score, 0.75)
            reasons.append("baseline_deviation")

        action = self._action_for_score(score)
        level = self._level_for_score(score)
        return RiskDecision(
            risk_score=round(score, 3),
            risk_level=level,
            recommended_action=action,
            reasons=reasons or ["rules_baseline"],
            scorer="rules",
            rules_score=round(score, 3),
        )

    @staticmethod
    def _action_for_score(score: float) -> str:
        if score >= settings.block_threshold:
            return "block"
        if score >= settings.high_threshold:
            return "step_up_mfa"
        return "allow"

    @staticmethod
    def _level_for_score(score: float) -> str:
        if score >= settings.block_threshold:
            return "critical"
        if score >= settings.high_threshold:
            return "high"
        if score >= settings.medium_threshold:
            return "medium"
        return "low"
