import json

import httpx

from customer_reply_audit.detector import aggregate
from customer_reply_audit.hybrid_judge import HybridJudge
from customer_reply_audit.jev_provider import JevJudge, answers_to_judge_output
from customer_reply_audit.candidates import build_candidates, build_jev_questions
from customer_reply_audit.models import (
    Claim,
    EvidenceRelation,
    IssueType,
    JudgeOutput,
    ReplyRecord,
    Severity,
)


RECORD = ReplyRecord(
    id="x",
    user_question="版本？",
    system_reply="版本是5.3。",
    knowledge_base="版本是5.0。",
)


def _choice(selected, options):
    return {
        "type": "choice",
        "choice": selected,
        "probabilities": {name: 1.0 if name == selected else 0.0 for name in options},
        "confidence": 1.0,
    }


def _answers(questions, relation="supported_by_K01", issue="none"):
    answers = {}
    for name, question in questions.items():
        if name.startswith("relation_"):
            answers[name] = _choice(relation, question["criteria"])
        elif name.startswith("material_"):
            answers[name] = {"type": "noul", "noul": 1.0}
        elif name.startswith("issue_"):
            answers[name] = _choice(issue, question["criteria"])
        else:
            answers[name] = _choice("covered", question["criteria"])
    return answers


def test_jev_http_contract_and_resolved_model(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

    def handler(request: httpx.Request):
        assert request.url.path == "/v1/systemone"
        assert request.headers["authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        assert payload["model"] == "jev-1.13.0"
        return httpx.Response(200, json={
            "model": "jev-1.13.0",
            "answers": _answers(payload["questions"]),
            "usage": {"input_tokens": 123, "output_tokens": 45},
        })

    judge = JevJudge(transport=httpx.MockTransport(handler))
    output, usage = judge.judge(RECORD)
    item = aggregate(RECORD, output, mode="jev")
    assert item.status == "ok" and item.is_hallucination is False
    assert judge.resolved_model == "jev-1.13.0"
    assert usage["input_tokens"] == 123
    assert judge.total_usage["requests"] == 1


def test_jev_contradiction_becomes_a_grounded_problem(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    reply, knowledge = build_candidates(RECORD)
    questions = build_jev_questions(reply, knowledge)
    answers = _answers(questions, relation="contradicted_by_K01", issue="factual_contradiction")
    config = {
        "relation_min_probability": 0.60,
        "choice_min_confidence": 0.25,
        "material_probability_threshold": 0.55,
        "omission_min_probability": 0.60,
    }
    output = answers_to_judge_output(RECORD, reply, knowledge, answers, config)
    item = aggregate(RECORD, output, mode="jev")
    assert item.is_hallucination is True
    assert item.evidence_quotes == ["版本是5.0。"]
    assert IssueType.FACTUAL_CONTRADICTION in item.issue_types


def test_hybrid_keeps_hard_rules_while_using_jev_semantics():
    record = ReplyRecord(
        id="cap",
        user_question="改好了吗？",
        system_reply="已帮您修改完成。",
        knowledge_base="客服系统未接入订单修改接口。",
    )

    class FakeJev:
        resolved_model = "jev-test"

        def judge(self, _record):
            return JudgeOutput(claims=[Claim(
                reply_quote=record.system_reply,
                subject="reply",
                predicate="semantic",
                value="supported",
                relation=EvidenceRelation.SUPPORTED,
                evidence_quote=record.knowledge_base,
                issue_types=[],
                severity=Severity.NONE,
                reason="fake semantic output",
            )]), {"requests": 1}

    output, _ = HybridJudge(FakeJev()).judge(record)
    item = aggregate(record, output, mode="hybrid")
    assert item.is_hallucination is True
    assert IssueType.FABRICATED_CAPABILITY in item.issue_types

