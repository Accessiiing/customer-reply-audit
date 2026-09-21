from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .models import DetectionItem, TruthRecord


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def evaluate(items: Iterable[DetectionItem], truth: Iterable[TruthRecord]) -> dict[str, Any]:
    predictions = list(items)
    labels = list(truth)
    pred_by_id = {item.id: item for item in predictions}
    truth_by_id = {item.id: item for item in labels}
    if len(pred_by_id) != len(predictions):
        raise ValueError("prediction IDs must be unique")
    if len(truth_by_id) != len(labels):
        raise ValueError("truth IDs must be unique")
    missing = sorted(truth_by_id.keys() - pred_by_id.keys())
    extra = sorted(pred_by_id.keys() - truth_by_id.keys())
    if missing or extra:
        raise ValueError(f"ID mismatch: missing_predictions={missing}, extra_predictions={extra}")

    buckets = {name: [] for name in ("tp", "fp", "tn", "fn")}
    unresolved = {"needs_review": [], "error": []}
    for record_id in truth_by_id:
        prediction, label = pred_by_id[record_id], truth_by_id[record_id]
        if prediction.status != "ok":
            unresolved[prediction.status].append(record_id)
            continue
        if prediction.is_hallucination and label.is_hallucination:
            buckets["tp"].append(record_id)
        elif prediction.is_hallucination and not label.is_hallucination:
            buckets["fp"].append(record_id)
        elif not prediction.is_hallucination and not label.is_hallucination:
            buckets["tn"].append(record_id)
        else:
            buckets["fn"].append(record_id)

    tp, fp, tn, fn = (len(buckets[key]) for key in ("tp", "fp", "tn", "fn"))
    valid = tp + fp + tn + fn
    positives = sum(record.is_hallucination for record in labels)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    specificity = _ratio(tn, tn + fp)
    result = {
        "dataset": {
            "total": len(labels),
            "positive": positives,
            "negative": len(labels) - positives,
            "valid_decisions": valid,
            "decision_coverage": _ratio(valid, len(labels)),
        },
        "confusion_matrix": {key.upper(): len(value) for key, value in buckets.items()},
        "ids": {key.upper(): value for key, value in buckets.items()},
        "unresolved": {
            "needs_review_count": len(unresolved["needs_review"]),
            "needs_review_ids": unresolved["needs_review"],
            "error_count": len(unresolved["error"]),
            "error_ids": unresolved["error"],
        },
        "metrics_on_valid_decisions": {
            "precision": precision,
            "recall": recall,
            "f1": _ratio(2 * precision * recall, precision + recall) if precision is not None and recall is not None else None,
            "accuracy": _ratio(tp + tn, valid),
            "normal_reply_false_positive_rate": _ratio(fp, fp + tn),
            "balanced_accuracy": _ratio((recall or 0) + (specificity or 0), 2) if recall is not None and specificity is not None else None,
        },
        "full_positive_confirmed_rate": _ratio(tp, positives),
    }
    return result


def all_positive_baseline(truth: Iterable[TruthRecord]) -> dict[str, Any]:
    labels = list(truth)
    positives = sum(record.is_hallucination for record in labels)
    negatives = len(labels) - positives
    precision = _ratio(positives, len(labels))
    recall = 1.0 if positives else None
    return {
        "TP": positives, "FP": negatives, "TN": 0, "FN": 0,
        "precision": precision,
        "recall": recall,
        "f1": _ratio(2 * precision * recall, precision + recall) if precision is not None and recall is not None else None,
        "accuracy": _ratio(positives, len(labels)),
        "normal_reply_false_positive_rate": 1.0 if negatives else None,
        "balanced_accuracy": 0.5 if positives and negatives else None,
    }


def format_metric(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1%}"


def evaluation_markdown(result: dict[str, Any], baseline: dict[str, Any], *, run_id: str, mode: str) -> str:
    cm, metrics, data = result["confusion_matrix"], result["metrics_on_valid_decisions"], result["dataset"]
    ids = result["ids"]
    return f"""# 评估结果

- run_id：`{run_id}`
- 运行模式：`{mode}`
- 数据：{data['total']} 条（正例 {data['positive']} / 负例 {data['negative']}）
- 有效二元判定：{data['valid_decisions']}，覆盖率 {format_metric(data['decision_coverage'])}

## 主要指标（仅有效判定）

| TP | FP | TN | FN | Precision | Recall | F1 | Accuracy | 正常回复误报率 | Balanced Accuracy |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| {cm['TP']} | {cm['FP']} | {cm['TN']} | {cm['FN']} | {format_metric(metrics['precision'])} | {format_metric(metrics['recall'])} | {format_metric(metrics['f1'])} | {format_metric(metrics['accuracy'])} | {format_metric(metrics['normal_reply_false_positive_rate'])} | {format_metric(metrics['balanced_accuracy'])} |

- TP：{', '.join(ids['TP']) or '无'}
- FP：{', '.join(ids['FP']) or '无'}
- TN：{', '.join(ids['TN']) or '无'}
- FN：{', '.join(ids['FN']) or '无'}
- needs_review：{', '.join(result['unresolved']['needs_review_ids']) or '无'}
- error：{', '.join(result['unresolved']['error_ids']) or '无'}
- 全量正例已确认检出比例：{format_metric(result['full_positive_confirmed_rate'])}

## “全部判为幻觉”朴素基线

准确率 {format_metric(baseline['accuracy'])}，召回率 {format_metric(baseline['recall'])}，F1 {format_metric(baseline['f1'])}，正常回复误报率 {format_metric(baseline['normal_reply_false_positive_rate'])}，Balanced Accuracy {format_metric(baseline['balanced_accuracy'])}。

> 指标只比较二分类标签。自定义多标签类型与人工单一类型没有同口径金标准，因此不报告类型准确率。`mock` 结果只证明受限规则流程，不证明真实模型效果或泛化能力。
"""

