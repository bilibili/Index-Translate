#!/usr/bin/env python3
"""Run repeated VecAlign trials without restarting Python for every trial."""

from __future__ import annotations

import io
import json
import random
from math import ceil
from pathlib import Path

import numpy as np


def read_embedding_candidates(text_file: Path, embed_file: Path):
    candidates = json.loads(text_file.read_text(encoding="utf-8"))
    if not isinstance(candidates, list) or not all(isinstance(value, str) for value in candidates):
        raise ValueError("embedding candidates must be a string list")
    if not candidates:
        raise ValueError(
            "embedding candidates are empty: the aligner produced no candidate "
            "sentences for this side"
        )
    sent2line = {}
    for index, candidate in enumerate(candidates):
        key = candidate.strip()
        if key in sent2line:
            raise ValueError("multiple embeddings for the same candidate")
        sent2line[key] = index
    embeddings = np.fromfile(embed_file, dtype=np.float32)
    if not embeddings.size or embeddings.size % len(candidates):
        raise ValueError("embedding row count does not match candidates")
    return sent2line, embeddings.reshape(len(candidates), -1)


def load_case(paths: dict[str, Path], max_size: int) -> dict:
    from vecalign import dp_utils

    effective_max_size = max(2, max_size)
    random.seed(42)
    np.random.seed(42)

    src_sent2line, src_line_embeddings = read_embedding_candidates(
        paths["src_overlap"], paths["src_embed"]
    )
    tgt_sent2line, tgt_line_embeddings = read_embedding_candidates(
        paths["tgt_overlap"], paths["tgt_embed"]
    )
    src_lines = json.loads(paths["src"].read_text(encoding="utf-8"))
    tgt_lines = json.loads(paths["tgt"].read_text(encoding="utf-8"))

    vecs0 = dp_utils.make_doc_embedding(
        src_sent2line, src_line_embeddings, src_lines, effective_max_size
    )
    vecs1 = dp_utils.make_doc_embedding(
        tgt_sent2line, tgt_line_embeddings, tgt_lines, effective_max_size
    )
    return {
        "dp_utils": dp_utils,
        "vecs0": vecs0,
        "vecs1": vecs1,
        "alignment_types": dp_utils.make_alignment_types(effective_max_size),
        "width_over2": ceil(effective_max_size / 2.0) + 5,
        # The CLI reseeds before every invocation. Restoring the state after
        # input construction reproduces the random samples used by each trial.
        "python_random_state": random.getstate(),
        "numpy_random_state": np.random.get_state(),
    }


def run_trial(case: dict, del_percentile_frac: float) -> list[str]:
    dp_utils = case["dp_utils"]
    random.setstate(case["python_random_state"])
    np.random.set_state(case["numpy_random_state"])
    stack = dp_utils.vecalign(
        vecs0=case["vecs0"].copy(),
        vecs1=case["vecs1"].copy(),
        final_alignment_types=case["alignment_types"],
        del_percentile_frac=del_percentile_frac,
        width_over2=case["width_over2"],
        max_size_full_dp=300,
        costs_sample_size=20000,
        num_samps_for_norm=100,
    )
    output = io.StringIO()
    dp_utils.print_alignments(
        stack[0]["final_alignments"],
        scores=stack[0]["alignment_scores"],
        ofile=output,
    )
    return output.getvalue().strip().splitlines()
