from customer_reply_audit.comparison import compare_runs
from customer_reply_audit.models import DetectionItem, DetectionRun, RunMetadata, Severity, TruthRecord


def _run(mode, values, duration):
    items = [DetectionItem(
        id=str(index), mode=mode, status="ok", is_hallucination=value,
        severity=Severity.NONE, reason="test",
    ) for index, value in enumerate(values)]
    return DetectionRun(metadata=RunMetadata(
        run_id=mode, mode=mode, input_path="test", input_sha256="x",
        taxonomy_version="v1", taxonomy_sha256="x", prompt_version="v1", prompt_sha256="x",
        model=mode, temperature=0, started_at="now", finished_at="now",
        duration_seconds=duration, retries=0, usage={}, code_version="test",
    ), items=items)


def test_comparison_prefers_balanced_accuracy_after_coverage():
    truth = [
        TruthRecord(id="0", is_hallucination=True, detail="x"),
        TruthRecord(id="1", is_hallucination=True, detail="x"),
        TruthRecord(id="2", is_hallucination=False, detail="x"),
        TruthRecord(id="3", is_hallucination=False, detail="x"),
    ]
    comparison = compare_runs({
        "mock": _run("mock", [True, True, True, True], 0.1),
        "jev": _run("jev", [True, False, False, False], 1.0),
        "hybrid": _run("hybrid", [True, True, False, False], 2.0),
    }, truth)
    assert comparison["winner"] == "hybrid"
    assert comparison["experiment_complete"] is True
    assert comparison["ranking"][0] == "hybrid"


def test_comparison_refuses_winner_when_any_version_has_errors():
    truth = [TruthRecord(id="0", is_hallucination=True, detail="x")]
    runs = {
        "mock": _run("mock", [True], 0.1),
        "jev": _run("jev", [True], 1.0),
        "hybrid": _run("hybrid", [True], 2.0),
    }
    runs["jev"].items[0].status = "error"
    runs["jev"].items[0].is_hallucination = None
    comparison = compare_runs(runs, truth)
    assert comparison["experiment_complete"] is False
    assert comparison["winner"] is None
    assert comparison["disqualified"] == ["jev"]
