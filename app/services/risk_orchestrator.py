from app.schemas.risk import RiskDecision

ACTION_RANK = {"allow": 0, "step_up_mfa": 1, "block": 2}


class RiskOrchestrator:
    def merge(self, ml: RiskDecision, rules: RiskDecision) -> RiskDecision:
        if ACTION_RANK[ml.recommended_action] >= ACTION_RANK[rules.recommended_action]:
            winner = ml
            loser = rules
        else:
            winner = rules
            loser = ml

        reasons = list(dict.fromkeys(winner.reasons + loser.reasons))
        return RiskDecision(
            risk_score=max(ml.risk_score, rules.risk_score),
            risk_level=winner.risk_level,
            recommended_action=winner.recommended_action,
            reasons=reasons,
            scorer="merged",
            ml_score=ml.ml_score or ml.risk_score,
            rules_score=rules.rules_score or rules.risk_score,
        )
