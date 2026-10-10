#!/usr/bin/env python3
"""Score predictions for Instruction-Following Translation Bench.

Reads a JSONL of {"case_id", "prediction"} rows, checks the five hard constraints
with rules, scores the five soft constraints and translation quality with an LLM
Judge, and writes per-instance scores plus aggregate metrics.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from eval.constraints import (
    SOFT_CONSTRAINT_IDS,
    check_hard_constraints,
    collect_soft_constraint_descs,
)
from eval.judge_client import JudgeClient, JudgeRequestError
from eval.metrics import (
    compute_if_score,
    compute_summary,
    parse_quality_score,
    parse_soft_constraint_scores,
)
from eval.prompts import (
    QUALITY_JUDGE_PROMPT_VERSION,
    build_quality_prompt,
    build_soft_constraint_prompt,
)

DEFAULT_DATA_FILE = Path(__file__).resolve().parent / "data/test.jsonl"
DEFAULT_JUDGE_MODEL = "gpt-5.6-sol"
DEFAULT_BASE_URL = "https://api.openai.com/v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    # split("\n"), not splitlines(): source text contains raw U+2028, which is
    # legal inside a JSON string but is a line break to splitlines().
    for line_number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    return rows


def load_predictions(path: Path, valid_ids: set[str]) -> dict[str, str]:
    predictions: dict[str, str] = {}
    for row in read_jsonl(path):
        case_id = row.get("case_id")
        if case_id is None:
            raise SystemExit(f"{path}: a prediction row is missing 'case_id'")
        if case_id in predictions:
            raise SystemExit(f"{path}: duplicate prediction for {case_id}")
        if case_id not in valid_ids:
            raise SystemExit(f"{path}: unknown case_id {case_id}")
        prediction = row.get("prediction")
        predictions[case_id] = prediction if isinstance(prediction, str) else ""
    return predictions


def score_row(
    row: dict[str, Any], prediction: str, judge: JudgeClient | None
) -> dict[str, Any]:
    """Score one instance. Missing predictions score 0 without calling the Judge."""
    present = bool(prediction.strip())

    hard_results = check_hard_constraints(row, prediction) if present else {}

    soft_results: dict[str, Any] = {}
    soft_cids = [cid for cid in row["constraint_ids"] if cid in SOFT_CONSTRAINT_IDS]
    if present and soft_cids and judge is not None:
        soft_descs = collect_soft_constraint_descs(row["constraint_ids"], row["constraints"])
        if soft_descs:
            soft_ids = list(soft_descs)
            response, _ = judge.complete(
                build_soft_constraint_prompt(row, prediction, soft_descs),
                validator=lambda text: all(
                    entry["score"] is not None
                    for entry in parse_soft_constraint_scores(text, soft_ids).values()
                ),
            )
            soft_results = parse_soft_constraint_scores(response, soft_ids)
            if any(value["score"] is None for value in soft_results.values()):
                raise ValueError("Judge returned incomplete or invalid soft-constraint scores")
    elif present and soft_cids:
        soft_results = {cid: {"score": None} for cid in soft_cids}

    quality_score = None
    if present and judge is not None:
        response, _ = judge.complete(
            build_quality_prompt(row, prediction),
            validator=lambda text: parse_quality_score(text) is not None,
        )
        quality_score = parse_quality_score(response)
        if quality_score is None:
            raise ValueError("Judge quality response must be exactly 0, 0.5 or 1")

    if_score = compute_if_score(hard_results, soft_results) if present else 0.0

    return {
        "case_id": row["case_id"],
        "source_lang": row["source_lang"],
        "target_lang": row["target_lang"],
        "scenario": row["scenario"],
        "domain": row["domain"],
        "constraint_ids": row["constraint_ids"],
        "prediction_status": "present" if present else "missing",
        "if_score": if_score,
        "quality_score": quality_score,
        "hard_constraint_results": hard_results,
        "soft_constraint_results": soft_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--data-file", type=Path, default=DEFAULT_DATA_FILE)
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0,
                        help="score only the first N instances (smoke check, not a formal result)")
    parser.add_argument("--skip-judge", action="store_true",
                        help="rule-only mode: hard constraints only, no Judge calls")
    parser.add_argument("--clear-judge-cache", action="store_true",
                        help="delete the Judge cache before scoring (a cached "
                             "verdict cannot be re-judged otherwise)")
    args = parser.parse_args()

    rows = read_jsonl(args.data_file)
    # --limit narrows what is scored, not which predictions are legal: a
    # predictions file covers the whole test set (and beyond its tail).
    all_case_ids = {row["case_id"] for row in rows}
    if args.limit:
        rows = rows[: args.limit]

    predictions = load_predictions(args.predictions, all_case_ids)
    missing = [row["case_id"] for row in rows if row["case_id"] not in predictions]
    if missing and not args.limit:
        print(f"warning: {len(missing)} instances have no prediction and will score 0",
              file=sys.stderr)

    judge = None
    if not args.skip_judge:
        judge = JudgeClient(
            api_key=os.environ.get("JUDGE_API_KEY", ""),
            base_url=os.environ.get("JUDGE_API_BASE", DEFAULT_BASE_URL),
            model=args.judge_model,
            prompt_version=QUALITY_JUDGE_PROMPT_VERSION,
            cache_path=args.output_dir / "judge_cache.jsonl",
        )
        if args.clear_judge_cache:
            judge.clear_cache()

    def work(row: dict[str, Any]) -> dict[str, Any]:
        return score_row(row, predictions.get(row["case_id"], ""), judge)

    try:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            scored = list(pool.map(work, rows))
    except JudgeRequestError as exc:
        # Aborting beats silently turning provider failures into quality scores.
        raise SystemExit(f"judge failure, aborting: {exc}") from exc

    summary = compute_summary(scored)
    summary["config"] = {
        "judge_model": None if args.skip_judge else args.judge_model,
        "quality_judge_prompt_version": QUALITY_JUDGE_PROMPT_VERSION,
        "data_file": str(args.data_file),
        "instances_scored": len(scored),
        "formal_run": not args.limit and not args.skip_judge,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "scores.jsonl").open("w", encoding="utf-8") as handle:
        for row in scored:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"instances:        {summary['total']}")
    print(f"coverage:         {summary['prediction_coverage']}/{summary['total']}")
    print(f"IF_Score:         {summary['if_score']:.4f}")
    if summary["translation_quality"] is not None:
        print(f"quality:          {summary['translation_quality']:.4f}")
    if not summary["config"]["formal_run"]:
        print("note: subset or rule-only run, not a full-benchmark result")


if __name__ == "__main__":
    main()
