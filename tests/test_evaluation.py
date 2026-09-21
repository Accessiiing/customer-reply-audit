import pytest

from customer_reply_audit.evaluation import all_positive_baseline, evaluate
from customer_reply_audit.models import DetectionItem, Severity, TruthRecord


def pred(record_id, status, value):
    return DetectionItem(
        id=record_id, mode="mock", status=status, is_hallucination=value,
        severity=Severity.NONE, reason="test",
    )


def truth(record_id, value):
    return TruthRecord(id=record_id, is_hallucination=value, detail="test")


def test_confusion_matrix_and_unresolved_denominators():
    result = evaluate(
        [pred("tp", "ok", True), pred("fp", "ok", True), pred("fn", "ok", False), pred("pending", "needs_review", None)],
        [truth("tp", True), truth("fp", False), truth("fn", True), truth("pending", True)],
    )
    assert result["confusion_matrix"] == {"TP": 1, "FP": 1, "TN": 0, "FN": 1}
    assert result["dataset"]["valid_decisions"] == 3
    assert result["full_positive_confirmed_rate"] == pytest.approx(1 / 3)
    assert result["unresolved"]["needs_review_ids"] == ["pending"]


def test_id_mismatch_is_rejected():
    with pytest.raises(ValueError, match="ID mismatch"):
        evaluate([pred("x", "ok", False)], [truth("y", False)])


def test_all_positive_baseline_exposes_imbalance():
    labels = [truth(str(i), i < 18) for i in range(20)]
    baseline = all_positive_baseline(labels)
    assert baseline["accuracy"] == 0.9
    assert baseline["normal_reply_false_positive_rate"] == 1.0
    assert baseline["balanced_accuracy"] == 0.5

