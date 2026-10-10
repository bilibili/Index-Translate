#!/usr/bin/env python3
"""Run document SEGALE with local scratch and complete-case CPU parallelism."""

from __future__ import annotations

import argparse
import datetime
import json
import multiprocessing
import re
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

import numpy as np
from tqdm import tqdm

import segale_align as base
from segale_search_policy import AlignmentSearchState, select_alignment_result
from vecalign_inprocess import load_case, run_trial


SAFE_DOC_ID = re.compile(r"^case-[a-f0-9]{24}$")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--system-file", required=True)
    parser.add_argument("--ref-file", required=True)
    parser.add_argument("--task-lang", required=True)
    parser.add_argument("--proc-device", choices=("cpu", "cuda"), required=True)
    parser.add_argument("--embedding-model", required=True)
    parser.add_argument("--max-size", type=int, default=8)
    parser.add_argument("--scratch-dir", required=True)
    parser.add_argument("--case-workers", type=int, default=1)
    parser.add_argument(
        "--search-mode", choices=("full-grid", "online-stop"), default="full-grid"
    )
    parser.add_argument("-v", "--verbose", action="count", default=0)
    args = parser.parse_args()
    if args.max_size < 1:
        parser.error("--max-size must be positive")
    if args.case_workers < 1:
        parser.error("--case-workers must be positive")
    return args


def segment_document(doc):
    doc_id = doc["doc_id"]
    if not SAFE_DOC_ID.fullmatch(doc_id):
        raise ValueError(f"unsafe document ID: {doc_id}")
    src_sentences, ref_sentences = base.clean_lists(
        doc["src_list"], doc["ref_list"], doc_id
    )
    segment_started = time.perf_counter()
    mt_sentences = [
        sentence for sentence in base.segment_sentences_by_spacy(doc["tgt"])
        if sentence.strip()
    ]
    return {
        "doc": doc,
        "src_sentences": src_sentences,
        "ref_sentences": ref_sentences,
        "mt_sentences": mt_sentences,
        "target_segmentation_seconds": time.perf_counter() - segment_started,
    }


def write_prepared_inputs(segmented, scratch_folder, tokenizer, model, max_size):
    prepare_started = time.perf_counter()
    doc = segmented["doc"]
    doc_id = doc["doc_id"]
    src_sentences = segmented["src_sentences"]
    ref_sentences = segmented["ref_sentences"]
    mt_sentences = segmented["mt_sentences"]
    if not src_sentences or not mt_sentences:
        raise ValueError(
            f"Document {doc_id} produced empty inputs "
            f"(source_sentences={len(src_sentences)}, target_sentences={len(mt_sentences)}); "
            "embedding concatenation requires at least one row per side"
        )

    src_started = time.perf_counter()
    src_overlap, src_embed = base.generate_overlap_and_embedding(
        src_sentences, model, tokenizer, max_size
    )
    source_embedding_seconds = time.perf_counter() - src_started

    tgt_started = time.perf_counter()
    tgt_overlap, tgt_embed = base.generate_overlap_and_embedding(
        mt_sentences, model, tokenizer, max_size
    )
    target_embedding_seconds = time.perf_counter() - tgt_started

    write_started = time.perf_counter()
    doc_scratch = scratch_folder / doc_id
    doc_scratch.mkdir()
    paths = {
        "src": doc_scratch / "src.json",
        "tgt": doc_scratch / "tgt.json",
        "src_overlap": doc_scratch / "src.overlaps.json",
        "tgt_overlap": doc_scratch / "tgt.overlaps.json",
        "src_embed": doc_scratch / "src.emb",
        "tgt_embed": doc_scratch / "tgt.emb",
    }
    for key, value in (
        ("src", src_sentences),
        ("tgt", mt_sentences),
        ("src_overlap", src_overlap),
        ("tgt_overlap", tgt_overlap),
    ):
        # Canonical units and spaCy sentences can contain embedded newlines.
        # Keep one list item per unit and one embedding row per candidate.
        paths[key].write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    paths["src_embed"].write_bytes(np.concatenate(src_embed, axis=0).tobytes())
    paths["tgt_embed"].write_bytes(np.concatenate(tgt_embed, axis=0).tobytes())
    scratch_write_seconds = time.perf_counter() - write_started

    return {
        "doc": doc,
        "src_sentences": src_sentences,
        "ref_sentences": ref_sentences,
        "mt_sentences": mt_sentences,
        "paths": paths,
        "doc_scratch": doc_scratch,
        "timing": {
            "doc_id": doc_id,
            "target_segmentation_seconds": segmented[
                "target_segmentation_seconds"
            ],
            "source_embedding_seconds": source_embedding_seconds,
            "target_embedding_seconds": target_embedding_seconds,
            "scratch_write_seconds": scratch_write_seconds,
            "prepare_seconds": time.perf_counter() - prepare_started,
            "source_sentence_count": len(src_sentences),
            "target_sentence_count": len(mt_sentences),
            "source_overlap_count": len(src_overlap),
            "target_overlap_count": len(tgt_overlap),
        },
    }


