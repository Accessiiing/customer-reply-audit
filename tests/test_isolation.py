from pathlib import Path


def test_detection_runtime_does_not_reference_ground_truth_contract():
    root = Path(__file__).resolve().parents[1] / "src/customer_reply_audit"
    for filename in ("detector.py", "provider.py", "mock_judge.py"):
        source = (root / filename).read_text(encoding="utf-8")
        assert "TruthRecord" not in source
        assert "ground_truth" not in source


def test_real_mode_requires_local_credentials(monkeypatch):
    from customer_reply_audit.provider import OpenAICompatibleJudge, ProviderError

    monkeypatch.delenv("AUDIT_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AUDIT_MODEL", "test-model")
    prompt = Path(__file__).resolve().parents[1] / "prompts/detect-v1.md"
    try:
        OpenAICompatibleJudge(prompt_path=prompt)
    except ProviderError as exc:
        assert "AUDIT_API_KEY" in str(exc)
    else:
        raise AssertionError("real mode accepted missing credentials")
