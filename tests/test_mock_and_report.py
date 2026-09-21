from pathlib import Path

from customer_reply_audit.detector import aggregate
from customer_reply_audit.evaluation import evaluate
from customer_reply_audit.io import load_replies, load_truth
from customer_reply_audit.mock_judge import judge
from customer_reply_audit.models import DetectionRun, RunMetadata
from customer_reply_audit.report import render_html


ROOT = Path(__file__).resolve().parents[1]


def test_mock_has_no_known_task_ids_or_truth_import():
    source = (ROOT / "src/customer_reply_audit/mock_judge.py").read_text(encoding="utf-8")
    assert "ground_truth" not in source
    for index in range(1, 21):
        assert f"h{index:02}" not in source


def test_synthetic_e2e_and_html_escaping(tmp_path):
    records = load_replies(ROOT / "data/examples/replies.json")
    items = [aggregate(record, judge(record), mode="mock") for record in records]
    result = evaluate(items, load_truth(ROOT / "data/examples/ground_truth.json"))
    assert result["confusion_matrix"] == {"TP": 1, "FP": 0, "TN": 1, "FN": 0}
    records[0].system_reply += "<script>alert(1)</script>"
    run = DetectionRun(metadata=RunMetadata(
        run_id="test", mode="mock", input_path="test", input_sha256="x", taxonomy_version="v1",
        taxonomy_sha256="x", prompt_version="v1", prompt_sha256="x", model="mock", temperature=0,
        started_at="now", finished_at="now", duration_seconds=0, retries=0,
        usage={"tokens": "unavailable"}, code_version="test",
    ), items=items)
    output = tmp_path / "report.html"
    render_html(run, result, records, output)
    rendered = output.read_text(encoding="utf-8")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "<script>alert(1)</script>" not in rendered

