import json

import pytest

from customer_reply_audit.preparation import prepare_replies


def test_prepare_input_preserves_source_and_records_trailing_data(tmp_path):
    records = [{"id": "x", "user_question": "q", "system_reply": "r", "knowledge_base": "k"}]
    source = tmp_path / "source.json"
    original = json.dumps(records, ensure_ascii=False) + "\nnotes outside json\n"
    source.write_text(original, encoding="utf-8")
    clean, manifest = prepare_replies(source, tmp_path / "derived")
    assert source.read_text(encoding="utf-8") == original
    assert json.loads(clean.read_text(encoding="utf-8"))[0]["id"] == "x"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["record_count"] == 1
    assert payload["trailing_chars"] > 0


def test_prepare_input_refuses_to_rewrite_valid_json(tmp_path):
    source = tmp_path / "valid.json"
    source.write_text('[]', encoding="utf-8")
    with pytest.raises(ValueError, match="already valid"):
        prepare_replies(source, tmp_path / "derived")

