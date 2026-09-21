import json

import pytest
from pydantic import ValidationError

from customer_reply_audit.io import load_replies, quote_exists
from customer_reply_audit.models import Claim, EvidenceRelation, IssueType, Severity


def test_quote_normalization_is_fixed_and_reproducible():
    assert quote_exists("蓝牙 5.0", "参数：蓝牙5.0。")
    assert not quote_exists("蓝牙5.3", "参数：蓝牙5.0。")


def test_duplicate_input_ids_are_rejected(tmp_path):
    row = {"id": "x", "user_question": "q", "system_reply": "r", "knowledge_base": "k"}
    path = tmp_path / "input.json"
    path.write_text(json.dumps([row, row]), encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_replies(path)


def test_unsupported_cannot_fabricate_evidence_quote():
    with pytest.raises(ValidationError):
        Claim(
            reply_quote="支持", subject="功能", predicate="支持", value="是",
            relation=EvidenceRelation.UNSUPPORTED, evidence_quote="不存在的证据",
            issue_types=[IssueType.UNSUPPORTED_ASSERTION], severity=Severity.MEDIUM,
            reason="知识库没有相关参数。",
        )

