from customer_reply_audit.candidates import build_candidates, build_jev_questions, build_jev_state
from customer_reply_audit.models import ReplyRecord


def test_candidates_keep_exact_source_spans_and_bind_relation_to_evidence():
    record = ReplyRecord(
        id="x",
        user_question="版本？",
        system_reply="版本是5.3，支持多设备。",
        knowledge_base="版本是5.0。仅支持单设备。",
    )
    reply, knowledge = build_candidates(record)
    assert all(item.text in record.system_reply for item in reply)
    assert all(item.text in record.knowledge_base for item in knowledge)
    questions = build_jev_questions(reply, knowledge)
    relation = questions["relation_R01"]
    assert "supported_by_K01" in relation["criteria"]
    assert "contradicted_by_K01" in relation["criteria"]
    assert questions["coverage_K01"]["type"] == "choice"
    state = build_jev_state(record, reply, knowledge)
    assert state["reply_claim_candidates"][0]["text"] == reply[0].text

