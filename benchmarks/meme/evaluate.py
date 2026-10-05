#!/usr/bin/env python3
"""Score Chinese-to-English translations for Meme Translation Bench."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

BENCHMARK_DIR = Path(__file__).resolve().parent
from eval.judge_client import (  # noqa: E402
    JUDGE_MAX_TOKENS,
    JUDGE_TEMPERATURE,
    JudgeClient,
)
from eval.metrics import compute_summary  # noqa: E402
from eval.prompts import (  # noqa: E402
    JUDGE_PROMPT_VERSION,
    build_judge_prompt,
    prompt_sha256,
)
from eval.score_parser import parse_score  # noqa: E402

EXPECTED_CASES = 3638


def redact_base_url(base_url: str) -> str:
    """Publish endpoint identity without credentials, paths or URL parameters."""
    try:
        parsed = urlsplit(base_url)
        host = parsed.hostname
        if not parsed.scheme or not host:
            return "<redacted>"
        if ":" in host:
            host = f"[{host}]"
        if parsed.port is not None:
            host += f":{parsed.port}"
        return f"{parsed.scheme}://{host}"
    except ValueError:
        return "<redacted>"


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected object")
            rows.append(row)
    return rows


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def load_cases(data_dir: Path, limit: int = 0) -> list[dict[str, Any]]:
    if limit < 0:
        raise ValueError("limit must be non-negative")
    cases = read_jsonl(data_dir / "test.jsonl")
    if not limit and len(cases) != EXPECTED_CASES:
        raise ValueError(f"expected {EXPECTED_CASES} benchmark cases, got {len(cases)}")
    return cases[:limit] if limit else cases


def load_prediction_map(
    path: Path, cases: list[dict[str, Any]]
) -> tuple[dict[str, str], dict[str, int]]:
    payload = read_json(path) if path.suffix.lower() == ".json" else read_jsonl(path)
    if isinstance(payload, dict):
        payload = payload.get("results", payload.get("predictions"))
    if not isinstance(payload, list):
        raise ValueError("prediction input must be a JSON array or JSONL objects")
    valid_ids = {case["sentence_id"] for case in cases}
    predictions: dict[str, str] = {}
    seen_ids: set[str] = set()
    empty = 0
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(f"prediction[{index}] must be an object")
        sentence_id = row.get("sentence_id")
        if not isinstance(sentence_id, str) or not sentence_id:
            raise ValueError(f"prediction[{index}] has invalid sentence_id")
        if sentence_id not in valid_ids:
            raise ValueError(f"prediction[{index}] has unknown sentence_id {sentence_id!r}")
        if sentence_id in seen_ids:
            raise ValueError(f"duplicate prediction for {sentence_id!r}")
        seen_ids.add(sentence_id)
        value = row.get("prediction", row.get("translation"))
        if value is None and "content" in row:
            value = row["content"]
        if not isinstance(value, str):
            raise ValueError(f"prediction[{index}] prediction must be a string")
        value = value.strip()
        if value:
            predictions[sentence_id] = value
        else:
            empty += 1
    if not predictions:
        raise ValueError(
            f"{path}: no usable predictions found ({len(payload)} input rows, "
            f"{empty} empty predictions); refusing to report a zero-score run"
        )
    return predictions, {"input_rows": len(payload), "empty_predictions": empty}


def score_predictions(
    *,
    cases: list[dict[str, Any]],
    contexts: dict[str, dict[str, Any]],
    predictions: dict[str, str],
    client: JudgeClient,
    max_workers: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Score every case, but abort the queue on the first judge failure.

    A judge failure (spent retry budget, empty response) aborts the run instead of
    letting the remaining thousands of queued cases run: pending futures are
    cancelled, only in-flight calls finish, and the rows already scored are returned
    so the caller can still persist a partial, clearly marked report.
    """
    results_by_index: dict[int, dict[str, Any]] = {}
    audits: list[dict[str, Any]] = []
    abort_error: str | None = None

    def score_one(index: int, case: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        prediction = predictions.get(case["sentence_id"])
        base = {
            "sentence_id": case["sentence_id"],
            "term_id": case["term_id"],
            "definition_id": case["definition_id"],
            "text_type": case["text_type"],
        }
        if prediction is None:
            return index, {
                **base,
                "prediction": None,
                "prediction_status": "missing",
                "judge_status": "not_called",
                "score": 0.0,
                "parse_status": "missing_prediction_0",
            }
        context = contexts[case["definition_id"]]
        prompt = build_judge_prompt(case, context, prediction)
        response, cached = client.complete(prompt)
        parsed = parse_score(response)
        return index, {
            **base,
            "prediction": prediction,
            "prediction_status": "present",
            "judge_status": (
                "success" if parsed.parse_status != "nonstandard_fallback_0" else "unparsed"
            ),
            "judge_cached": cached,
            "judge_prompt_version": JUDGE_PROMPT_VERSION,
            "judge_prompt_sha256": prompt_sha256(prompt),
            "judge_response": response,
            "score": parsed.score,
            "parse_status": parsed.parse_status,
            "matched_score_text": parsed.matched_text,
        }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(score_one, i, case): i for i, case in enumerate(cases)}
        try:
            for completed, future in enumerate(as_completed(futures), 1):
                index, result = future.result()
                results_by_index[index] = result
                if result["parse_status"] == "nonstandard_fallback_0":
                    normalized_prediction = str(result["prediction"] or "").strip().lower()
                    audits.append({
                        "sentence_id": result["sentence_id"],
                        "prediction": result["prediction"],
                        "judge_response": result["judge_response"],
                        "parsed_score": result["score"],
                        "parse_status": result["parse_status"],
                        "audit_decision": (
                            "keep_0_candidate_is_NA"
                            if normalized_prediction in {"n/a", "na"}
                            else "needs_review"
                        ),
                    })
                if completed % 100 == 0:
                    print(f"Judge progress: {completed}/{len(cases)}", flush=True)
        except Exception as exc:
            # Do not wait for the still-queued judge calls; report what we have.
            abort_error = f"{type(exc).__name__}: {exc}"
            for future in futures:
                future.cancel()
        except BaseException:
            for future in futures:
                future.cancel()
            raise
    results = [results_by_index[index] for index in sorted(results_by_index)]
    run_state = {
        "aborted": abort_error is not None,
        "abort_error": abort_error,
        "scored_cases": len(results),
        "total_cases": len(cases),
    }
    return results, audits, run_state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=BENCHMARK_DIR / "data")
    parser.add_argument("--limit", type=int, default=0, help="Subset for smoke checks; 0 scores the full benchmark")
    parser.add_argument("--judge-model", default="gemini-2.5-flash")
    parser.add_argument("--judge-base-url", default=os.environ.get("JUDGE_API_BASE"))
    parser.add_argument("--judge-cache", type=Path)
    parser.add_argument("--num-processes", type=int, default=20)
    args = parser.parse_args()
    if not args.judge_base_url:
        parser.error("provide --judge-base-url or set JUDGE_API_BASE to an OpenAI-compatible endpoint")
    if args.limit < 0 or args.num_processes < 1:
        parser.error("--limit must be non-negative and --num-processes must be positive")
    return args


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cases = load_cases(args.data_dir, args.limit)
    inference_path = args.predictions
    predictions, input_stats = load_prediction_map(inference_path, cases)
    contexts = {case["definition_id"]: case for case in cases}
    client = JudgeClient(
        api_key=os.environ.get("JUDGE_API_KEY", ""),
        base_url=args.judge_base_url,
        model=args.judge_model,
        prompt_version=JUDGE_PROMPT_VERSION,
        cache_path=args.judge_cache or args.output_dir / "judge_cache.jsonl",
    )
    results, audits, run_state = score_predictions(
        cases=cases,
        contexts=contexts,
        predictions=predictions,
        client=client,
        max_workers=args.num_processes,
    )
    metrics = compute_summary(results)
    now = datetime.now(timezone.utc).isoformat()
    summary = {
        "benchmark": "meme_translation",
        "benchmark_version": "v1",
        "formal_run": args.limit == 0 and not run_state["aborted"],
        "timestamp": now,
        "run_state": run_state,
        "judge": {
            "model": args.judge_model,
            "base_url": redact_base_url(args.judge_base_url),
            "prompt_version": JUDGE_PROMPT_VERSION,
            "temperature": JUDGE_TEMPERATURE,
            "max_tokens": JUDGE_MAX_TOKENS,
        },
        "prediction_input": {
            "path": str(inference_path),
            **input_stats,
            "missing_predictions": len(cases) - len(predictions),
        },
        **metrics,
    }
    atomic_json(
        args.output_dir / "eval_results.json",
        {"summary": summary, "results": results, "run_state": run_state},
    )
    atomic_json(args.output_dir / "score_parse_audit.json", audits)
    atomic_json(args.output_dir / "eval_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if run_state["aborted"]:
        print(
            "ABORTED after "
            f"{run_state['scored_cases']}/{run_state['total_cases']} cases "
            f"({run_state['abort_error']}); partial results written to {args.output_dir}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
