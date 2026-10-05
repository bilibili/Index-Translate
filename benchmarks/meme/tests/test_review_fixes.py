#!/usr/bin/env python3
"""Regression tests for the 2026-10-05 review fixes in the meme suite.

Run standalone (no pytest needed):

    python benchmarks/meme/tests/test_review_fixes.py

The judge is never called for real: `openai` is replaced by a stub before
`JudgeClient` is constructed, and `evaluate.JudgeClient` is replaced by a
scripted stub for the end-to-end abort test.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
MEME_DIR = TESTS_DIR.parent
BENCHMARKS_DIR = MEME_DIR.parent
for path in (str(MEME_DIR), str(BENCHMARKS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import download_data  # noqa: E402
import evaluate  # noqa: E402
from eval.judge_client import JudgeClient, JudgeRequestError  # noqa: E402
from eval.score_parser import parse_score  # noqa: E402

JUDGE_CLIENT_SOURCE = MEME_DIR / "eval" / "judge_client.py"


def install_fake_openai(contents):
    """Replace the `openai` module with a stub whose completions return `contents`.

    The list is consumed one entry per completion call; the last entry repeats.
    Returns a mutable state dict with the number of calls made.
    """
    module = types.ModuleType("openai")
    state = {"calls": 0, "contents": list(contents)}

    class _Message:
        def __init__(self, content):
            self.content = content

    class _Choice:
        def __init__(self, content):
            self.message = _Message(content)

    class _Response:
        def __init__(self, content):
            self.choices = [_Choice(content)]

    class _Completions:
        def create(self, **kwargs):
            state["calls"] += 1
            index = min(state["calls"] - 1, len(state["contents"]) - 1)
            return _Response(state["contents"][index])

    class OpenAI:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.chat = types.SimpleNamespace(completions=_Completions())

    module.OpenAI = OpenAI
    sys.modules["openai"] = module
    return state


class JudgeClientCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cache_path = Path(self._tmp.name) / "judge_cache.jsonl"
        self._sleep = mock.patch.object(sys.modules["time"], "sleep", lambda *_: None)
        self._sleep.start()
        self.addCleanup(self._sleep.stop)

    def make_client(self, base_url="https://judge.example/v1", max_attempts=3):
        return JudgeClient(
            api_key="test-key",
            base_url=base_url,
            model="test-model",
            prompt_version="v-test",
            cache_path=self.cache_path,
            max_attempts=max_attempts,
        )

    def cached_lines(self):
        if not self.cache_path.is_file():
            return []
        return [line for line in self.cache_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_empty_response_is_retried_and_never_cached(self):
        state = install_fake_openai([""])
        client = self.make_client(max_attempts=3)
        with self.assertRaises(JudgeRequestError) as ctx:
            client.complete("评分请求")
        print(f"[diag] empty-response error={ctx.exception!r} calls={state['calls']}")
        self.assertIn("empty", str(ctx.exception))
        self.assertEqual(state["calls"], 3, "an empty response must consume the retry budget")
        self.assertEqual(self.cached_lines(), [], "empty judge response was written to the cache")
        self.assertEqual(client.cache_entries, 0)

    def test_none_response_is_retried_and_never_cached(self):
        state = install_fake_openai([None])
        client = self.make_client(max_attempts=2)
        with self.assertRaises(JudgeRequestError):
            client.complete("评分请求")
        self.assertEqual(state["calls"], 2)
        self.assertEqual(self.cached_lines(), [])

    def test_non_empty_response_is_cached_and_reused(self):
        state = install_fake_openai(["评分：1"])
        client = self.make_client()
        content, cached = client.complete("评分请求")
        self.assertEqual((content, cached), ("评分：1", False))
        content, cached = client.complete("评分请求")
        self.assertEqual((content, cached), ("评分：1", True))
        self.assertEqual(state["calls"], 1)
        self.assertEqual(len(self.cached_lines()), 1)

    def test_cache_is_scoped_to_the_provider_base_url(self):
        install_fake_openai(["评分：1"])
        self.make_client(base_url="https://a.example/v1").complete("同一提示")
        self.assertEqual(len(self.cached_lines()), 1)

        install_fake_openai(["评分：0"])
        other_provider = self.make_client(base_url="https://b.example/v1")
        content, cached = other_provider.complete("同一提示")
        print(f"[diag] second provider content={content!r} cached={cached}")
        self.assertEqual((content, cached), ("评分：0", False), "cache leaked across providers")

        same_provider = self.make_client(base_url="https://a.example/v1")
        content, cached = same_provider.complete("同一提示")
        self.assertEqual((content, cached), ("评分：1", True))

    def test_no_baseexception_and_no_dead_condition(self):
        source = JUDGE_CLIENT_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("BaseException", source)
        self.assertNotIn("if line_number > 1", source)

    def test_torn_final_cache_line_keeps_earlier_entries(self):
        install_fake_openai(["评分：1"])
        client = self.make_client()
        client.complete("提示一")
        with self.cache_path.open("a", encoding="utf-8") as handle:
            handle.write('{"key": "torn"')
        reloaded = self.make_client()
        self.assertEqual(reloaded.cache_entries, 1)


class ScoreParserCase(unittest.TestCase):
    def test_markdown_emphasis_is_stripped(self):
        parsed = parse_score("**评分：1**")
        print(f"[diag] '**评分：1**' -> {parsed.to_dict()}")
        self.assertEqual((parsed.score, parsed.parse_status), (1.0, "explicit_score_line"))

    def test_alternate_labels_are_accepted(self):
        for response in ("得分：1", "总分: 1", "最终评分：1", "最终得分=1", "Score: 1", "**得分：1**"):
            with self.subTest(response=response):
                parsed = parse_score(response)
                self.assertEqual((parsed.score, parsed.parse_status), (1.0, "explicit_score_line"))

    def test_grid_values_still_parse(self):
        for response, expected in (
            ("评分：0", 0.0),
            ("评分：0.5", 0.5),
            ("评分： 1", 1.0),
            ("0.5", 0.5),
            ("**1**", 1.0),
        ):
            with self.subTest(response=response):
                parsed = parse_score(response)
                self.assertEqual(parsed.score, expected)

    def test_off_grid_score_stays_zero(self):
        for response in ("评分：0.7", "**评分：0.7**", "得分：0.7"):
            with self.subTest(response=response):
                parsed = parse_score(response)
                print(f"[diag] {response!r} -> {parsed.to_dict()}")
                self.assertEqual(parsed.score, 0.0)
                self.assertEqual(parsed.parse_status, "nonstandard_fallback_0")

    def test_unparsed_response_stays_zero(self):
        parsed = parse_score("模型输出被内容过滤器清空")
        self.assertEqual((parsed.score, parsed.parse_status), (0.0, "nonstandard_fallback_0"))


class _ScriptedJudge:
    """Duck-typed JudgeClient: poisons one prompt, is slow for everything else."""

    def __init__(self, *, poison_token="POISON", delay=0.2, response="评分：1"):
        self.poison_token = poison_token
        self.delay = delay
        self.response = response
        self.calls = 0

    def complete(self, prompt):
        self.calls += 1
        if self.poison_token in prompt:
            raise JudgeRequestError("Judge request failed after 6 attempts: empty response")
        time.sleep(self.delay)
        return self.response, False


def write_case_data(directory, count, poison_token="POISON"):
    directory.mkdir(parents=True, exist_ok=True)
    cases = []
    for index in range(count):
        original = f"原文{index}"
        if index == 0:
            original = f"{poison_token} {original}"
        cases.append({
            "sentence_id": f"s{index}",
            "term_id": f"t{index}",
            "definition_id": "d1",
            "text_type": "bullet",
            "original_text": original,
            "term": "梗",
            "definition": "梗的释义",
            "examples": [],
        })
    with (directory / "test.jsonl").open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")
    return cases


def write_predictions(path, cases):
    with path.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps({
                "sentence_id": case["sentence_id"],
                "prediction": f"translation of {case['sentence_id']}",
            }, ensure_ascii=False) + "\n")


class ScriptedResponseJudge:
    """Returns a queued response per call; each response is handed out once."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self._lock = threading.Lock()

    def complete(self, prompt):
        with self._lock:
            index = min(self.calls, len(self.responses) - 1)
            self.calls += 1
        return self.responses[index], False


class ScorePredictionRowCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def _cases(self, count=2):
        return write_case_data(self.tmp / "data", count)

    def test_judge_status_follows_the_parse_result(self):
        cases = self._cases(2)
        contexts = {case["definition_id"]: case for case in cases}
        predictions = {case["sentence_id"]: "translation" for case in cases}

        results, audits, run_state = evaluate.score_predictions(
            cases=cases,
            contexts=contexts,
            predictions=predictions,
            client=ScriptedResponseJudge(["评分：1", "评分：0.7"]),
            max_workers=2,
        )
        statuses = sorted(row["judge_status"] for row in results)
        scores = sorted(row["score"] for row in results)
        print(f"[diag] judge_status={statuses} scores={scores} audits={len(audits)} run_state={run_state}")
        self.assertEqual(statuses, ["success", "unparsed"])
        self.assertEqual(scores, [0.0, 1.0])
        self.assertFalse(run_state["aborted"])
        self.assertEqual(run_state["scored_cases"], 2)
        self.assertEqual(len(audits), 1)


class EmptyPredictionCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_all_empty_predictions_are_rejected(self):
        cases = write_case_data(self.tmp / "data", 2)
        path = self.tmp / "predictions.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for case in cases:
                handle.write(json.dumps({"sentence_id": case["sentence_id"], "prediction": "   "}) + "\n")
        with self.assertRaises(ValueError) as ctx:
            evaluate.load_prediction_map(path, cases)
        print(f"[diag] empty-prediction error={ctx.exception}")
        self.assertIn("no usable predictions", str(ctx.exception))


