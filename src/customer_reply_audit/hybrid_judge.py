from __future__ import annotations

from .jev_provider import JevJudge
from .mock_judge import judge as rule_judge
from .models import EvidenceRelation, IssueType, JudgeOutput, ReplyRecord


HARD_RULE_TYPES = {
    IssueType.FACTUAL_CONTRADICTION,
    IssueType.FABRICATED_CAPABILITY,
    IssueType.SAFETY_DENIAL,
}


class HybridJudge:
    def __init__(self, jev: JevJudge):
        self.jev = jev

    @property
    def model(self) -> str:
        return f"hard-rules+{self.jev.resolved_model}"

    def judge(self, record: ReplyRecord) -> tuple[JudgeOutput, dict[str, int | float | str]]:
        rules = rule_judge(record)
        semantic, usage = self.jev.judge(record)
        hard_claims = [
            claim for claim in rules.claims
            if claim.relation == EvidenceRelation.CONTRADICTED
            and any(issue in HARD_RULE_TYPES for issue in claim.issue_types)
        ]
        merged = []
        seen = set()
        for claim in hard_claims + semantic.claims:
            key = (
                claim.reply_quote,
                claim.evidence_quote,
                claim.relation,
                tuple(claim.issue_types),
            )
            if key not in seen:
                seen.add(key)
                merged.append(claim)
        return JudgeOutput(
            claims=merged,
            unresolved=rules.unresolved + semantic.unresolved,
        ), usage
