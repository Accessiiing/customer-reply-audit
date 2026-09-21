from __future__ import annotations

from collections.abc import Callable

from .io import quote_exists
from .models import (
    Claim,
    DetectionItem,
    EvidenceRelation,
    IssueType,
    JudgeOutput,
    ReplyRecord,
    Severity,
)

SEVERITY_ORDER = {value: index for index, value in enumerate(Severity)}


def validate_claim_quotes(record: ReplyRecord, output: JudgeOutput) -> list[str]:
    errors: list[str] = []
    for index, claim in enumerate(output.claims):
        if claim.reply_quote and not quote_exists(claim.reply_quote, record.system_reply):
            errors.append(f"claim[{index}].reply_quote is not in this reply")
        if claim.evidence_quote and not quote_exists(claim.evidence_quote, record.knowledge_base):
            errors.append(f"claim[{index}].evidence_quote is not in this knowledge base")
        if claim.relation == EvidenceRelation.CONTRADICTED and not claim.evidence_quote:
            errors.append(f"claim[{index}] contradicted requires evidence_quote")
        if claim.relation == EvidenceRelation.UNSUPPORTED and not claim.reason.strip():
            errors.append(f"claim[{index}] unsupported requires missing-evidence reason")
    return errors


def aggregate(record: ReplyRecord, output: JudgeOutput, *, mode: str, attempts: int = 1) -> DetectionItem:
    validation_errors = validate_claim_quotes(record, output)
    if validation_errors:
        return DetectionItem(
            id=record.id, mode=mode, status="needs_review", is_hallucination=None,
            severity=Severity.NONE, reason="引用校验失败，不能把格式故障判成正常。",
            claims=output.claims, unresolved=output.unresolved + validation_errors,
            review_reasons=["invalid_quote"], attempts=attempts,
        )

    confirmed = [
        claim for claim in output.claims
        if claim.material and claim.relation in {EvidenceRelation.CONTRADICTED, EvidenceRelation.UNSUPPORTED}
    ]
    uncertain = [claim for claim in output.claims if claim.relation == EvidenceRelation.UNCERTAIN]
    if confirmed:
        severity = max((claim.severity for claim in confirmed), key=lambda item: SEVERITY_ORDER[item])
        issue_types = list(dict.fromkeys(issue for claim in confirmed for issue in claim.issue_types))
        return DetectionItem(
            id=record.id, mode=mode, status="ok", is_hallucination=True,
            issue_types=issue_types, severity=severity,
            problem_quotes=list(dict.fromkeys(claim.reply_quote for claim in confirmed if claim.reply_quote)),
            evidence_quotes=list(dict.fromkeys(claim.evidence_quote for claim in confirmed if claim.evidence_quote)),
            reason="；".join(dict.fromkeys(claim.reason for claim in confirmed)),
            claims=output.claims, unresolved=output.unresolved + [claim.reason for claim in uncertain],
            review_reasons=["confirmed_issue_with_uncertainty"] if uncertain else [], attempts=attempts,
        )
    if uncertain or output.unresolved:
        return DetectionItem(
            id=record.id, mode=mode, status="needs_review", is_hallucination=None,
            severity=Severity.NONE, reason="现有证据不足以形成可靠二元结论。",
            claims=output.claims, unresolved=output.unresolved + [claim.reason for claim in uncertain],
            review_reasons=["semantic_uncertainty"], attempts=attempts,
        )
    return DetectionItem(
        id=record.id, mode=mode, status="ok", is_hallucination=False,
        severity=Severity.NONE, reason="未发现经当前证据确认的实质问题。",
        claims=output.claims, attempts=attempts,
    )


def detect_one(
    record: ReplyRecord,
    judge: Callable[[ReplyRecord], JudgeOutput],
    *,
    mode: str,
) -> DetectionItem:
    try:
        return aggregate(record, judge(record), mode=mode)
    except Exception as exc:  # provider/system faults are isolated per record
        return DetectionItem(
            id=record.id, mode=mode, status="error", is_hallucination=None,
            severity=Severity.NONE, reason="检测调用发生系统故障。", error=f"{type(exc).__name__}: {exc}",
        )