def alignment_from_state(state, doc_id):
    selected = state.selected_result
    if selected is None:
        print(f"doc_id: {doc_id} | no valid alignment found", flush=True)
        return []
    print(
        f"doc_id: {doc_id} | selected_del_percentile_frac: "
        f"{selected['del_percentile_frac']:.3f} | Avg Cost: "
        f"{selected['avg_cost']:.6f} | Zero-Cost Ratio: "
        f"{selected['zero_cost_ratio']:.2%}",
        flush=True,
    )
    return base.parse_alignments(selected["output_lines"])


def run_vecalign_search(
    prepared, save_folder, max_size, search_mode, stop_jump, cost_min, verbose
):
    doc_id = prepared["doc"]["doc_id"]
    paths = prepared["paths"]
    all_results = []
    online_state = (
        AlignmentSearchState(stop_jump, cost_min)
        if search_mode == "online-stop"
        else None
    )
    vecalign_case = load_case(paths, max_size)

    del_percentile_frac = 0.2
    while del_percentile_frac > 0.01:
        output_lines = run_trial(vecalign_case, del_percentile_frac)
        avg_cost, zero_cost_ratio = base.compute_alignment_stats(output_lines)
        trial = {
            "del_percentile_frac": del_percentile_frac,
            "avg_cost": avg_cost,
            "zero_cost_ratio": zero_cost_ratio,
            "output_lines": output_lines,
        }
        all_results.append(trial)
        if verbose >= 1:
            print(
                f"doc_id: {doc_id} | del_percentile_frac: "
                f"{del_percentile_frac:.3f} | Avg Cost: {avg_cost:.6f} | "
                f"Zero-Cost Ratio: {zero_cost_ratio:.2%}",
                flush=True,
            )
        if online_state is not None and online_state.observe(trial):
            print(
                f"doc_id: {doc_id} | stopping exploration at "
                f"{del_percentile_frac:.3f} ({online_state.stop_reason})",
                flush=True,
            )
            break
        del_percentile_frac -= 0.005

    if verbose >= 1:
        aps_folder = save_folder / "spacy_run_vecalign_explore"
        aps_folder.mkdir(exist_ok=True)
        (aps_folder / f"{doc_id}_aps_results.json").write_text(
            json.dumps(all_results, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    state = online_state or select_alignment_result(
        all_results, stop_jump, cost_min
    )
    if online_state is None and state.stop_reason:
        print(
            f"doc_id: {doc_id} | historical selection stopped at "
            f"{state.stop_result['del_percentile_frac']:.3f} ({state.stop_reason})",
            flush=True,
        )
    alignments = alignment_from_state(state, doc_id)
    selected = state.selected_result
    return alignments, {
        "vecalign_trial_count": len(all_results),
        "early_stop_triggered": state.stop_reason is not None,
        "early_stop_reason": state.stop_reason,
        "selected_del_percentile_frac": (
            selected["del_percentile_frac"] if selected is not None else None
        ),
        "selected_average_cost": selected["avg_cost"] if selected is not None else None,
        "selected_zero_cost_ratio": (
            selected["zero_cost_ratio"] if selected is not None else None
        ),
    }


def align_prepared_doc(
    prepared, save_folder, max_size, search_mode, stop_jump, cost_min, verbose
):
    alignment_started = time.perf_counter()
    doc = prepared["doc"]
    doc_id = doc["doc_id"]
    src_sentences = prepared["src_sentences"]
    ref_sentences = prepared["ref_sentences"]
    mt_sentences = prepared["mt_sentences"]
    src_mt_alignments, search_timing = run_vecalign_search(
        prepared, save_folder, max_size, search_mode, stop_jump, cost_min, verbose
    )

    aligned = []
    aligned_qe = []
    for src_indices, mt_indices in src_mt_alignments:
        aligned_src = " ".join(src_sentences[i] for i in src_indices)
        aligned_ref = " ".join(ref_sentences[i] for i in src_indices)
        aligned_mt = " ".join(mt_sentences[i] for i in mt_indices)
        aligned.append((aligned_src, aligned_ref, aligned_mt))
        aligned_qe.append((aligned_src, aligned_mt))
    result = {
        "doc_id": doc_id,
        "sys_id": doc["sys_id"],
        "src": doc["src"],
        "tgt": doc["tgt"],
        "ref": doc["ref"],
        "ref_aligned": aligned,
        "qe_aligned": aligned_qe,
    }

    if verbose >= 2:
        individual_folder = save_folder / "spacy_individual_alignments"
        individual_folder.mkdir(exist_ok=True)
        (individual_folder / f"{doc_id}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    for path in prepared["paths"].values():
        path.unlink()
    prepared["doc_scratch"].rmdir()

    timing = dict(prepared["timing"])
    timing.update(search_timing)
    timing["vecalign_seconds"] = time.perf_counter() - alignment_started
    return result, timing


def main():
    args = parse_args()
    base.set_seed(42)
    base.VERBOSE = args.verbose
    base.SPACY = "spacy"
    base.init_config(args.task_lang)

    save_folder = Path(base.init_save_folder(args.system_file)).resolve()
    scratch_folder = Path(args.scratch_dir).resolve()
    scratch_folder.mkdir(parents=True, exist_ok=False)

    ref_path = Path(args.ref_file)
    alignment_summary_path = ref_path.parent / ref_path.stem / "spacy_alignment_summary.json"
    if not alignment_summary_path.is_file():
        print(
            f"warning: {alignment_summary_path} not found; continuing with default "
            "SEGALE alignment thresholds",
            file=sys.stderr,
        )
    align_paras = base.load_alignment_summary(
        str(ref_path.parent / ref_path.stem)
    )
    base.STOP_JUMP = align_paras["min_jump"]
    base.COST_MAX = align_paras["cost_max"]
    base.COST_MIN = align_paras["cost_min"]
    print(
        f"Alignment execution: workers={args.case_workers} "
        f"search_mode={args.search_mode} scratch={scratch_folder}",
        flush=True,
    )
    print(f"align_paras: {align_paras}", flush=True)

    system = base.merge_system_entries(base.read_jsonl(args.system_file))
    reference = base.merge_ref_entries(base.read_jsonl(args.ref_file))
    documents = base.combine_system_ref(system, reference)
    worker_context = multiprocessing.get_context("fork")
    executor = ProcessPoolExecutor(
        max_workers=args.case_workers, mp_context=worker_context
    )
    try:
        segmentation_started = time.perf_counter()
        segmented_documents = list(
            tqdm(
                executor.map(segment_document, documents, chunksize=1),
                total=len(documents),
                desc="Segmented documents",
            )
        )
        print(
            "SEGALE_SEGMENTATION_COMPLETED "
            f"documents={len(segmented_documents)} workers={args.case_workers} "
            f"wall_seconds={time.perf_counter() - segmentation_started:.3f}",
            flush=True,
        )

        # The process pool has forked before this CUDA model is loaded, so CPU
        # workers never inherit an initialized CUDA context.
        model_load_started = time.perf_counter()
        tokenizer, model = base.load_alternative_model(
            args.proc_device, args.embedding_model
        )
        print(
            "SEGALE_EMBEDDING_MODEL_LOADED "
            f"wall_seconds={time.perf_counter() - model_load_started:.3f}",
            flush=True,
        )

        run_started = time.perf_counter()
        ordered_results = [None] * len(documents)
        ordered_timings = [None] * len(documents)
        pending = {}

        def collect_completed(futures, progress):
            for future in futures:
                index = pending.pop(future)
                result, timing = future.result()
                ordered_results[index] = result
                ordered_timings[index] = timing
                progress.update(1)

        max_pending = args.case_workers * 2
        with tqdm(total=len(documents), desc="Aligned documents") as progress:
            for index, segmented in enumerate(segmented_documents):
                while len(pending) >= max_pending:
                    completed, _ = wait(pending, return_when=FIRST_COMPLETED)
                    collect_completed(completed, progress)
                prepared = write_prepared_inputs(
                    segmented, scratch_folder, tokenizer, model, args.max_size
                )
                future = executor.submit(
                    align_prepared_doc,
                    prepared,
                    save_folder,
                    args.max_size,
                    args.search_mode,
                    base.STOP_JUMP,
                    base.COST_MIN,
                    args.verbose,
                )
                pending[future] = index
            while pending:
                completed, _ = wait(pending, return_when=FIRST_COMPLETED)
                collect_completed(completed, progress)
    finally:
        executor.shutdown(wait=True, cancel_futures=True)

    aligned_file = save_folder / f"aligned_spacy_{Path(args.system_file).stem}.jsonl"
    base.save_align_info(ordered_results, str(aligned_file))
    timing_file = save_folder / "case_timings.jsonl"
    timing_file.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in ordered_timings),
        encoding="utf-8",
    )
    target_sentences_file = save_folder / "target_sentences.jsonl"
    target_sentences_file.write_text(
        "".join(
            json.dumps(
                {
                    "doc_id": segmented["doc"]["doc_id"],
                    "sentences": segmented["mt_sentences"],
                },
                ensure_ascii=False,
            )
            + "\n"
            for segmented in segmented_documents
        ),
        encoding="utf-8",
    )
    scratch_folder.rmdir()

    wall_seconds = time.perf_counter() - run_started
    print(
        "SEGALE_CASE_TIME_TOTALS "
        f"segmentation_seconds={sum(row['target_segmentation_seconds'] for row in ordered_timings):.3f} "
        f"source_embedding_seconds={sum(row['source_embedding_seconds'] for row in ordered_timings):.3f} "
        f"target_embedding_seconds={sum(row['target_embedding_seconds'] for row in ordered_timings):.3f} "
        f"scratch_write_seconds={sum(row['scratch_write_seconds'] for row in ordered_timings):.3f} "
        f"vecalign_seconds={sum(row['vecalign_seconds'] for row in ordered_timings):.3f}",
        flush=True,
    )
    print(
        "SEGALE_CASE_ALIGNMENT_COMPLETED "
        f"documents={len(ordered_results)} workers={args.case_workers} "
        f"search_mode={args.search_mode} "
        f"trials={sum(row['vecalign_trial_count'] for row in ordered_timings)} "
        f"early_stops={sum(row['early_stop_triggered'] for row in ordered_timings)} "
        f"wall_seconds={wall_seconds:.3f} timings={timing_file}",
        flush=True,
    )
    print(
        f"SEGALE_TARGET_SENTENCES_SAVED path={target_sentences_file}", flush=True
    )
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Alignment completed at: {timestamp}.", flush=True)


if __name__ == "__main__":
    main()
