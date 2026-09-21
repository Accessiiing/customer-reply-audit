from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRelation(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNSUPPORTED = "unsupported"
    UNCERTAIN = "uncertain"


class IssueType(StrEnum):
    FACTUAL_CONTRADICTION = "factual_contradiction"
    UNSUPPORTED_ASSERTION = "unsupported_assertion"
    FABRICATED_CAPABILITY = "fabricated_capability"
    MATERIAL_OMISSION = "material_omission"
    SAFETY_DENIAL = "safety_denial"


class Severity(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReplyRecord(StrictModel):
    id: str = Field(min_length=1)
    user_question: str = Field(min_length=1)
    system_reply: str = Field(min_length=1)
    knowledge_base: str = Field(min_length=1)


class TruthRecord(StrictModel):
    id: str = Field(min_length=1)
    is_hallucination: bool
    hallucination_type: str | None = None
    detail: str


class Claim(StrictModel):
    reply_quote: str = ""
    subject: str
    predicate: str
    value: str
    conditions: str = ""
    relation: EvidenceRelation
    evidence_quote: str = ""
    issue_types: list[IssueType] = Field(default_factory=list)
    business_tags: list[str] = Field(default_factory=list)
    severity: Severity = Severity.NONE
    reason: str
    material: bool = True

    @model_validator(mode="after")
    def relation_consistency(self) -> "Claim":
        if self.relation == EvidenceRelation.SUPPORTED and self.issue_types:
            raise ValueError("supported claim cannot carry issue_types")
        if self.relation in {EvidenceRelation.CONTRADICTED, EvidenceRelation.UNSUPPORTED} and not self.issue_types:
            raise ValueError("problematic claim must carry issue_types")
        if self.relation == EvidenceRelation.UNSUPPORTED and self.evidence_quote:
            raise ValueError("unsupported claim must not fabricate an evidence quote")
        return self


class JudgeOutput(StrictModel):
    claims: list[Claim] = Field(min_length=1)
    unresolved: list[str] = Field(default_factory=list)


class DetectionItem(StrictModel):
    id: str
    mode: Literal["real", "mock"]
    status: Literal["ok", "needs_review", "error"]
    is_hallucination: bool | None
    issue_types: list[IssueType] = Field(default_factory=list)
    severity: Severity
    problem_quotes: list[str] = Field(default_factory=list)
    evidence_quotes: list[str] = Field(default_factory=list)
    reason: str
    claims: list[Claim] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)
    attempts: int = 1
    error: str | None = None

    @model_validator(mode="after")
    def status_consistency(self) -> "DetectionItem":
        if self.status == "ok" and self.is_hallucination is None:
            raise ValueError("ok item requires a boolean decision")
        if self.status != "ok" and self.is_hallucination is not None:
            raise ValueError("non-ok item must use null decision")
        return self


class RunMetadata(StrictModel):
    run_id: str
    mode: Literal["real", "mock"]
    input_path: str
    input_sha256: str
    taxonomy_version: str
    taxonomy_sha256: str
    prompt_version: str
    prompt_sha256: str
    model: str
    temperature: float
    started_at: str
    finished_at: str
    duration_seconds: float
    retries: int
    usage: dict[str, int | float | str]
    code_version: str


class DetectionRun(StrictModel):
    metadata: RunMetadata
    items: list[DetectionItem]

