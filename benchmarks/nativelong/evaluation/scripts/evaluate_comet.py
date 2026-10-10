#!/usr/bin/env python3
"""Score SEGALE-aligned windows with COMET and aggregate document diagnostics.

This adapter follows SEGALE's document aggregation rule: every null alignment
receives a COMET score of 0 and remains in document and corpus means. It runs
only reference-based COMET; unavailable optional metrics are represented by an
explicit status and a JSON null value rather than a synthetic numeric score.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import shutil
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import torch

# unbabel-comet 2.2.7 can select an unusable MPS DataLoader path on macOS even
# when CPU inference is requested. CUDA inference is unaffected by this guard.
torch.backends.mps.is_available = lambda: False

from comet import download_model, load_from_checkpoint  # noqa: E402


POSITION_BUCKETS = ("beginning", "middle", "end")
UNCLASSIFIED_WINDOW = "unclassified"


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_checkpoint_sha256(
    model_path: Path | None, declared: str | None
) -> tuple[str | None, str | None]:
    """Return (declared, observed) checkpoint digests; verify any declaration.

    The observed digest is always computed from the checkpoint actually loaded,
    so a run can never report a declaration it did not honour.
    """

    if model_path is None:
        return declared, None
    observed = sha256_file(model_path)
    if declared and declared != observed:
        raise ValueError(
            "--model-checkpoint-sha256 mismatch: "
            f"declared={declared} observed={observed} path={model_path}"
        )
    return declared, observed


def classify_window(row: dict) -> str:
    src = row.get("src", "")
    ref = row.get("ref", "")
    hypothesis = row.get("tgt", "")
    if src and ref and hypothesis:
        return "aligned"
    if src and ref and not hypothesis:
        return "under_translation_null"
    if not src and not ref and hypothesis:
        return "over_translation_null"
    if src and not ref:
        return "canonical_null_reference"
    # An unrecognised empty-field pattern is recorded as a counted status and
    # scored null instead of aborting the whole run on one malformed window.
    return UNCLASSIFIED_WINDOW


def mean(values: Iterable[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return statistics.fmean(present) if present else None


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def segment_sort_key(row: dict) -> tuple[int, int | str]:
    value = row.get("seg_id", 0)
    try:
        return (0, int(value))
    except (TypeError, ValueError):
        return (1, str(value))


def position_bucket(fraction: float) -> str:
    if fraction < 1 / 3:
        return "beginning"
    if fraction < 2 / 3:
        return "middle"
    return "end"


def assign_source_positions(
    doc_rows: list[dict], source_lines: list[str] | None = None
) -> None:
    """Assign source spans and positions, preferably against original sentences.

    VecAlign joins a multi-sentence source window with spaces.  Those inserted
    spaces are not present in the original BWB character coordinates, so probe
    and position calculations first recover each window's ordered source
    sentence span when the manifest carries the original source lines.
    """

    if source_lines is not None:
        if not isinstance(source_lines, list) or not all(
            isinstance(line, str) for line in source_lines
        ):
            raise ValueError("evaluation_source_lines must be a list of strings")
        sentence_cursor = 0
        char_prefix = [0]
        for line in source_lines:
            char_prefix.append(char_prefix[-1] + len(line))
        for row in doc_rows:
            source = row.get("src", "")
            if not source:
                sentence_start = sentence_cursor
                sentence_end = sentence_cursor
            else:
                target = normalized_exact_text(source)
                sentence_start = sentence_cursor
                sentence_end = None
                for candidate_end in range(sentence_cursor + 1, len(source_lines) + 1):
                    candidates = (
                        " ".join(source_lines[sentence_cursor:candidate_end]),
                        "".join(source_lines[sentence_cursor:candidate_end]),
                    )
                    if any(normalized_exact_text(value) == target for value in candidates):
                        sentence_end = candidate_end
                        break
                if sentence_end is None:
                    raise ValueError(
                        "Cannot map aligned source window to original source lines: "
                        f"cursor={sentence_cursor} src={source[:160]!r}"
                    )
                sentence_cursor = sentence_end
            row["source_sentence_start"] = sentence_start
            row["source_sentence_end"] = sentence_end
            row["source_char_start"] = char_prefix[sentence_start]
            row["source_char_end"] = char_prefix[sentence_end]
        if sentence_cursor != len(source_lines):
            raise ValueError(
                "Aligned source does not cover all original source lines: "
                f"covered={sentence_cursor} expected={len(source_lines)}"
            )
        source_total = char_prefix[-1]
    else:
        source_total = sum(len(row.get("src", "")) for row in doc_rows)

    source_cursor = 0
    for index, row in enumerate(doc_rows):
        if source_lines is None:
            source_chars = len(row.get("src", ""))
            start = source_cursor
            end = start + source_chars
            row["source_char_start"] = start
            row["source_char_end"] = end
        else:
            start = row["source_char_start"]
            end = row["source_char_end"]
            source_chars = end - start
        if source_total:
            fraction = (start + source_chars / 2) / source_total
        else:
            # A pathological all-empty-source document still gets deterministic
            # buckets, while runtime metadata records the normal basis.
            fraction = (index + 0.5) / len(doc_rows)
        row["source_position_fraction"] = fraction
        row["position_bucket"] = position_bucket(fraction)
        source_cursor = end


def normalized_exact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def duplicate_stats(texts: Iterable[str], *, example_limit: int = 20) -> dict:
    normalized = [normalized_exact_text(text) for text in texts]
    normalized = [text for text in normalized if text]
    counts = Counter(normalized)
    duplicate_occurrences = sum(count - 1 for count in counts.values() if count > 1)
    examples = [text for text, count in counts.items() if count > 1]
    return {
        "items": len(normalized),
        "duplicate_occurrences": duplicate_occurrences,
        "duplicate_ratio": ratio(duplicate_occurrences, len(normalized)),
        "duplicate_unique_items": len(examples),
        "duplicate_examples": examples[:example_limit],
        "duplicate_examples_truncated": len(examples) > example_limit,
    }


def row_totals(rows: list[dict]) -> dict[str, int]:
    return {
        "source_chars": sum(len(row.get("src", "")) for row in rows),
        "reference_chars": sum(len(row.get("ref", "")) for row in rows),
        "hypothesis_chars": sum(len(row.get("tgt", "")) for row in rows),
    }


def length_fields(totals: dict[str, int]) -> dict:
    source_chars = totals["source_chars"]
    reference_chars = totals["reference_chars"]
    hypothesis_chars = totals["hypothesis_chars"]
    return {
        **totals,
        "reference_source_char_ratio": ratio(reference_chars, source_chars),
        "hypothesis_source_char_ratio": ratio(hypothesis_chars, source_chars),
        "hypothesis_reference_char_ratio": ratio(hypothesis_chars, reference_chars),
    }


def null_text_statistics(rows: list[dict]) -> dict:
    """Reporting only: character mass in null blocks, never scoring weights."""
    evaluable = [row for row in rows if row['alignment_type'] != 'canonical_null_reference']
    source_chars = sum(len(row.get('src', '')) for row in evaluable)
    hypothesis_chars = sum(len(row.get('tgt', '')) for row in evaluable)
    under_chars = sum(len(row['src']) for row in evaluable
                      if row['alignment_type'] == 'under_translation_null')
    over_chars = sum(len(row['tgt']) for row in evaluable
                     if row['alignment_type'] == 'over_translation_null')
    return {
        'evaluable_source_chars': source_chars,
        'evaluable_hypothesis_chars': hypothesis_chars,
        'under_null_source_chars': under_chars,
        'over_null_hypothesis_chars': over_chars,
        'null_source_char_ratio': ratio(under_chars, source_chars),
        'null_hypothesis_char_ratio': ratio(over_chars, hypothesis_chars),
    }


def summarize_bucket(rows: list[dict]) -> dict:
    evaluable_rows = [row for row in rows if row["alignment_type"] != "canonical_null_reference"]
    null_rows = [row for row in evaluable_rows if row["alignment_type"] != "aligned"]
    under_nulls = sum(
        row["alignment_type"] == "under_translation_null" for row in rows
    )
    over_nulls = sum(
        row["alignment_type"] == "over_translation_null" for row in rows
    )
    totals = row_totals(rows)
    return {
        "windows": len(rows),
        "evaluable_windows": len(evaluable_rows),
        "canonical_null_reference_windows": len(rows) - len(evaluable_rows),
        "comet": mean(row["comet"] for row in evaluable_rows),
        "na_ratio": ratio(len(null_rows), len(evaluable_rows)),
        "under_translation_nulls": under_nulls,
        "over_translation_nulls": over_nulls,
        "under_translation_na_ratio": ratio(under_nulls, len(evaluable_rows)),
        "over_translation_na_ratio": ratio(over_nulls, len(evaluable_rows)),
        **length_fields(totals),
    }


def summarize_probe(doc_rows: list[dict], probe: dict | None) -> dict | None:
    """Summarize a probe selection, recording failure instead of aborting the run.

    A probe that selects no aligned window is reported with
    status="no_windows_selected"; the document and corpus aggregates keep their
    normal basis and the run stays inspectable.
    """

    if not probe:
        return None
    sentence_start = probe.get("source_sentence_start")
    sentence_end = probe.get("source_sentence_end")
    if isinstance(sentence_start, int) and isinstance(sentence_end, int):
        if not 0 <= sentence_start < sentence_end:
            raise ValueError(f"Invalid probe source sentence span: {probe}")
        mapped_total = max(
            (row.get("source_sentence_end", 0) for row in doc_rows), default=0
        )
        if sentence_end > mapped_total:
            raise ValueError(
                "Probe sentence span ends after aligned source: "
                f"end={sentence_end} source_total={mapped_total}"
            )
        selected = []
        boundary_crossings = 0
        for row in doc_rows:
            row_start = row.get("source_sentence_start")
            row_end = row.get("source_sentence_end")
            if not isinstance(row_start, int) or not isinstance(row_end, int):
                raise ValueError("Probe sentence selection requires mapped source windows")
            if row_end > row_start:
                midpoint = (row_start + row_end) / 2
                include = sentence_start <= midpoint < sentence_end
                boundary_crossings += int(
                    row_start < sentence_start < row_end
                    or row_start < sentence_end < row_end
                )
            else:
                include = sentence_start <= row_start < sentence_end or (
                    row_start == sentence_end == mapped_total
                )
            if include:
                selected.append(row)
        return {
            "probe_id": probe.get("probe_id"),
            "source_sha256": probe.get("source_sha256"),
            "status": "selected" if selected else "no_windows_selected",
            "coordinate_basis": "source_sentence_index_over_original_source_lines",
            "source_char_start": probe.get("source_char_start"),
            "source_char_end": probe.get("source_char_end"),
            "source_sentence_start": sentence_start,
            "source_sentence_end": sentence_end,
            "selection_rule": (
                "mapped_source_sentence_window_midpoint; source-empty window at "
                "sentence insertion cursor, including document-end cursor"
            ),
            "boundary_crossing_windows": boundary_crossings,
            **summarize_bucket(selected),
        }

    start = probe.get("source_char_start")
    end = probe.get("source_char_end")
    if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end:
        raise ValueError(f"Invalid probe source span: {probe}")
    # Row spans come from assign_source_positions, so the document total must be
    # the same coordinate as those spans. Summing len(row['src']) would mix the
    # VecAlign space-joined window text into original-source coordinates.
    source_total = max((row.get("source_char_end", 0) for row in doc_rows), default=0)
    if end > source_total:
        raise ValueError(
            f"Probe span ends after aligned source: end={end} source_total={source_total}"
        )

    selected = []
    boundary_crossings = 0
    for row in doc_rows:
        row_start = row["source_char_start"]
        row_end = row["source_char_end"]
        if row_end > row_start:
            midpoint = (row_start + row_end) / 2
            include = start <= midpoint < end
            boundary_crossings += int(
                row_start < start < row_end or row_start < end < row_end
            )
        else:
            # Source-empty over-translation windows are attached to the source
            # cursor at which the aligner inserted them.
            include = start <= row_start < end or row_start == end == source_total
        if include:
            selected.append(row)
    return {
        "probe_id": probe.get("probe_id"),
        "source_sha256": probe.get("source_sha256"),
        "status": "selected" if selected else "no_windows_selected",
        "coordinate_basis": "aligned_source_characters",
        "source_char_start": start,
        "source_char_end": end,
        "selection_rule": (
            "source_window_midpoint; source-empty window at insertion cursor, "
            "including document-end cursor"
        ),
        "boundary_crossing_windows": boundary_crossings,
        **summarize_bucket(selected),
    }


def summarize_case(
    doc_id: str,
    doc_rows: list[dict],
    case_metadata: dict,
    sentence_segmenter=None,
    hypothesis_sentences: list[str] | None = None,
) -> dict:
    evaluable_rows = [row for row in doc_rows if row["alignment_type"] != "canonical_null_reference"]
    null_rows = [row for row in evaluable_rows if row["alignment_type"] != "aligned"]
    aligned_rows = [row for row in doc_rows if row["alignment_type"] == "aligned"]
    position = {
        bucket: summarize_bucket(
            [row for row in doc_rows if row["position_bucket"] == bucket]
        )
        for bucket in POSITION_BUCKETS
    }

    if hypothesis_sentences is None:
        hypothesis_text = "\n".join(
            row.get("tgt", "") for row in doc_rows if row.get("tgt", "")
        )
        hypothesis_sentences = [
            normalized_exact_text(sentence.text)
            for sentence in sentence_segmenter(hypothesis_text).sents
            if sentence.text.strip()
        ]
    sentence_duplicates = duplicate_stats(hypothesis_sentences)
    window_duplicates = duplicate_stats(row.get("tgt", "") for row in doc_rows)
    totals = row_totals(doc_rows)
    benchmark_metadata = case_metadata.get("benchmark_metadata")
    probe = (
        benchmark_metadata.get("probe")
        if isinstance(benchmark_metadata, dict)
        else None
    )

    return {
        "case_id": case_metadata.get("case_id", doc_id),
        "segale_doc_id": doc_id,
        "operation": case_metadata.get("operation", "none"),
        "affected_segments": case_metadata.get("affected_segments", []),
        "benchmark_metadata": benchmark_metadata,
        "metadata": case_metadata.get("metadata", {}),
        "windows": len(doc_rows),
        "evaluable_windows": len(evaluable_rows),
        "canonical_null_reference_windows": len(doc_rows) - len(evaluable_rows),
        "unclassified_windows": sum(
            row["alignment_type"] == UNCLASSIFIED_WINDOW for row in doc_rows
        ),
        "aligned_windows": len(aligned_rows),
        "null_windows": len(null_rows),
        "under_translation_nulls": sum(
            row["alignment_type"] == "under_translation_null" for row in doc_rows
        ),
        "over_translation_nulls": sum(
            row["alignment_type"] == "over_translation_null" for row in doc_rows
        ),
        "na_ratio": ratio(len(null_rows), len(evaluable_rows)),
        "comet": mean(row["comet"] for row in evaluable_rows),
        "comet_aligned_only": mean(row["comet"] for row in aligned_rows),
        "diagnostics": null_text_statistics(doc_rows),
        **length_fields(totals),
        "hypothesis_sentences": sentence_duplicates["items"],
        "exact_duplicate_sentence_occurrences": sentence_duplicates[
            "duplicate_occurrences"
        ],
        "exact_duplicate_sentence_ratio": sentence_duplicates["duplicate_ratio"],
        "exact_duplicate_sentence_unique_items": sentence_duplicates[
            "duplicate_unique_items"
        ],
        "exact_duplicate_sentence_examples": sentence_duplicates["duplicate_examples"],
        "exact_duplicate_sentence_examples_truncated": sentence_duplicates[
            "duplicate_examples_truncated"
        ],
        "nonempty_hypothesis_windows": window_duplicates["items"],
        "exact_duplicate_window_occurrences": window_duplicates["duplicate_occurrences"],
        "exact_duplicate_window_ratio": window_duplicates["duplicate_ratio"],
        "exact_duplicate_window_unique_items": window_duplicates[
            "duplicate_unique_items"
        ],
        "exact_duplicate_window_examples": window_duplicates["duplicate_examples"],
        "exact_duplicate_window_examples_truncated": window_duplicates[
            "duplicate_examples_truncated"
        ],
        "position_buckets": position,
        "probe": summarize_probe(doc_rows, probe),
    }


def aggregate_cases(cases: list[dict], rows: list[dict]) -> dict:
    totals = row_totals(rows)
    evaluable_rows = [row for row in rows if row["alignment_type"] != "canonical_null_reference"]
    null_rows = [row for row in evaluable_rows if row["alignment_type"] != "aligned"]
    aligned_rows = [row for row in rows if row["alignment_type"] == "aligned"]

    macro = {
        "comet": mean(case["comet"] for case in cases),
        "comet_aligned_only": mean(case["comet_aligned_only"] for case in cases),
        "na_ratio": mean(case["na_ratio"] for case in cases),
        "reference_source_char_ratio": mean(
            case["reference_source_char_ratio"] for case in cases
        ),
        "hypothesis_source_char_ratio": mean(
            case["hypothesis_source_char_ratio"] for case in cases
        ),
        "hypothesis_reference_char_ratio": mean(
            case["hypothesis_reference_char_ratio"] for case in cases
        ),
        "exact_duplicate_sentence_ratio": mean(
            case["exact_duplicate_sentence_ratio"] for case in cases
        ),
        "exact_duplicate_window_ratio": mean(
            case["exact_duplicate_window_ratio"] for case in cases
        ),
        "position_buckets": {
            bucket: {
                "comet": mean(
                    case["position_buckets"][bucket]["comet"] for case in cases
                ),
                "na_ratio": mean(
                    case["position_buckets"][bucket]["na_ratio"] for case in cases
                ),
                "hypothesis_reference_char_ratio": mean(
                    case["position_buckets"][bucket][
                        "hypothesis_reference_char_ratio"
                    ]
                    for case in cases
                ),
            }
            for bucket in POSITION_BUCKETS
        },
    }

    sentence_count = sum(case["hypothesis_sentences"] for case in cases)
    sentence_duplicates = sum(
        case["exact_duplicate_sentence_occurrences"] for case in cases
    )
    window_count = sum(case["nonempty_hypothesis_windows"] for case in cases)
    window_duplicates = sum(
        case["exact_duplicate_window_occurrences"] for case in cases
    )
    weighted = {
        "comet": mean(row["comet"] for row in evaluable_rows),
        "comet_aligned_only": mean(row["comet"] for row in aligned_rows),
        "na_ratio": ratio(len(null_rows), len(evaluable_rows)),
        **length_fields(totals),
        "hypothesis_sentences": sentence_count,
        "exact_duplicate_sentence_occurrences": sentence_duplicates,
        "exact_duplicate_sentence_ratio": ratio(sentence_duplicates, sentence_count),
        "nonempty_hypothesis_windows": window_count,
        "exact_duplicate_window_occurrences": window_duplicates,
        "exact_duplicate_window_ratio": ratio(window_duplicates, window_count),
        "position_buckets": {
            bucket: summarize_bucket(
                [row for row in rows if row["position_bucket"] == bucket]
            )
            for bucket in POSITION_BUCKETS
        },
    }
    probe_summaries = [case["probe"] for case in cases if case.get("probe")]
    return {
        "documents": len(cases),
        "windows": len(rows),
        "evaluable_windows": len(evaluable_rows),
        "canonical_null_reference_windows": len(rows) - len(evaluable_rows),
        "unclassified_windows": sum(
            row["alignment_type"] == UNCLASSIFIED_WINDOW for row in rows
        ),
        "aligned_windows": len(aligned_rows),
        "null_windows": len(null_rows),
        "probe": {
            "documents": len(probe_summaries),
            "status_counts": dict(
                sorted(Counter(p.get("status") for p in probe_summaries).items())
            ),
            "selected_documents": sum(
                p.get("status") == "selected" for p in probe_summaries
            ),
        },
        "macro": macro,
        "weighted": weighted,
    }


def package_versions() -> dict[str, str | None]:
    versions = {}
    for package in ("segale", "spacy", "transformers", "unbabel-comet", "numpy"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def metric_statuses(aggregate: dict) -> dict:
    not_requested = {
        "status": "not_requested",
        "availability": "not_run_in_this_experiment",
        "value": None,
    }
    unavailable = {
        "status": "unavailable",
        "availability": "unavailable_in_comet_only_evaluator",
        "value": None,
    }
    return {
        "comet": {
            "status": "ok",
            "value": {
                "macro": aggregate["macro"]["comet"],
                "weighted": aggregate["weighted"]["comet"],
            },
            "null_alignment_score": 0.0,
        },
        "comet_qe": dict(not_requested),
        "metricx": dict(unavailable),
        "metricx_qe": dict(unavailable),
    }


def attach_bindings(summaries: list[dict], manifest_cases: list[dict]) -> None:
    """Carry scored-input fingerprints from the adapter manifest into the summary.

    The summarizer re-binds the caller's current cases/generations to these
    digests before trusting a COMET sidecar, so the fingerprints have to travel
    inside the results packet (protected by the artifact manifest hash) instead
    of relying on the adapter manifest still being reachable at its old path.
    """

    by_case_id = {str(case["case_id"]): case for case in manifest_cases}
    for item in summaries:
        case = by_case_id.get(str(item["case_id"]))
        generation = case.get("generation", {}) if case else {}
        item["binding"] = {
            "generation_output_sha256": generation.get("output_sha256"),
            "source_sha256": case.get("source_sha256") if case else None,
            "reference_sha256": case.get("reference_sha256") if case else None,
        }


def bundle_manifest(comet_dir: Path, manifest_path: Path) -> str:
    """Copy the adapter manifest into the results packet; return its relative path.

    The copy is what the summarizer accepts as a relocatable input when the
    recorded absolute path no longer exists on the machine reading the packet.
    """

    bundled = comet_dir / "inputs" / "manifest.json"
    bundled.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(manifest_path, bundled)
    return "inputs/manifest.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--system-key", required=True)
    parser.add_argument("--model", default="Unbabel/wmt22-comet-da")
    parser.add_argument(
        "--model-checkpoint",
        type=Path,
        help="Local COMET .ckpt; when set, skip model download/resolution",
    )
    parser.add_argument(
        "--model-checkpoint-sha256",
        help="Preverified checkpoint SHA-256 supplied by the runner",
    )
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument(
        "--gpus",
        type=int,
        default=0,
        help="Number of CUDA GPUs passed to COMET (0 keeps CPU behavior)",
    )
    parser.add_argument("--spacy-model", default="es_core_news_sm")
    parser.add_argument(
        "--target-sentences",
        type=Path,
        help="Optional target sentence sidecar emitted by the aligner",
    )
    parser.add_argument("--encoder-model", type=Path, help="Pinned local XLM-R tokenizer/config")
    args = parser.parse_args()

    if args.gpus < 0:
        parser.error("--gpus must be non-negative")
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    if args.model_checkpoint_sha256 and not re.fullmatch(
        r"[a-f0-9]{64}", args.model_checkpoint_sha256
    ):
        parser.error("--model-checkpoint-sha256 must be a lowercase SHA-256")

    total_started = time.perf_counter()

    rows = read_jsonl(args.input_file)
    if not rows:
        raise ValueError(f"No rows in {args.input_file}")

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if "doc_id" not in row:
            raise ValueError(f"Aligned row has no doc_id: {row}")
        row["alignment_type"] = classify_window(row)
        grouped[str(row["doc_id"])].append(row)
    for doc_rows in grouped.values():
        doc_rows.sort(key=segment_sort_key)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    manifest_cases = manifest.get("cases", [])
    manifest_case_ids = [str(case["case_id"]) for case in manifest_cases]
    if len(manifest_case_ids) != len(set(manifest_case_ids)):
        raise ValueError("Manifest contains duplicate case_id values")
    manifest_doc_ids = [str(case.get("segale_doc_id", case["case_id"])) for case in manifest_cases]
    if len(manifest_doc_ids) != len(set(manifest_doc_ids)):
        raise ValueError("Manifest contains duplicate SEGALE document IDs")
    aligned_doc_ids = set(grouped)
    expected_doc_ids = set(manifest_doc_ids)
    if aligned_doc_ids != expected_doc_ids:
        raise ValueError(
            "Aligned/manifest document coverage mismatch: "
            f"missing={sorted(expected_doc_ids - aligned_doc_ids)} "
            f"unexpected={sorted(aligned_doc_ids - expected_doc_ids)}"
        )
    for doc_id, doc_rows in grouped.items():
        segment_ids = []
        for row in doc_rows:
            if "seg_id" not in row:
                raise ValueError(f"Aligned row has no seg_id in document {doc_id}")
            segment_ids.append(str(row["seg_id"]))
        if len(segment_ids) != len(set(segment_ids)):
            raise ValueError(f"Aligned document {doc_id} contains duplicate seg_id values")

    cases_by_id = {
        str(case.get("segale_doc_id", case["case_id"])): case
        for case in manifest_cases
    }
    mapped_source_documents = 0
    for doc_id, doc_rows in grouped.items():
        source_lines = cases_by_id[doc_id].get("evaluation_source_lines")
        mapped_source_documents += isinstance(source_lines, list)
        assign_source_positions(doc_rows, source_lines)
    rows = [row for doc_rows in grouped.values() for row in doc_rows]

    scorable = []
    scorable_rows = []
    for row in rows:
        if row["alignment_type"] == "aligned":
            scorable.append({"src": row["src"], "ref": row["ref"], "mt": row["tgt"]})
            scorable_rows.append(row)
        elif row["alignment_type"] in {"under_translation_null", "over_translation_null"}:
            row["comet"] = 0.0
        else:
            row["comet"] = None

    model_path: Path | None = None
    if args.model_checkpoint:
        # Preserve snapshot symlinks: COMET locates hparams.yaml relative to
        # the checkpoint path rather than its resolved blob-store target.
        model_path = args.model_checkpoint.expanduser().absolute()
        if not model_path.is_file():
            raise FileNotFoundError(f"COMET checkpoint does not exist: {model_path}")
    if scorable:
        if model_path is None:
            model_path = Path(download_model(args.model))
        model_load_started = time.perf_counter()
        # Portable release: use the pinned local encoder config/tokenizer.
        if args.encoder_model:
            from comet.models import RegressionMetric
            model = RegressionMetric.load_from_checkpoint(str(model_path),
                map_location=torch.device("cpu"), strict=False, load_pretrained_weights=False,
                pretrained_model=str(args.encoder_model), local_files_only=True)
        else:
            model = load_from_checkpoint(str(model_path))
        model_load_seconds = time.perf_counter() - model_load_started
        prediction_started = time.perf_counter()
        prediction = model.predict(
            scorable,
            batch_size=args.batch_size,
            gpus=args.gpus,
            num_workers=0,
        )
        prediction_seconds = time.perf_counter() - prediction_started
        scores = prediction.scores if hasattr(prediction, "scores") else prediction["scores"]
        for row, score in zip(scorable_rows, scores, strict=True):
            row["comet"] = float(score)
    else:
        model_load_seconds = 0.0
        prediction_seconds = 0.0

    aggregation_started = time.perf_counter()
    target_sentences_by_doc = None
    if args.target_sentences:
        target_rows = read_jsonl(args.target_sentences)
        target_sentences_by_doc = {}
        for row in target_rows:
            doc_id = str(row.get("doc_id"))
            sentences = row.get("sentences")
            if doc_id in target_sentences_by_doc:
                raise ValueError(f"Duplicate target sentence document: {doc_id}")
            if not isinstance(sentences, list) or not all(
                isinstance(sentence, str) for sentence in sentences
            ):
                raise ValueError(f"Invalid target sentence document: {doc_id}")
            target_sentences_by_doc[doc_id] = sentences
        if set(target_sentences_by_doc) != expected_doc_ids:
            raise ValueError("Target sentence/manifest document coverage mismatch")
        for doc_id, sentences in target_sentences_by_doc.items():
            sidecar_text = normalized_exact_text(" ".join(sentences))
            aligned_text = normalized_exact_text(
                " ".join(
                    row.get("tgt", "")
                    for row in grouped[doc_id]
                    if row.get("tgt", "")
                )
            )
            if sidecar_text != aligned_text:
                raise ValueError(
                    f"Target sentence/aligned text mismatch: {doc_id}"
                )
        sentence_segmenter = None
    else:
        import spacy

        sentence_segmenter = spacy.load(args.spacy_model)
    summaries = [
        summarize_case(
            doc_id,
            doc_rows,
            cases_by_id.get(doc_id, {}),
            sentence_segmenter,
            target_sentences_by_doc.get(doc_id)
            if target_sentences_by_doc is not None
            else None,
        )
        for doc_id, doc_rows in grouped.items()
    ]
    attach_bindings(summaries, manifest_cases)
    manifest_order = {str(case["case_id"]): index for index, case in enumerate(manifest_cases)}
    summaries.sort(
        key=lambda item: (
            manifest_order.get(item["case_id"], len(manifest_order)),
            item["case_id"],
        )
    )
    aggregate = aggregate_cases(summaries, rows)
    aggregation_seconds = time.perf_counter() - aggregation_started

    args.output_dir.mkdir(parents=True, exist_ok=True)
    per_window_path = args.output_dir / "per_window.jsonl"
    with per_window_path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    inputs = {
        "aligned_input": {
            "path": str(args.input_file.absolute()),
            "sha256": sha256_file(args.input_file),
        },
        "manifest": {
            "path": str(args.manifest.absolute()),
            "sha256": sha256_file(args.manifest),
            "bundled": bundle_manifest(args.output_dir, args.manifest),
        },
    }
    if args.target_sentences:
        inputs["target_sentences"] = {
            "path": str(args.target_sentences.absolute()),
            "sha256": sha256_file(args.target_sentences),
        }
    declared_checkpoint_sha256, observed_checkpoint_sha256 = resolve_checkpoint_sha256(
        model_path, args.model_checkpoint_sha256
    )
    unclassified_windows = sum(
        row["alignment_type"] == UNCLASSIFIED_WINDOW for row in rows
    )

    if mapped_source_documents == len(grouped):
        position_basis = (
            "window_midpoint_in_original_source_characters_after_ordered_sentence_mapping"
        )
    elif mapped_source_documents == 0:
        position_basis = "window_midpoint_in_cumulative_aligned_source_characters"
    else:
        position_basis = (
            "per-document: original source characters when manifest sentences are "
            "available, otherwise cumulative aligned source characters"
        )
    runtime = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "packages": package_versions(),
        "comet_model": args.model,
        "comet_checkpoint": str(model_path) if model_path else None,
        "comet_checkpoint_sha256": observed_checkpoint_sha256
        or declared_checkpoint_sha256,
        "comet_checkpoint_sha256_declared": declared_checkpoint_sha256,
        "comet_checkpoint_sha256_observed": observed_checkpoint_sha256,
        "comet_device": "cuda" if args.gpus else "cpu",
        "comet_gpus": args.gpus,
        "comet_batch_size": args.batch_size,
        "sentence_segmenter": args.spacy_model,
        "position_bucket_basis": position_basis,
        "source_sentence_mapped_documents": mapped_source_documents,
        "target_sentences": (
            str(args.target_sentences.absolute()) if args.target_sentences else None
        ),
        "target_sentences_sha256": (
            inputs["target_sentences"]["sha256"] if args.target_sentences else None
        ),
        "target_sentence_source": (
            "alignment_sidecar" if args.target_sentences else "scorer_spacy"
        ),
        "probe_window_basis": (
            "mapped source-sentence-window midpoint over original source lines when "
            "the probe and manifest carry sentence mapping; otherwise character "
            "midpoint over aligned source_char_start/source_char_end coordinates"
        ),
        "probe_selection_status_counts": dict(
            sorted(
                Counter(
                    case["probe"].get("status")
                    for case in summaries
                    if case.get("probe")
                ).items()
            )
        ),
        "unclassified_window_count": unclassified_windows,
        "exact_duplicate_basis": "case-sensitive_text_after_whitespace_normalization",
        "aligned_input": inputs["aligned_input"]["path"],
        "aligned_input_sha256": inputs["aligned_input"]["sha256"],
        "manifest": inputs["manifest"]["path"],
        "manifest_sha256": inputs["manifest"]["sha256"],
        "phase_seconds": {
            "model_load": model_load_seconds,
            "prediction": prediction_seconds,
            "aggregation": aggregation_seconds,
            "total": time.perf_counter() - total_started,
        },
    }
    result = {
        "schema_version": "document-comet-v1",
        "suite_id": args.suite_id,
        "system_key": args.system_key,
        "inputs": inputs,
        "experiment": manifest.get("experiment", {}),
        "runtime": runtime,
        "metrics": metric_statuses(aggregate),
        "aggregate": aggregate,
        "cases": summaries,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # Zero-validation artifacts are what let a stale or partial COMET run pass
    # silently, so a completed run ships the same triple as the chrF2 sidecar.
    artifacts = {
        name: sha256_file(args.output_dir / name)
        for name in ("summary.json", "per_window.jsonl")
    }
    (args.output_dir / "artifact-manifest.json").write_text(
        json.dumps(artifacts, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "COMPLETED.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "scope": "document-comet-sidecar-only",
                "artifact_manifest_sha256": sha256_file(
                    args.output_dir / "artifact-manifest.json"
                ),
                "suite_id": args.suite_id,
                "system_key": args.system_key,
                "aggregate": {
                    "documents": aggregate["documents"],
                    "windows": aggregate["windows"],
                    "macro_comet": aggregate["macro"]["comet"],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"Scored {len(rows)} windows across {len(summaries)} cases; "
        f"COMET macro={aggregate['macro']['comet']:.6f}, "
        f"weighted={aggregate['weighted']['comet']:.6f}"
    )


if __name__ == "__main__":
    main()
