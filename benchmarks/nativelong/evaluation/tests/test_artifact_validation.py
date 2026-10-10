#!/usr/bin/env python3
"""Review fixes for the nativelong evaluation suite.

Each test asserts the *fixed* behavior and, where the defect was behavioural,
also asserts the baseline behaviour so a regression cannot silently return.

Run directly (python tests/test_artifact_validation.py) or under pytest.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVALUATION = HERE.parent
SCRIPTS = EVALUATION / "scripts"
ROOT = EVALUATION.parents[1]
# The revision this review fixed; baseline assertions must not track HEAD.
BASELINE_REV = "9cc5ee7"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(EVALUATION))


def stub_heavy_dependencies() -> None:
    """evaluate_comet imports torch/comet at module scope; the fixes do not."""
    torch = types.ModuleType("torch")
    torch.__version__ = "0.0-stub"
    backends = types.ModuleType("torch.backends")
    mps = types.ModuleType("torch.backends.mps")
    mps.is_available = lambda: False
    backends.mps = mps
    torch.backends = backends
    comet = types.ModuleType("comet")
    comet.download_model = lambda *a, **k: None
    comet.load_from_checkpoint = lambda *a, **k: None
    sys.modules.setdefault("torch", torch)
    sys.modules.setdefault("torch.backends", backends)
    sys.modules.setdefault("torch.backends.mps", mps)
    sys.modules.setdefault("comet", comet)


stub_heavy_dependencies()
import evaluate_comet as ec  # noqa: E402
import prepare_document_segale as prepare  # noqa: E402
import summarize_document_segale as sds  # noqa: E402
import run as runner  # noqa: E402


def baseline_module(relative_path: str, name: str):
    """Load the pre-fix revision of a module straight out of the reviewed baseline."""
    source = subprocess.run(
        ["git", "show", f"{BASELINE_REV}:{relative_path}"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout
    path = EVALUATION / "tests" / f"_baseline_{name}.py"
    path.write_text(source, encoding="utf-8")
    try:
        spec = importlib.util.spec_from_file_location(f"baseline_{name}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        path.unlink()
    return module


# Original source lines are "Aaa"/"Bbb"/"Ccc"/"Ddd" (12 original characters).
# Both windows join two sentences, so summing len(row['src']) gives 14 - the
# mixed basis the review flagged.
MAPPED_ROWS = [
    {"doc_id": "d", "seg_id": 1, "src": "Aaa Bbb", "ref": "r1", "tgt": "t1",
     "alignment_type": "aligned", "source_char_start": 0, "source_char_end": 6,
     "source_sentence_start": 0, "source_sentence_end": 2},
    {"doc_id": "d", "seg_id": 2, "src": "Ccc Ddd", "ref": "r2", "tgt": "t2",
     "alignment_type": "aligned", "source_char_start": 6, "source_char_end": 12,
     "source_sentence_start": 2, "source_sentence_end": 4},
]


def test_unclassified_window_is_counted_not_fatal():
    baseline = baseline_module(
        "benchmarks/nativelong/evaluation/scripts/evaluate_comet.py", "evaluate_comet")
    row = {"doc_id": "d", "seg_id": 1, "src": "", "ref": "", "tgt": ""}
    assert ec.classify_window(row) == "unclassified"
    try:
        baseline.classify_window(row)
    except ValueError:
        pass
    else:  # pragma: no cover - guards the regression
        raise AssertionError("baseline was expected to abort on an unknown pattern")


def test_probe_without_windows_reports_status():
    baseline = baseline_module(
        "benchmarks/nativelong/evaluation/scripts/evaluate_comet.py", "evaluate_comet")
    probe = {"probe_id": "p1", "source_char_start": 0, "source_char_end": 3}
    result = ec.summarize_probe(MAPPED_ROWS, probe)
    assert result["status"] == "no_windows_selected"
    assert result["windows"] == 0 and result["comet"] is None
    try:
        baseline.summarize_probe(MAPPED_ROWS, probe)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("baseline was expected to abort on an empty probe")


def test_probe_character_basis_matches_row_coordinates():
    baseline = baseline_module(
        "benchmarks/nativelong/evaluation/scripts/evaluate_comet.py", "evaluate_comet")
    probe = {"probe_id": "p2", "source_char_start": 11, "source_char_end": 13}
    try:
        ec.summarize_probe(MAPPED_ROWS, probe)
    except ValueError as error:
        # 12 original characters, not the 14 of the space-joined window text.
        assert "source_total=12" in str(error), error
    else:  # pragma: no cover
        raise AssertionError("probe span beyond the original source must be rejected")
    try:
        baseline.summarize_probe(MAPPED_ROWS, probe)
    except ValueError as error:
        assert "source_total=14" not in str(error) and "source_total=12" not in str(error), error
    else:  # pragma: no cover
        raise AssertionError("baseline accepted the mixed coordinate basis")


def test_checkpoint_sha_is_observed_and_verified(tmp_path: Path):
    checkpoint = tmp_path / "model.ckpt"
    checkpoint.write_bytes(b"checkpoint-bytes")
    observed = hashlib.sha256(b"checkpoint-bytes").hexdigest()
    assert ec.resolve_checkpoint_sha256(checkpoint, None) == (None, observed)
    assert ec.resolve_checkpoint_sha256(checkpoint, observed) == (observed, observed)
    try:
        ec.resolve_checkpoint_sha256(checkpoint, "0" * 64)
    except ValueError as error:
        assert "mismatch" in str(error)
    else:  # pragma: no cover
        raise AssertionError("a wrong declared checkpoint digest must fail the run")


def write_comet_run(directory: Path, summary: dict, *, completed: bool = True) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (directory / "per_window.jsonl").write_text("{}\n", encoding="utf-8")
    artifacts = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                 for name in ("summary.json", "per_window.jsonl")}
    (directory / "artifact-manifest.json").write_text(json.dumps(artifacts), encoding="utf-8")
    if completed:
        (directory / "COMPLETED.json").write_text(json.dumps({
            "status": "completed",
            "artifact_manifest_sha256": hashlib.sha256(
                (directory / "artifact-manifest.json").read_bytes()).hexdigest(),
        }), encoding="utf-8")
    return directory / "summary.json"


def comet_summary(inputs: dict, cases: list[dict]) -> dict:
    return {"schema_version": "document-comet-v1", "suite_id": "s", "system_key": "k",
            "inputs": inputs, "cases": cases}


def test_comet_sidecar_validation(tmp_path: Path):
    baseline = baseline_module(
        "benchmarks/nativelong/evaluation/scripts/summarize_document_segale.py",
        "summarize_document_segale")
    assert not hasattr(baseline, "verify_comet_artifacts")
    source = tmp_path / "aligned.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    inputs = {"aligned_input": {"path": str(source),
                                "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}}
    run_dir = tmp_path / "comet"
    summary_path = write_comet_run(run_dir, comet_summary(inputs, []))
    sds.verify_comet_artifacts(summary_path, "s", "k")
    # Missing completed marker: a partial run must not be consumed.
    (run_dir / "COMPLETED.json").unlink()
    try:
        sds.verify_comet_artifacts(summary_path, "s", "k")
    except ValueError as error:
        assert "not completed" in str(error)
    else:  # pragma: no cover
        raise AssertionError("an incomplete COMET run must be rejected")
    # Tampered artifact.
    write_comet_run(run_dir, comet_summary(inputs, []))
    (run_dir / "summary.json").write_text("{}", encoding="utf-8")
    try:
        sds.verify_comet_artifacts(summary_path, "s", "k")
    except ValueError as error:
        assert "hash mismatch" in str(error)
    else:  # pragma: no cover
        raise AssertionError("a stale COMET artifact must be rejected")


def test_duplicate_comet_case_id_is_rejected(tmp_path: Path):
    source = tmp_path / "aligned.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    inputs = {"aligned_input": {"path": str(source),
                                "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}}
    cases = tmp_path / "cases.jsonl"
    cases.write_text(json.dumps({"case_id": "a", "reference": "r", "metadata": {},
                                 "alignment_unit_count": 0}) + "\n", encoding="utf-8")
    mt = "t"
    generations = tmp_path / "generations.jsonl"
    generations.write_text(json.dumps({
        "case_id": "a", "mt": mt, "status": "ok",
        "output_sha256": hashlib.sha256(mt.encode()).hexdigest()}) + "\n", encoding="utf-8")
    summary_path = write_comet_run(tmp_path / "comet", comet_summary(inputs, [
        {"case_id": "a", "comet": 0.5}, {"case_id": "a", "comet": 0.9}]))
    argv = sys.argv
    sys.argv = ["summarize_document_segale.py", "--cases", str(cases),
                "--generations", str(generations), "--comet-summary", str(summary_path),
                "--output", str(tmp_path / "summary.json"), "--suite-id", "s",
                "--system-key", "k"]
    try:
        sds.main()
    except ValueError as error:
        assert "Duplicate case_id in COMET summary" in str(error), error
    else:  # pragma: no cover
        raise AssertionError("duplicate COMET case_id silently accepted")
    finally:
        sys.argv = argv


def test_empty_selection_comet_run_passes_validation(tmp_path: Path):
    cases = tmp_path / "cases.jsonl"
    cases.write_text("", encoding="utf-8")
    inputs = runner.file_inputs({"cases": cases})
    comet_dir = tmp_path / "comet"
    runner.write_empty_comet_run(comet_dir, inputs)
    sds.verify_comet_artifacts(comet_dir / "summary.json", runner.SUITE_ID, runner.SYSTEM_KEY)


def sha_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_bound_comet_run(tmp_path: Path):
    """A minimal results packet that carries per-case input bindings.

    Scored translation is "T"; cases source/reference are "S"/"R".
    """

    aligned = tmp_path / "aligned.jsonl"
    aligned.write_text("{}\n", encoding="utf-8")
    cases = tmp_path / "cases.jsonl"
    cases.write_text(json.dumps({
        "case_id": "a", "source": "S", "reference": "R",
        "metadata": {}, "alignment_unit_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    generations = tmp_path / "generations.jsonl"
    generations.write_text(json.dumps({
        "case_id": "a", "mt": "T", "status": "ok",
        "output_sha256": sha_hex("T")}, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {
        "schema_version": "document-comet-v1", "suite_id": "s", "system_key": "k",
        "inputs": {"aligned_input": {
            "path": str(aligned),
            "sha256": hashlib.sha256(aligned.read_bytes()).hexdigest()}},
        "cases": [{"case_id": "a", "comet": 0.5, "binding": {
            "generation_output_sha256": sha_hex("T"),
            "source_sha256": sha_hex("S"),
            "reference_sha256": sha_hex("R")}}],
    }
    return write_comet_run(tmp_path / "comet", summary), cases, generations


def run_summarize(cases: Path, generations: Path, comet_summary: Path, output: Path,
                  *extra: str) -> None:
    argv = sys.argv
    sys.argv = ["summarize_document_segale.py", "--cases", str(cases),
                "--generations", str(generations), "--comet-summary", str(comet_summary),
                "--output", str(output), "--suite-id", "s", "--system-key", "k", *extra]
    try:
        sds.main()
    finally:
        sys.argv = argv


def test_comet_binding_matches_only_current_inputs():
    cases = [{"case_id": "a", "source": "S", "reference": "R"}]
    generations = [{"case_id": "a", "mt": "T", "status": "ok"}]
    binding = {"generation_output_sha256": sha_hex("T"), "source_sha256": sha_hex("S"),
               "reference_sha256": sha_hex("R")}
    sds.verify_comet_inputs({"cases": [{"case_id": "a", "binding": binding}]},
                            cases, generations)  # control: matching inputs pass
    for label, swapped_cases, swapped_generations in (
        ("generations", cases, [{"case_id": "a", "mt": "T2", "status": "ok"}]),
        ("cases", [{"case_id": "a", "source": "S2", "reference": "R"}], generations),
    ):
        try:
            sds.verify_comet_inputs({"cases": [{"case_id": "a", "binding": binding}]},
                                    swapped_cases, swapped_generations)
        except ValueError as error:
            assert "re-score" in str(error), error
        else:  # pragma: no cover
            raise AssertionError(f"edited {label} silently reused old scores")
    try:
        sds.verify_comet_inputs({"cases": [{"case_id": "a"}]}, cases, generations)
    except ValueError as error:
        assert "does not bind" in str(error), error
    else:  # pragma: no cover
        raise AssertionError("an unbound COMET summary must be rejected")


def test_summarize_rejects_stale_generations_end_to_end(tmp_path: Path):
    summary_path, cases, _ = write_bound_comet_run(tmp_path)
    swapped = tmp_path / "generations-swapped.jsonl"
    swapped.write_text(json.dumps({
        "case_id": "a", "mt": "T2", "status": "ok",
        "output_sha256": sha_hex("T2")}, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        run_summarize(cases, swapped, summary_path, tmp_path / "out.json")
    except ValueError as error:
        assert "re-score" in str(error), error
    else:  # pragma: no cover
        raise AssertionError("stale scores were reused with new translations")


def test_relocated_comet_inputs_verify_with_override(tmp_path: Path):
    summary_path, cases, generations = write_bound_comet_run(tmp_path)
    moved = tmp_path / "moved" / "aligned.jsonl"
    moved.parent.mkdir()
    shutil.move(tmp_path / "aligned.jsonl", moved)
    try:
        run_summarize(cases, generations, summary_path, tmp_path / "out.json")
    except ValueError as error:
        assert "is missing" in str(error), error
    else:  # pragma: no cover
        raise AssertionError("a missing recorded input must be rejected")
    run_summarize(cases, generations, summary_path, tmp_path / "out.json",
                  "--comet-input", f"aligned_input={moved}")
    assert (tmp_path / "out.json").is_file()


def test_bundled_comet_input_copy_is_accepted(tmp_path: Path):
    aligned = tmp_path / "aligned.jsonl"
    aligned.write_text("{}\n", encoding="utf-8")
    comet_dir = tmp_path / "comet"
    (comet_dir / "inputs").mkdir(parents=True)
    bundled = comet_dir / "inputs" / "manifest.json"
    bundled.write_bytes(b'{"cases": []}')
    summary = comet_summary({
        "aligned_input": {"path": str(aligned),
                          "sha256": hashlib.sha256(aligned.read_bytes()).hexdigest()},
        "manifest": {"path": str(tmp_path / "gone" / "manifest.json"),
                     "sha256": hashlib.sha256(bundled.read_bytes()).hexdigest(),
                     "bundled": "inputs/manifest.json"},
    }, [])
    summary_path = write_comet_run(comet_dir, summary)
    sds.verify_comet_artifacts(summary_path, "s", "k")  # bundled copy resolves
    escaping = comet_summary({
        "aligned_input": {"path": str(aligned),
                          "sha256": hashlib.sha256(aligned.read_bytes()).hexdigest()},
        "manifest": {"path": str(tmp_path / "gone" / "manifest.json"),
                     "sha256": hashlib.sha256(bundled.read_bytes()).hexdigest(),
                     "bundled": "../manifest.json"},
    }, [])
    escaping_path = write_comet_run(comet_dir, escaping)
    # Create the escape target so the traversal guard is observable: without the
    # ".." check this file would be picked up as a candidate and fail as a hash
    # mismatch instead of the expected "is missing".
    escape_target = tmp_path / "manifest.json"
    escape_target.write_bytes(b'{"cases": ["should not be read"]}')
    try:
        sds.verify_comet_artifacts(escaping_path, "s", "k")
    except ValueError as error:
        assert "is missing" in str(error), error
    else:  # pragma: no cover
        raise AssertionError("a bundled path escaping the packet must be ignored")


def test_bundled_symlink_escaping_the_packet_is_rejected(tmp_path: Path):
    """A packet-local symlink must not let the verifier hash files outside it."""

    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"CANARY")
    comet_dir = tmp_path / "comet"
    (comet_dir / "inputs").mkdir(parents=True)
    link = comet_dir / "inputs" / "in"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):  # pragma: no cover
        return  # platform without symlink support: nothing to observe
    summary = comet_summary({
        "in": {"path": str(tmp_path / "gone" / "in"),
               "sha256": hashlib.sha256(outside.read_bytes()).hexdigest(),
               "bundled": "inputs/in"},
    }, [])
    summary_path = write_comet_run(comet_dir, summary)
    try:
        sds.verify_comet_artifacts(summary_path, "s", "k")
    except ValueError as error:
        assert "is missing" in str(error), error
    else:  # pragma: no cover
        raise AssertionError("a symlink escaping the packet must not be followed")


def test_corrupt_comet_metadata_raises_controlled_errors(tmp_path: Path):
    """Internally consistent forgeries must fail closed, never crash mid-run."""

    source = tmp_path / "aligned.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    inputs = {"aligned_input": {"path": str(source),
                                "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}}
    run_dir = tmp_path / "comet"
    summary_path = write_comet_run(run_dir, comet_summary(inputs, []))
    # A completed marker without its manifest hash: formerly an uncaught KeyError.
    (run_dir / "COMPLETED.json").write_text(
        json.dumps({"status": "completed"}), encoding="utf-8")
    try:
        sds.verify_comet_artifacts(summary_path, "s", "k")
    except ValueError as error:
        assert "artifact manifest hash" in str(error), error
    else:  # pragma: no cover
        raise AssertionError("a completed marker without a hash must be rejected")
    # Malformed cases fields: formerly KeyError/TypeError from main().
    for cases_value, expected in (({}, "cases must be a list"),
                                  (5, "cases must be a list"),
                                  ("cases", "cases must be a list"),
                                  ([{"comet": 0.5}], "case_id")):
        write_comet_run(run_dir, comet_summary(inputs, cases_value))
        try:
            sds.verify_comet_artifacts(summary_path, "s", "k")
        except ValueError as error:
            assert expected in str(error), (cases_value, error)
        else:  # pragma: no cover
            raise AssertionError(f"malformed cases must be rejected: {cases_value!r}")
        # The same packet must fail through main() as a controlled ValueError too.
        cases_file = tmp_path / "cases.jsonl"
        cases_file.write_text("", encoding="utf-8")
        generations_file = tmp_path / "generations.jsonl"
        generations_file.write_text("", encoding="utf-8")
        try:
            run_summarize(cases_file, generations_file, summary_path,
                          tmp_path / "out.json")
        except ValueError as error:
            assert expected in str(error), (cases_value, error)
        else:  # pragma: no cover
            raise AssertionError(f"main() must reject malformed cases: {cases_value!r}")


def test_bundled_symlink_loop_is_a_controlled_error(tmp_path: Path):
    """A self-referencing symlink must fail closed, not raise RuntimeError."""

    comet_dir = tmp_path / "comet"
    (comet_dir / "inputs").mkdir(parents=True)
    loop = comet_dir / "inputs" / "loop"
    try:
        loop.symlink_to(loop)
    except (OSError, NotImplementedError):  # pragma: no cover
        return  # platform without symlink support: nothing to observe
    summary = comet_summary({
        "in": {"path": str(tmp_path / "gone" / "in"),
               "sha256": "0" * 64,
               "bundled": "inputs/loop"},
    }, [])
    summary_path = write_comet_run(comet_dir, summary)
    try:
        sds.verify_comet_artifacts(summary_path, "s", "k")
    except ValueError as error:
        assert "is missing" in str(error), error
    else:  # pragma: no cover
        raise AssertionError("a symlink loop must be rejected as missing, not crash")


def test_non_string_recorded_path_is_a_controlled_error(tmp_path: Path):
    """A forged packet whose recorded path is not a string must not TypeError."""

    for index, bad in enumerate((5, ["x"])):
        run_dir = tmp_path / f"comet-{index}"
        summary_path = write_comet_run(run_dir, comet_summary({
            "in": {"path": bad, "sha256": "0" * 64},
        }, []))
        try:
            sds.verify_comet_artifacts(summary_path, "s", "k")
        except ValueError as error:
            assert "non-string path" in str(error), (bad, error)
        else:  # pragma: no cover
            raise AssertionError(f"a non-string path must be rejected: {bad!r}")


def test_whole_packet_relocation_verifies(tmp_path: Path):
    """Results packet and inputs moved together still verify at the new paths."""

    root = tmp_path / "run-a"
    root.mkdir()
    aligned = root / "aligned.jsonl"
    aligned.write_text("{}\n", encoding="utf-8")
    cases = root / "cases.jsonl"
    cases.write_text(json.dumps({
        "case_id": "a", "source": "S", "reference": "R",
        "metadata": {}, "alignment_unit_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    generations = root / "generations.jsonl"
    generations.write_text(json.dumps({
        "case_id": "a", "mt": "T", "status": "ok",
        "output_sha256": sha_hex("T")}, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest = root / "adapter-manifest.json"
    manifest.write_text(json.dumps({"cases": [{
        "case_id": "a", "generation": {"output_sha256": sha_hex("T")},
        "source_sha256": sha_hex("S"), "reference_sha256": sha_hex("R")}]}),
        encoding="utf-8")
    comet_dir = root / "comet"
    (comet_dir / "inputs").mkdir(parents=True)
    shutil.copyfile(manifest, comet_dir / "inputs" / "manifest.json")
    summary = {
        "schema_version": "document-comet-v1", "suite_id": "s", "system_key": "k",
        "inputs": {
            "aligned_input": {"path": str(aligned),
                              "sha256": hashlib.sha256(aligned.read_bytes()).hexdigest()},
            "manifest": {"path": str(manifest),
                         "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                         "bundled": "inputs/manifest.json"},
        },
        "cases": [{"case_id": "a", "comet": 0.5, "binding": {
            "generation_output_sha256": sha_hex("T"),
            "source_sha256": sha_hex("S"),
            "reference_sha256": sha_hex("R")}}],
    }
    summary_path = write_comet_run(comet_dir, summary)
    moved = tmp_path / "run-b"
    shutil.move(str(root), str(moved))
    run_summarize(moved / "cases.jsonl", moved / "generations.jsonl",
                  moved / "comet" / "summary.json", tmp_path / "out.json",
                  "--comet-input", f"aligned_input={moved / 'aligned.jsonl'}")
    assert (tmp_path / "out.json").is_file()


def test_prepare_manifest_records_input_fingerprints(tmp_path: Path):
    cases = tmp_path / "cases.jsonl"
    cases.write_text(json.dumps({
        "case_id": "a", "source": "S", "reference": "R",
        "alignment_unit_count": 1, "metadata": {}}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    units = tmp_path / "units.jsonl"
    units.write_text(json.dumps({
        "case_id": "a", "alignment_unit_index": 0,
        "source": "S", "reference": "R"}, ensure_ascii=False) + "\n", encoding="utf-8")
    generations = tmp_path / "generations.jsonl"
    generations.write_text(json.dumps({
        "case_id": "a", "mt": "T", "status": "ok", "finish_reason": None,
        "input_tokens": None, "output_tokens": None, "cap_hit": None,
        "model_revision": None, "generation_config_sha256": None,
        "output_sha256": sha_hex("T")}, ensure_ascii=False) + "\n", encoding="utf-8")
    output_dir = tmp_path / "adapter"
    argv = sys.argv
    sys.argv = ["prepare_document_segale.py", "--cases", str(cases),
                "--alignment-units", str(units), "--generations", str(generations),
                "--output-dir", str(output_dir), "--suite-id", "s", "--system-key", "k"]
    try:
        prepare.main()
    finally:
        sys.argv = argv
    record = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))["cases"][0]
    assert record["source_sha256"] == sha_hex("S")
    assert record["reference_sha256"] == sha_hex("R")
    assert record["generation"]["output_sha256"] == sha_hex("T")


def test_evaluate_comet_transcribes_and_bundles_inputs(tmp_path: Path):
    manifest_cases = [{"case_id": "a", "generation": {"output_sha256": "0" * 64},
                       "source_sha256": "1" * 64, "reference_sha256": "2" * 64}]
    summaries = [{"case_id": "a", "comet": 0.5}]
    ec.attach_bindings(summaries, manifest_cases)
    assert summaries[0]["binding"] == {"generation_output_sha256": "0" * 64,
                                       "source_sha256": "1" * 64,
                                       "reference_sha256": "2" * 64}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"cases": []}', encoding="utf-8")
    comet_dir = tmp_path / "comet"
    relative = ec.bundle_manifest(comet_dir, manifest_path)
    assert relative == "inputs/manifest.json"
    assert (comet_dir / relative).read_bytes() == manifest_path.read_bytes()


def test_five_band_macro_exposes_scored_with_comet():
    macro = runner.five_band_macro({"groups": {"length_band": {
        "4k": {"segale_comet": 0.5, "scored_cases": 3, "scored_with_comet_cases": 2, "cases": 4},
        "8k": {"segale_comet": 0.4, "scored_cases": 2, "scored_with_comet_cases": 2, "cases": 2},
        "16k": {"segale_comet": 0.3, "scored_cases": 1, "scored_with_comet_cases": 1, "cases": 1},
        "32k": {"segale_comet": 0.2, "scored_cases": 1, "scored_with_comet_cases": 1, "cases": 1},
        "64k": {"segale_comet": 0.1, "scored_cases": 1, "scored_with_comet_cases": 0, "cases": 1}}}})
    assert macro["coverage"]["4k"] == {"scored": 3, "scored_with_comet": 2, "total": 4}
    assert macro["value"] is not None


def test_empty_selection_branch_no_longer_writes_bare_summary():
    baseline = baseline_module("benchmarks/nativelong/evaluation/run.py", "run")
    assert hasattr(baseline, "five_band_macro")
    assert not hasattr(baseline, "write_empty_comet_run")
    assert not hasattr(baseline, "file_inputs")


if __name__ == "__main__":
    import tempfile

    failures = 0
    for name, function in sorted(globals().items()):
        if not name.startswith("test_") or not callable(function):
            continue
        if "tmp_path" in function.__code__.co_varnames[:function.__code__.co_argcount]:
            with tempfile.TemporaryDirectory() as directory:
                try:
                    function(Path(directory))
                except Exception as error:  # noqa: BLE001
                    failures += 1
                    print(f"FAIL {name}: {type(error).__name__}: {error}")
                else:
                    print(f"PASS {name}")
        else:
            try:
                function()
            except Exception as error:  # noqa: BLE001
                failures += 1
                print(f"FAIL {name}: {type(error).__name__}: {error}")
            else:
                print(f"PASS {name}")
    print(f"{failures} failing test(s)")
    sys.exit(1 if failures else 0)
