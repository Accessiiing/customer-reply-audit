from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from .candidates import TextCandidate, build_candidates, build_jev_questions, build_jev_state
from .models import Claim, EvidenceRelation, IssueType, JudgeOutput, ReplyRecord, Severity
from .provider import ProviderError


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "jev-v1.json"

DEFAULT_SEVERITY = {
    IssueType.FACTUAL_CONTRADICTION: Severity.MEDIUM,
    IssueType.UNSUPPORTED_ASSERTION: Severity.MEDIUM,
    IssueType.FABRICATED_CAPABILITY: Severity.HIGH,
    IssueType.MATERIAL_OMISSION: Severity.MEDIUM,
    IssueType.SAFETY_DENIAL: Severity.CRITICAL,
}


def _choice(answers: dict[str, Any], question_id: str) -> tuple[str, float, float]:
    answer = answers.get(question_id)
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        raise ProviderError(f"missing or invalid Choice answer: {question_id}")
    selected = answer.get("choice")
    probabilities = answer.get("probabilities")
    confidence = answer.get("confidence")
    if not isinstance(selected, str) or not isinstance(probabilities, dict) or selected not in probabilities:
        raise ProviderError(f"invalid Choice payload: {question_id}")
    probability = probabilities[selected]
    if not isinstance(probability, (int, float)) or not isinstance(confidence, (int, float)):
        raise ProviderError(f"invalid Choice probability/confidence: {question_id}")
    return selected, float(probability), float(confidence)


def _noul(answers: dict[str, Any], question_id: str) -> float:
    answer = answers.get(question_id)
    if not isinstance(answer, dict) or answer.get("type") != "noul" or not isinstance(answer.get("noul"), (int, float)):
        raise ProviderError(f"missing or invalid Noul answer: {question_id}")
    return float(answer["noul"])


def _tags(text: str) -> list[str]:
    mapping = {
        "rights": r"退货|退款|保修|发票|运费|优惠",
        "commitment": r"预计|保证|会在|已帮|已经|直接发到",
        "address": r"地址|路|街|号|邮编",
        "product_parameter": r"参数|版本|接口|材质|延迟|尺码|NFC",
        "safety": r"安全|孕妇|哺乳|医生|放心使用",
    }
    return [tag for tag, pattern in mapping.items() if re.search(pattern, text, re.I)]


def _severity(issue: IssueType, tags: list[str]) -> Severity:
    severity = DEFAULT_SEVERITY[issue]
    if severity == Severity.MEDIUM and set(tags) & {"rights", "address", "product_parameter", "safety"}:
        return Severity.HIGH
    return severity


def answers_to_judge_output(
    record: ReplyRecord,
    reply_candidates: list[TextCandidate],
    knowledge_candidates: list[TextCandidate],
    answers: dict[str, Any],
    config: dict[str, Any],
) -> JudgeOutput:
    facts = {item.id: item for item in knowledge_candidates}
    claims: list[Claim] = []
    unresolved: list[str] = []
    relation_floor = float(config["relation_min_probability"])
    confidence_floor = float(config["choice_min_confidence"])
    material_floor = float(config["material_probability_threshold"])

    for candidate in reply_candidates:
        selected, probability, confidence = _choice(answers, f"relation_{candidate.id}")
        material_probability = _noul(answers, f"material_{candidate.id}")
        issue_name, issue_probability, issue_confidence = _choice(answers, f"issue_{candidate.id}")
        material = material_probability >= material_floor
        evidence_quote = ""

        if probability < relation_floor or confidence < confidence_floor:
            relation = EvidenceRelation.UNCERTAIN
            unresolved.append(
                f"{candidate.id} evidence relation below gate: probability={probability:.3f}, confidence={confidence:.3f}"
            )
        elif selected.startswith("supported_by_"):
            fact_id = selected.removeprefix("supported_by_")
            if fact_id not in facts:
                raise ProviderError(f"unknown evidence candidate: {fact_id}")
            relation = EvidenceRelation.SUPPORTED
            evidence_quote = facts[fact_id].text
        elif selected.startswith("contradicted_by_"):
            fact_id = selected.removeprefix("contradicted_by_")
            if fact_id not in facts:
                raise ProviderError(f"unknown evidence candidate: {fact_id}")
            relation = EvidenceRelation.CONTRADICTED
            evidence_quote = facts[fact_id].text
        elif selected == "unsupported":
            relation = EvidenceRelation.UNSUPPORTED
        else:
            relation = EvidenceRelation.UNCERTAIN

        issue_types: list[IssueType] = []
        severity = Severity.NONE
        tags = _tags(candidate.text + " " + evidence_quote)
        if relation in {EvidenceRelation.CONTRADICTED, EvidenceRelation.UNSUPPORTED}:
            try:
                issue = IssueType(issue_name)
            except ValueError:
                issue = (
                    IssueType.FACTUAL_CONTRADICTION
                    if relation == EvidenceRelation.CONTRADICTED
                    else IssueType.UNSUPPORTED_ASSERTION
                )
                unresolved.append(f"{candidate.id} issue type fell back from {issue_name!r}")
            if issue_name == "none" or issue_probability < relation_floor or issue_confidence < confidence_floor:
                issue = (
                    IssueType.FACTUAL_CONTRADICTION
                    if relation == EvidenceRelation.CONTRADICTED
                    else IssueType.UNSUPPORTED_ASSERTION
                )
                unresolved.append(
                    f"{candidate.id} issue type below gate; deterministic fallback={issue.value}"
                )
            issue_types = [issue]
            severity = _severity(issue, tags)

        claims.append(Claim(
            reply_quote=candidate.text,
            subject=candidate.id,
            predicate="evidence_relation",
            value=selected,
            relation=relation,
            evidence_quote=evidence_quote,
            issue_types=issue_types,
            business_tags=tags,
            severity=severity,
            reason=(
                f"Jev selected {selected} (p={probability:.3f}, confidence={confidence:.3f}); "
                f"material_noul={material_probability:.3f}."
            ),
            material=material,
        ))

    omission_floor = float(config["omission_min_probability"])
    for fact in knowledge_candidates:
        selected, probability, confidence = _choice(answers, f"coverage_{fact.id}")
        if selected == "materially_omitted" and probability >= omission_floor and confidence >= confidence_floor:
            tags = _tags(fact.text)
            claims.append(Claim(
                reply_quote="",
                subject=fact.id,
                predicate="knowledge_coverage",
                value="materially_omitted",
                relation=EvidenceRelation.CONTRADICTED,
                evidence_quote=fact.text,
                issue_types=[IssueType.MATERIAL_OMISSION],
                business_tags=tags,
                severity=_severity(IssueType.MATERIAL_OMISSION, tags),
                reason=f"Jev marked relevant knowledge as materially omitted (p={probability:.3f}, confidence={confidence:.3f}).",
                material=True,
            ))
        elif selected == "uncertain" or probability < omission_floor or confidence < confidence_floor:
            unresolved.append(
                f"{fact.id} coverage unresolved: selected={selected}, probability={probability:.3f}, confidence={confidence:.3f}"
            )

    return JudgeOutput(claims=claims, unresolved=unresolved)