class AbortOnJudgeFailureCase(unittest.TestCase):
    CASE_COUNT = 40
    MAX_WORKERS = 4
    SLOW_CALL_SECONDS = 0.2

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_first_failure_aborts_the_queue_and_writes_partial_results(self):
        cases = write_case_data(self.tmp / "data", self.CASE_COUNT)
        predictions_path = self.tmp / "predictions.jsonl"
        write_predictions(predictions_path, cases)
        output_dir = self.tmp / "out"
        judge = _ScriptedJudge(delay=self.SLOW_CALL_SECONDS)

        argv = [
            "evaluate.py",
            "--predictions", str(predictions_path),
            "--output-dir", str(output_dir),
            "--data-dir", str(self.tmp / "data"),
            "--limit", str(self.CASE_COUNT),
            "--num-processes", str(self.MAX_WORKERS),
            "--judge-base-url", "https://judge.example/v1",
            "--judge-cache", str(self.tmp / "judge_cache.jsonl"),
        ]
        started = time.perf_counter()
        with mock.patch.object(sys, "argv", argv), mock.patch.object(evaluate, "JudgeClient", lambda **_: judge):
            try:
                exit_code = evaluate.main()
            except Exception as exc:  # pre-fix behaviour: the failure escapes main()
                exit_code = f"raised {type(exc).__name__}: {exc}"
        elapsed = time.perf_counter() - started

        artifacts = sorted(p.name for p in output_dir.glob("*.json")) if output_dir.exists() else []
        payload = {}
        if (output_dir / "eval_results.json").is_file():
            payload = json.loads((output_dir / "eval_results.json").read_text(encoding="utf-8"))
        run_state = payload.get("run_state", {})
        print(
            f"[diag] exit={exit_code!r} elapsed={elapsed:.2f}s judge_calls={judge.calls} "
            f"artifacts={artifacts} run_state={run_state}"
        )

        # 40 cases at 4 workers x 0.2s each would take ~2s if the queue kept running.
        self.assertLess(elapsed, 1.0, "a judge failure must not wait for the queued cases")
        self.assertTrue(payload, "partial results were not written")
        self.assertTrue(run_state.get("aborted"), "partial results are not marked as aborted")
        self.assertEqual(payload.get("summary", {}).get("formal_run"), False)
        self.assertEqual(run_state.get("total_cases"), self.CASE_COUNT)
        self.assertLess(run_state.get("scored_cases", 0), self.CASE_COUNT)
        self.assertIn("summary", payload)
        self.assertTrue((output_dir / "eval_summary.json").is_file())
        self.assertNotEqual(exit_code, 0)


class MirrorFileCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    @staticmethod
    def spec_for(raw: bytes):
        return {"path": "eval/judge_client.py", "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

    def test_crlf_checkout_verifies(self):
        lf = b"line one\nline two\n"
        path = self.tmp / "judge_client.py"
        path.write_bytes(lf.replace(b"\n", b"\r\n"))
        self.assertTrue(download_data.verify_mirror_file(path, self.spec_for(lf)))

    def test_edited_mirror_file_warns(self):
        lf = b"line one\nline two\n"
        path = self.tmp / "judge_client.py"
        path.write_bytes(lf.replace(b"two", b"2wo"))
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            verified = download_data.verify_mirror_file(path, self.spec_for(lf))
        print(f"[diag] edited mirror verified={verified} stderr={stderr.getvalue().strip()}")
        self.assertFalse(verified)
        self.assertIn("differs from the released", stderr.getvalue())

    def test_missing_mirror_file_warns(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            verified = download_data.verify_mirror_file(self.tmp / "absent.py", self.spec_for(b"x\n"))
        self.assertFalse(verified)
        self.assertIn("missing from the checkout", stderr.getvalue())

    def test_data_file_check_stays_byte_exact(self):
        raw = b'{"row": 1}\n'
        path = self.tmp / "test.jsonl"
        path.write_bytes(raw.replace(b"\n", b"\r\n").replace(b"row", b"row"))  # CRLF rewrite
        with self.assertRaises(ValueError):
            download_data.verify_data_file(path, self.spec_for(raw))
        path.write_bytes(raw)
        download_data.verify_data_file(path, self.spec_for(raw))

    def test_repo_mirror_files_are_advisory(self):
        # No network: only the mirror (advisory) path runs against real repository files.
        releases = json.loads((BENCHMARKS_DIR / "releases.json").read_text(encoding="utf-8"))
        meme = releases["meme"]
        specs = {f["path"]: f for f in meme["files"]}
        data_files = set(meme["data_files"])
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            results = {
                p: download_data.verify_mirror_file(MEME_DIR / p, specs[p])
                for p in specs
                if p not in data_files
            }
        print(f"[diag] repo mirror verification={results}")
        self.assertIn("eval/score_parser.py", results)


class EndpointRedactionCase(unittest.TestCase):
    def test_url_components_do_not_expose_credentials(self):
        for url, expected in (
            ("https://user:REVIEW_TOKEN@example.test/v1", "https://example.test"),
            ("https://example.test?token=REVIEW_TOKEN", "https://example.test"),
            ("https://example.test#REVIEW_TOKEN", "https://example.test"),
            ("http://user:REVIEW_TOKEN@[::1]:8080/v1", "http://[::1]:8080"),
            ("https://example.test:REVIEW_TOKEN/v1", "<redacted>"),
        ):
            with self.subTest(url=url):
                self.assertEqual(evaluate.redact_base_url(url), expected)

    def test_published_summary_is_redacted_but_client_receives_original_url(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            cases = write_case_data(directory / "data", 1)
            predictions = directory / "predictions.jsonl"
            write_predictions(predictions, cases)
            endpoint = "https://user:REVIEW_TOKEN@example.test/v1?key=REVIEW_TOKEN"
            client = types.SimpleNamespace(
                complete=lambda prompt: ("评分：1", False), cache_entries=0,
            )
            argv = ["evaluate.py", "--data-dir", str(directory / "data"),
                    "--predictions", str(predictions), "--output-dir", str(directory / "out"),
                    "--limit", "1", "--judge-base-url", endpoint]
            with mock.patch.object(sys, "argv", argv), \
                    mock.patch.object(evaluate, "JudgeClient", return_value=client) as factory, \
                    mock.patch.dict(evaluate.os.environ, {"JUDGE_API_KEY": "test"}), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(evaluate.main(), 0)
            self.assertEqual(factory.call_args.kwargs["base_url"], endpoint)
            for filename in ("eval_summary.json", "eval_results.json"):
                text = (directory / "out" / filename).read_text(encoding="utf-8")
                self.assertNotIn("REVIEW_TOKEN", text)
            summary = json.loads((directory / "out" / "eval_summary.json").read_text())
            self.assertEqual(summary["judge"]["base_url"], "https://example.test")


if __name__ == "__main__":
    unittest.main(verbosity=2)
