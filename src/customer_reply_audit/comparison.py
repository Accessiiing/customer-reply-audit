from __future__ import annotations

from pathlib import Path
from typing import Any

from .evaluation import evaluate, format_metric
from .io import write_json
from .models import DetectionRun, TruthRecord


EXPECTED_MODES = ("mock", "jev", "hybrid")
DEPENDENCY_PREFERENCE = {"mock": 0, "hybrid": 1, "jev": 2}


def compare_runs(runs: dict[str, DetectionRun], truth: list[TruthRecord]) -> dict[str, Any]:
    if set(runs) != set(EXPECTED_MODES):
        raise ValueError(f"comparison requires exactly {EXPECTED_MODES}; got {sorted(runs)}")
    versions: dict[str, Any] = {}
    for mode in EXPECTED_MODES:
        run = runs[mode]
        result = evaluate(run.items, truth)
        versions[mode] = {
            "run_id": run.metadata.run_id,
            "model": run.metadata.model,
            "duration_seconds": run.metadata.duration_seconds,
            "usage": run.metadata.usage,
            "evaluation": result,
        }

    eligible = [
        mode for mode, data in versions.items()
        if data["evaluation"]["unresolved"]["error_count"] == 0
    ]
    if not eligible:
        raise ValueError("no version is eligible: every run contains system errors")

    def score(mode: str) -> tuple:
        data = versions[mode]
        result = data["evaluation"]
        metrics = result["metrics_on_valid_decisions"]
        return (
            result["dataset"]["decision_coverage"] or 0.0,
            metrics["balanced_accuracy"] or 0.0,
            metrics["f1"] or 0.0,
            -(metrics["normal_reply_false_positive_rate"] if metrics["normal_reply_false_positive_rate"] is not None else 1.0),
            -float(data["duration_seconds"]),
            -DEPENDENCY_PREFERENCE[mode],
        )

    winner = max(eligible, key=score)
    return {
        "policy_version": "final-selection-policy-v1",
        "winner": winner,
        "versions": versions,
        "ranking": sorted(eligible, key=score, reverse=True),
    }


def comparison_markdown(comparison: dict[str, Any]) -> str:
    rows = []
    for mode in EXPECTED_MODES:
        data = comparison["versions"][mode]
        result = data["evaluation"]
        cm = result["confusion_matrix"]
        metrics = result["metrics_on_valid_decisions"]
        rows.append(
            f"| {mode} | {data['model']} | {cm['TP']} | {cm['FP']} | {cm['TN']} | {cm['FN']} | "
            f"{format_metric(result['dataset']['decision_coverage'])} | {format_metric(metrics['balanced_accuracy'])} | "
            f"{format_metric(metrics['f1'])} | {format_metric(metrics['normal_reply_false_positive_rate'])} | {data['duration_seconds']:.4f}s |"
        )
    return f"""# 三版本比较

> 最终选择由 `final-selection-policy-v1` 自动产生，不允许在看到结果后修改排序规则。

| 模式 | 模型 | TP | FP | TN | FN | 覆盖率 | Balanced Accuracy | F1 | 正常回复误报率 | 耗时 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## 最终选择

- 胜出版本：`{comparison['winner']}`
- 排名：{' → '.join(comparison['ranking'])}
"""


def write_comparison(output_dir: Path, comparison: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=False)
    write_json(output_dir / "comparison.json", comparison)
    (output_dir / "comparison.md").write_text(comparison_markdown(comparison), encoding="utf-8")