class JevJudge:
    def __init__(
        self,
        *,
        config_path: Path = DEFAULT_CONFIG,
        timeout: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.config_path = config_path
        self.config = json.loads(config_path.read_text(encoding="utf-8"))
        self.api_key = os.getenv("TYPESAFE_API_KEY") or os.getenv("JEV_API_KEY")
        self.base_url = (os.getenv("TYPESAFE_BASE_URL") or "https://api.typesafe.ai").rstrip("/")
        self.model = os.getenv("TYPESAFE_DEFAULT_MODEL") or str(self.config["default_model"])
        self.timeout = timeout or float(os.getenv("JEV_TIMEOUT_SECONDS", "30"))
        self.transport = transport
        self.resolved_models: set[str] = set()
        self.total_usage = {"input_tokens": 0, "output_tokens": 0, "requests": 0}
        self.total_duration_seconds = 0.0
        self.total_retries = 0
        if not self.api_key:
            raise ProviderError("jev mode requires TYPESAFE_API_KEY or JEV_API_KEY")

    @property
    def resolved_model(self) -> str:
        return ",".join(sorted(self.resolved_models)) or self.model

    def _request(self, payload: dict[str, Any]) -> tuple[dict[str, Any], float]:
        """Send one Jev request, retrying only documented transient failures."""
        max_retries = int(self.config["max_retries"])
        started = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                for attempt in range(max_retries + 1):
                    try:
                        response = client.post(
                            f"{self.base_url}/v1/systemone",
                            headers={"Authorization": f"Bearer {self.api_key}"},
                            json=payload,
                        )
                    except httpx.HTTPError as exc:
                        raise ProviderError(
                            f"Jev provider call failed: {type(exc).__name__}: {exc}"
                        ) from exc

                    if response.status_code in {429, 529} and attempt < max_retries:
                        self.total_retries += 1
                        retry_after = response.headers.get("retry-after")
                        wait_seconds = (
                            float(retry_after)
                            if retry_after
                            else float(self.config["retry_base_seconds"]) * (2 ** attempt)
                        )
                        time.sleep(wait_seconds)
                        continue

                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        raise ProviderError(
                            f"Jev provider call failed: HTTP {response.status_code}"
                        ) from exc
                    body = response.json()
                    if not isinstance(body, dict):
                        raise ProviderError("Jev response body is not an object")
                    return body, time.perf_counter() - started
        finally:
            self.total_duration_seconds += time.perf_counter() - started

        raise ProviderError("Jev provider retries exhausted")  # pragma: no cover

    def preflight(self) -> str:
        """Verify authentication and response shape before writing benchmark runs."""
        body, _ = self._request({
            "model": self.model,
            "state": "credential preflight",
            "questions": {
                "reachable": {
                    "type": "noul",
                    "instructions": "Is this text present?",
                }
            },
        })
        model = body.get("model")
        answers = body.get("answers")
        if not isinstance(model, str) or not isinstance(answers, dict):
            raise ProviderError("Jev preflight response is missing model or answers")
        _noul(answers, "reachable")
        return model

    def judge(self, record: ReplyRecord) -> tuple[JudgeOutput, dict[str, int | float | str]]:
        reply_candidates, knowledge_candidates = build_candidates(record)
        payload = {
            "model": self.model,
            "state": build_jev_state(record, reply_candidates, knowledge_candidates),
            "questions": build_jev_questions(reply_candidates, knowledge_candidates),
        }
        body, duration = self._request(payload)

        model = body.get("model")
        answers = body.get("answers")
        usage = body.get("usage") or {}
        if not isinstance(model, str) or not isinstance(answers, dict):
            raise ProviderError("Jev response is missing model or answers")
        self.resolved_models.add(model)
        call_usage = {
            "input_tokens": int(usage.get("input_tokens", 0)),
            "output_tokens": int(usage.get("output_tokens", 0)),
            "requests": 1,
            "duration_seconds": round(duration, 4),
            "cost": "unavailable",
        }
        for key in ("input_tokens", "output_tokens", "requests"):
            self.total_usage[key] += int(call_usage[key])
        return (
            answers_to_judge_output(record, reply_candidates, knowledge_candidates, answers, self.config),
            call_usage,
        )
