#!/usr/bin/env python3
"""Adapt frozen document cases and raw generations to the SEGALE interface."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
CASE_METADATA_FIELDS = (
    "schema_version",
    "benchmark_version",
    "track_id",
    "split",
    "corpus_id",
    "work_id",
    "official_directory_group",
    "length_band",
    "target_source_tokens",
    "window_family_id",
)


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--alignment-units", type=Path, required=True)
    parser.add_argument("--generations", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--system-key", required=True)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    if not SAFE_ID.fullmatch(args.suite_id):
        parser.error("--suite-id must be a path-safe identifier")
    if not SAFE_ID.fullmatch(args.system_key):
        parser.error("--system-key must be a path-safe identifier")
    cases = read_jsonl(args.cases)
    units = read_jsonl(args.alignment_units)
    generations = read_jsonl(args.generations)
    if not cases:
        raise ValueError("Cases file is empty")
    cases_by_id = {row["case_id"]: row for row in cases}
    generations_by_id = {row["case_id"]: row for row in generations}
    if len(cases_by_id) != len(cases) or len(generations_by_id) != len(generations):
        raise ValueError("Duplicate case_id")
    unexpected = set(generations_by_id) - set(cases_by_id)
    if unexpected:
        raise ValueError(f"Unexpected generations: {sorted(unexpected)}")
    grouped_units: dict[str, list[dict]] = {case_id: [] for case_id in cases_by_id}
    for unit in units:
        if unit["case_id"] not in grouped_units:
            raise ValueError(f"Alignment unit has unknown case_id: {unit['case_id']}")
        grouped_units[unit["case_id"]].append(unit)
    selected, failures = [], []
    for case in cases:
        case_id = case["case_id"]
        run = generations_by_id.get(case_id)
        if run is None:
            if args.allow_incomplete:
                failures.append({"case_id": case_id, "status": "missing"})
                continue
            raise ValueError(f"Missing generation for {case_id}")
        status = run.get("status", "ok")
        if not isinstance(status, str) or not status:
            raise ValueError(f"Generation {case_id} has an invalid status")
        if status != "ok":
            failures.append({"case_id": case_id, "status": status})
            if args.allow_incomplete:
                continue
            raise ValueError(f"Generation {case_id} has status={status}")
        required = (
            "mt", "finish_reason", "input_tokens", "output_tokens", "cap_hit",
            "model_revision", "generation_config_sha256", "output_sha256"
        )
        missing = [key for key in required if key not in run]
        if missing:
            raise ValueError(f"Generation {case_id} missing {missing}")
        if not isinstance(run["mt"], str) or not run["mt"]:
            raise ValueError(f"Generation {case_id} has empty mt")
        if sha_text(run["mt"]) != run["output_sha256"]:
            raise ValueError(f"Generation {case_id} output hash mismatch")
        case_units = sorted(grouped_units.get(case_id, []), key=lambda row: row["alignment_unit_index"])
        if len(case_units) != case["alignment_unit_count"]:
            raise ValueError(f"Alignment unit count mismatch for {case_id}")
        canonical_source_lines = [row["source"] for row in case_units]
        canonical_reference_lines = [row["reference"] for row in case_units]
        reconstructed_source = "\n".join(canonical_source_lines)
        reconstructed_reference = "\n".join(canonical_reference_lines)
        source_matches = case["source"] in (reconstructed_source, reconstructed_source + "\n")
        reference_matches = case["reference"] in (reconstructed_reference, reconstructed_reference + "\n")
        if not source_matches or not reference_matches:
            raise ValueError(f"Segment reconstruction mismatch for {case_id}")
        # SEGALE aligns MT against source positions. Canonical units without a
        # source position cannot enter VecAlign, but remain unchanged in the
        # release alignment-units file and are explicitly counted here.
        scored_units = [row for row in case_units if row["source"]]
        if not scored_units:
            raise ValueError(f"Generation {case_id} has no non-null source units")
        source_lines = [row["source"] for row in scored_units]
        reference_lines = [row["reference"] for row in scored_units]
        segale_doc_id = "case-" + sha_text(case_id)[:24]
        metadata = case.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError(f"Case {case_id} metadata must be an object")
        metadata = dict(metadata)
        for key in CASE_METADATA_FIELDS:
            if key in case:
                metadata[key] = case[key]
        selected.append(
            (case, run, source_lines, reference_lines, case_units, segale_doc_id, metadata)
        )
    segale_doc_ids = [row[5] for row in selected]
    if len(segale_doc_ids) != len(set(segale_doc_ids)):
        raise ValueError("SEGALE document ID collision")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    reference_rows, system_rows, manifest_cases = [], [], []
    for case, run, source_lines, reference_lines, canonical_units, segale_doc_id, metadata in selected:
        case_id = case["case_id"]
        for index, (source, reference) in enumerate(zip(source_lines, reference_lines, strict=True), 1):
            reference_rows.append({"doc_id": segale_doc_id, "sys_id": "reference", "src": source, "tgt": reference, "seg_id": index})
        system_rows.append({"doc_id": segale_doc_id, "sys_id": args.system_key, "src": case["source"], "tgt": run["mt"], "seg_id": 1})
        manifest_cases.append({
            "case_id": case_id,
            "segale_doc_id": segale_doc_id,
            "metadata": metadata,
            "track_id": case.get("track_id"),
            "split": case.get("split"),
            "work_id": case.get("work_id"),
            "official_directory_group": case.get("official_directory_group"),
            "length_band": case.get("length_band"),
            "window_family_id": case.get("window_family_id"),
            "evaluation_source_lines": source_lines,
            "canonical_alignment_unit_count": len(canonical_units),
            "segale_source_unit_count": len(source_lines),
            "canonical_null_source_count": sum(not row["source"] for row in canonical_units),
            "canonical_null_reference_count": sum(not row["reference"] for row in canonical_units),
            # Content fingerprints of the exact inputs this adapter scored:
            # the summarizer re-binds the caller's current cases/generations to
            # these before trusting a COMET sidecar produced from this manifest.
            "source_sha256": sha_text(case["source"]),
            "reference_sha256": sha_text(case["reference"]),
            "segale_rendering": "non-null-source units in canonical order; canonical units remain in release alignment-units.jsonl",
            "generation": {key: run.get(key) for key in (
                "finish_reason", "input_tokens", "output_tokens", "cap_hit",
                "model_revision", "generation_config_sha256", "output_sha256"
            )},
        })
    write_jsonl(args.output_dir / "reference.jsonl", reference_rows)
    write_jsonl(args.output_dir / "system.jsonl", system_rows)
    manifest = {
        "schema_version": "document-segale-adapter-v1",
        "suite_id": args.suite_id,
        "experiment": {
            "suite_id": args.suite_id,
            "system_key": args.system_key,
            "track_ids": sorted(
                {case["track_id"] for case, *_ in selected if case.get("track_id")}
            ),
            "raw_output_preserved": True,
            "output_cleanup": None,
        },
        "cases": manifest_cases,
        "failures": failures,
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(selected)} cases; omitted {len(failures)} non-success cases")


if __name__ == "__main__":
    main()
