from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .detector import detect_one
from .evaluation import all_positive_baseline, evaluate, evaluation_markdown
from .io import load_replies, load_truth, sha256_file, write_json
from .mock_judge import judge as mock_judge
from .models import DetectionRun, RunMetadata
from .provider import OpenAICompatibleJudge
from .report import render_html

ROOT = Path(__file__).resolve().parents[2]
PROMPT = ROOT / "prompts" / "detect-v1.md"
TAXONOMY = ROOT / "configs" / "taxonomy.json"


def _git_version() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
        return sha + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def _run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]


def detect(input_path: Path, *, mode: str, output_root: Path) -> Path:
    records = load_replies(input_path)
    started = datetime.now(UTC)
    start_clock = time.perf_counter()
    usage: dict[str, int | float | str] = {"tokens": "unavailable", "cost": "unavailable"}
    if mode == "mock":
        judge = mock_judge
        model = "deterministic-mock-rules-v1"
    else:
        provider = OpenAICompatibleJudge(prompt_path=PROMPT)
        model = provider.model

        def judge(record):
            result, call_usage = provider.judge(record)
            usage.update(call_usage)
            return result

    items = [detect_one(record, judge, mode=mode) for record in records]
    finished = datetime.now(UTC)
    run_id = _run_id()
    run = DetectionRun(
        metadata=RunMetadata(
            run_id=run_id, mode=mode, input_path=str(input_path.resolve()), input_sha256=sha256_file(input_path),
            taxonomy_version=json.loads(TAXONOMY.read_text(encoding="utf-8"))["version"],
            taxonomy_sha256=sha256_file(TAXONOMY), prompt_version="detect-v1", prompt_sha256=sha256_file(PROMPT),
            model=model, temperature=0.0, started_at=started.isoformat(), finished_at=finished.isoformat(),
            duration_seconds=round(time.perf_counter() - start_clock, 4), retries=0, usage=usage,
            code_version=_git_version(),
        ),
        items=items,
    )
    run_dir = output_root / run_id
    write_json(run_dir / "predictions.json", run)
    print(f"run_id={run_id} mode={mode} items={len(items)} output={run_dir}")
    return run_dir


def load_run(path: Path) -> DetectionRun:
    return DetectionRun.model_validate_json(path.read_text(encoding="utf-8"))


def evaluate_run(predictions: Path, truth_path: Path) -> tuple[dict, Path]:
    run = load_run(predictions)
    truth = load_truth(truth_path)
    result = evaluate(run.items, truth)
    baseline = all_positive_baseline(truth)
    run_dir = predictions.parent
    write_json(run_dir / "evaluation.json", {"run_id": run.metadata.run_id, "mode": run.metadata.mode, "result": result, "all_positive_baseline": baseline})
    (run_dir / "evaluation.md").write_text(
        evaluation_markdown(result, baseline, run_id=run.metadata.run_id, mode=run.metadata.mode), encoding="utf-8"
    )
    print(f"TP={result['confusion_matrix']['TP']} FP={result['confusion_matrix']['FP']} TN={result['confusion_matrix']['TN']} FN={result['confusion_matrix']['FN']}")
    print(f"evaluation={run_dir / 'evaluation.md'}")
    return result, run_dir


def main() -> None:
    parser = argparse.ArgumentParser(prog="reply-audit")
    sub = parser.add_subparsers(dest="command", required=True)
    detect_parser = sub.add_parser("detect", help="detect replies without reading ground truth")
    detect_parser.add_argument("--input", type=Path, required=True)
    detect_parser.add_argument("--mode", choices=["real", "mock"], default="real")
    detect_parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts" / "runs")
    eval_parser = sub.add_parser("evaluate", help="compare saved predictions with ground truth")
    eval_parser.add_argument("--predictions", type=Path, required=True)
    eval_parser.add_argument("--truth", type=Path, required=True)
    report_parser = sub.add_parser("report", help="render escaped local HTML report")
    report_parser.add_argument("--predictions", type=Path, required=True)
    report_parser.add_argument("--evaluation", type=Path, required=True)
    report_parser.add_argument("--input", type=Path, required=True)
    report_parser.add_argument("--output", type=Path)

    args = parser.parse_args()
    if args.command == "detect":
        detect(args.input, mode=args.mode, output_root=args.output_root)
    elif args.command == "evaluate":
        evaluate_run(args.predictions, args.truth)
    else:
        run = load_run(args.predictions)
        evaluation_payload = json.loads(args.evaluation.read_text(encoding="utf-8"))["result"]
        output = args.output or args.predictions.parent / "report.html"
        render_html(run, evaluation_payload, load_replies(args.input), output)
        print(f"report={output.resolve()}")


if __name__ == "__main__":
    main()

