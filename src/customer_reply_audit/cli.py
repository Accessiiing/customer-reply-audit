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
from .comparison import compare_runs, write_comparison
from .evaluation import all_positive_baseline, evaluate, evaluation_markdown
from .hybrid_judge import HybridJudge
from .io import load_replies, load_truth, sha256_file, write_json
from .jev_provider import JevJudge
from .mock_judge import judge as mock_judge
from .models import DetectionRun, RunMetadata
from .preparation import prepare_replies
from .provider import OpenAICompatibleJudge
from .report import render_html

ROOT = Path(__file__).resolve().parents[2]
PROMPT = ROOT / "prompts" / "detect-v1.md"
TAXONOMY = ROOT / "configs" / "taxonomy.json"
MOCK_SOURCE = ROOT / "src" / "customer_reply_audit" / "mock_judge.py"


def _load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


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
    retries = 0
    jev_provider = None
    if mode == "mock":
        judge = mock_judge
        model = "deterministic-mock-rules-v2"
        prompt_version = "mock-rules-v2"
        prompt_sha256 = sha256_file(MOCK_SOURCE)
    elif mode == "real":
        provider = OpenAICompatibleJudge(prompt_path=PROMPT)
        model = provider.model
        prompt_version = "detect-v1"
        prompt_sha256 = sha256_file(PROMPT)

        def judge(record):
            result, call_usage = provider.judge(record)
            usage.update(call_usage)
            return result
    elif mode == "jev":
        jev_provider = JevJudge()
        model = jev_provider.model
        prompt_version = str(jev_provider.config["version"])
        prompt_sha256 = sha256_file(jev_provider.config_path)

        def judge(record):
            result, _ = jev_provider.judge(record)
            return result
    elif mode == "hybrid":
        jev_provider = JevJudge()
        hybrid = HybridJudge(jev_provider)
        model = hybrid.model
        prompt_version = f"mock-rules-v2+{jev_provider.config['version']}"
        prompt_sha256 = sha256_file(jev_provider.config_path)

        def judge(record):
            result, _ = hybrid.judge(record)
            return result
    else:  # pragma: no cover - argparse and callers constrain modes
        raise ValueError(f"unknown mode: {mode}")

    items = [detect_one(record, judge, mode=mode) for record in records]
    if jev_provider is not None:
        model = (
            jev_provider.resolved_model
            if mode == "jev"
            else f"hard-rules+{jev_provider.resolved_model}"
        )
        usage = {
            **jev_provider.total_usage,
            "provider_duration_seconds": round(jev_provider.total_duration_seconds, 4),
        }
        retries = jev_provider.total_retries
    finished = datetime.now(UTC)
    run_id = _run_id()
    run = DetectionRun(
        metadata=RunMetadata(
            run_id=run_id, mode=mode, input_path=str(input_path.resolve()), input_sha256=sha256_file(input_path),
            taxonomy_version=json.loads(TAXONOMY.read_text(encoding="utf-8"))["version"],
            taxonomy_sha256=sha256_file(TAXONOMY), prompt_version=prompt_version, prompt_sha256=prompt_sha256,
            model=model, temperature=0.0, started_at=started.isoformat(), finished_at=finished.isoformat(),
            duration_seconds=round(time.perf_counter() - start_clock, 4), retries=retries, usage=usage,
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
    _load_local_env(ROOT / ".env")
    parser = argparse.ArgumentParser(prog="reply-audit")
    sub = parser.add_subparsers(dest="command", required=True)
    detect_parser = sub.add_parser("detect", help="detect replies without reading ground truth")
    detect_parser.add_argument("--input", type=Path, required=True)
    modes = ["real", "mock", "jev", "hybrid"]
    detect_parser.add_argument("--mode", choices=modes, default="real")
    detect_parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts" / "runs")
    eval_parser = sub.add_parser("evaluate", help="compare saved predictions with ground truth")
    eval_parser.add_argument("--predictions", type=Path, required=True)
    eval_parser.add_argument("--truth", type=Path, required=True)
    report_parser = sub.add_parser("report", help="render escaped local HTML report")
    report_parser.add_argument("--predictions", type=Path, required=True)
    report_parser.add_argument("--evaluation", type=Path, required=True)
    report_parser.add_argument("--input", type=Path, required=True)
    report_parser.add_argument("--output", type=Path)
    run_parser = sub.add_parser("run", help="detect, then independently evaluate and render")
    run_parser.add_argument("--input", type=Path, required=True)
    run_parser.add_argument("--truth", type=Path, required=True)
    run_parser.add_argument("--mode", choices=modes, default="real")
    run_parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts" / "runs")
    prepare_parser = sub.add_parser("prepare-input", help="derive valid JSON from a source with explicit trailing contamination")
    prepare_parser.add_argument("--source", type=Path, required=True)
    prepare_parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts" / "staging")
    compare_parser = sub.add_parser("compare", help="compare completed mock, Jev, and hybrid prediction runs")
    compare_parser.add_argument("--mock-predictions", type=Path, required=True)
    compare_parser.add_argument("--jev-predictions", type=Path, required=True)
    compare_parser.add_argument("--hybrid-predictions", type=Path, required=True)
    compare_parser.add_argument("--truth", type=Path, required=True)
    compare_parser.add_argument("--output-dir", type=Path, required=True)
    benchmark_parser = sub.add_parser("benchmark", help="run all three versions and select the winner")
    benchmark_parser.add_argument("--input", type=Path, required=True)
    benchmark_parser.add_argument("--truth", type=Path, required=True)
    benchmark_parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts" / "runs")
    benchmark_parser.add_argument("--comparison-root", type=Path, default=ROOT / "artifacts" / "comparisons")

    args = parser.parse_args()
    needs_jev = args.command == "benchmark" or (
        args.command in {"detect", "run"} and getattr(args, "mode", None) in {"jev", "hybrid"}
    )
    if needs_jev and not (os.getenv("TYPESAFE_API_KEY") or os.getenv("JEV_API_KEY")):
        parser.error("Jev execution requires TYPESAFE_API_KEY or JEV_API_KEY; configure it locally and do not commit the key")
    if args.command == "detect":
        detect(args.input, mode=args.mode, output_root=args.output_root)
    elif args.command == "evaluate":
        evaluate_run(args.predictions, args.truth)
    elif args.command == "report":
        run = load_run(args.predictions)
        evaluation_payload = json.loads(args.evaluation.read_text(encoding="utf-8"))["result"]
        output = args.output or args.predictions.parent / "report.html"
        render_html(run, evaluation_payload, load_replies(args.input), output)
        print(f"report={output.resolve()}")
    elif args.command == "prepare-input":
        clean, manifest = prepare_replies(args.source, args.output_dir)
        print(f"clean_input={clean.resolve()}")
        print(f"manifest={manifest.resolve()}")
    elif args.command == "compare":
        runs = {
            "mock": load_run(args.mock_predictions),
            "jev": load_run(args.jev_predictions),
            "hybrid": load_run(args.hybrid_predictions),
        }
        comparison = compare_runs(runs, load_truth(args.truth))
        write_comparison(args.output_dir, comparison)
        print(f"winner={comparison['winner']} comparison={args.output_dir.resolve()}")
    elif args.command == "benchmark":
        # Fail before writing a partial three-version experiment when credentials are absent.
        JevJudge()
        run_dirs = {
            mode: detect(args.input, mode=mode, output_root=args.output_root)
            for mode in ("mock", "jev", "hybrid")
        }
        runs = {mode: load_run(path / "predictions.json") for mode, path in run_dirs.items()}
        comparison = compare_runs(runs, load_truth(args.truth))
        comparison_dir = args.comparison_root / _run_id()
        write_comparison(comparison_dir, comparison)
        print(f"winner={comparison['winner']} comparison={comparison_dir.resolve()}")
    else:
        run_dir = detect(args.input, mode=args.mode, output_root=args.output_root)
        predictions = run_dir / "predictions.json"
        result, _ = evaluate_run(predictions, args.truth)
        run = load_run(predictions)
        render_html(run, result, load_replies(args.input), run_dir / "report.html")
        print(f"report={(run_dir / 'report.html').resolve()}")


if __name__ == "__main__":
    main()
