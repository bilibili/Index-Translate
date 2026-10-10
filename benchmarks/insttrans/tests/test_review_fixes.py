#!/usr/bin/env python3
"""Regression tests for the 2026-10-05 review fixes in the insttrans suite.

Run standalone (no pytest needed):

    python benchmarks/insttrans/tests/test_review_fixes.py

Prints one CHECK line per case; exits 1 if any expectation fails.
No Judge or network calls: the judge client is exercised with stubs.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent          # tests/
INSTTRANS_DIR = HERE.parent                      # benchmarks/insttrans/
sys.path.insert(0, str(INSTTRANS_DIR))

import eval.syllable as syl  # noqa: E402
from eval import judge_client as jc  # noqa: E402
from eval.constraints import (  # noqa: E402
    check_format_preserve,
    check_glossary,
    check_layout_preserved,
    check_placeholder_preserved,
    check_syllable_order,
)
from eval.metrics import aggregate_constraints  # noqa: E402
from eval.syllable import (  # noqa: E402
    _abbreviation_syllable_count,
    cal_syllable_count,
)

FAILURES: list[str] = []
PY = sys.executable


def check(name: str, got, want) -> None:
    ok = got == want
    if not ok:
        FAILURES.append(f"{name}: got {got!r} want {want!r}")
    print(f"CHECK {'ok  ' if ok else 'FAIL'} {name:<44} got={got!r} want={want!r}")


def note(name: str, got) -> None:
    print(f"NOTE  {name:<44} got={got!r}")


def section(title: str) -> None:
    print(f"--- {title}")


section("1 term boundary")
check("glossary cjk-adjacent", check_glossary("这是GPT-4的说明", ["GPT-4"])["is_valid"], True)
check("glossary cjk-period", check_glossary("说明GPT-4。", ["GPT-4"])["is_valid"], True)
check("glossary ascii-control", check_glossary("Use GPT-4.", ["GPT-4"])["is_valid"], True)
check("glossary no-false-positive", check_glossary("这是GPT-4x的说明", ["GPT-4"])["is_valid"], False)
check("glossary cjk-dash", check_glossary("中文GPT-4—说明", ["GPT-4"])["is_valid"], True)
check("glossary arabic substring", check_glossary("السلامة", ["سلام"])["is_valid"], False)
check("glossary arabic standalone", check_glossary("سلام عليكم", ["سلام"])["is_valid"], True)
check("glossary accent substring", check_glossary("Ölüberfluss", ["Öl"])["is_valid"], False)
check("glossary accent standalone", check_glossary("Öl ist teuer", ["Öl"])["is_valid"], True)
check("glossary hangul-adjacent", check_glossary("이것은GPT-4입니다", ["GPT-4"])["is_valid"], True)
check("glossary thai-adjacent", check_glossary("นี่คือGPT-4ครับ", ["GPT-4"])["is_valid"], True)
check("glossary halfwidth-katakana-adjacent", check_glossary("ﾃﾞﾓGPT-4です", ["GPT-4"])["is_valid"], True)
check("glossary ext-b-adjacent", check_glossary("\U00020000GPT-4", ["GPT-4"])["is_valid"], True)
check("glossary iteration-mark-adjacent", check_glossary("々GPT-4", ["GPT-4"])["is_valid"], True)
check("glossary halfwidth-both-sides", check_glossary("ｶﾀGPT-4ｶﾅ", ["GPT-4"])["is_valid"], True)
check("glossary kana-ext-b-adjacent", check_glossary("\U0001AFF0GPT-4", ["GPT-4"])["is_valid"], True)
check("glossary kana-supplement-adjacent", check_glossary("\U0001B000GPT-4", ["GPT-4"])["is_valid"], True)
check("glossary hentaigana-adjacent", check_glossary("\U0001B001GPT-4", ["GPT-4"])["is_valid"], True)
check("glossary halfwidth-hangul-adjacent", check_glossary("\uffa1GPT-4", ["GPT-4"])["is_valid"], True)
check("glossary compat-supplement-adjacent", check_glossary("\U0002F800GPT-4", ["GPT-4"])["is_valid"], True)
check("glossary ext-i-adjacent", check_glossary("\U0002EBF0GPT-4", ["GPT-4"])["is_valid"], True)

section("2 markdown trigger")
check("md ordered-list", check_format_preserve("1. alpha\n2. beta", "甲\n乙")["is_valid"], False)
check("md italic", check_format_preserve("*alpha*", "甲")["is_valid"], False)
check("md table", check_format_preserve("| a | b |", "甲")["is_valid"], False)
check("md plain control", check_format_preserve("alpha beta", "甲 乙")["is_valid"], True)

section("9 placeholders")
check("placeholder currency ok", check_placeholder_preserved("Price $100", "价格100美元")["is_valid"], True)
check("placeholder $var kept", check_placeholder_preserved("Hi $name", "你好 $name")["is_valid"], True)
check("placeholder $var lost", check_placeholder_preserved("Hi $name", "你好")["is_valid"], False)
check("placeholder %(name)s kept", check_placeholder_preserved("%(name)s", "%(name)s")["is_valid"], True)
check("placeholder %(name)s lost", check_placeholder_preserved("%(name)s", "名字")["is_valid"], False)
check("trigger currency no-op",
      check_format_preserve("Price $100", "价格100美元")["is_valid"], True)

section("10 syllable_order")
check("order empty values",
      check_syllable_order('{"1": "", "2": ""}', [1.0, 2.0], "en")["is_valid"], False)
check("order missing keys",
      check_syllable_order('{"9": "a", "10": "b"}', [1.0, 2.0], "en")["is_valid"], False)
check("order positive control",
      check_syllable_order('{"1": "a", "2": "alpha beta gamma"}', [1.0, 3.0], "en")["is_valid"], True)

section("5-8 syllable counters")
check("ordinal 2nd", cal_syllable_count("2nd", "en"), 2)
check("ordinal 22nd", cal_syllable_count("22nd", "en"), 4)
check("ordinal 1st", cal_syllable_count("1st", "en"), 1)
note("caps run FREE NEW ITEMS", cal_syllable_count("FREE NEW ITEMS", "en"))
check("caps run within tolerance", abs(cal_syllable_count("FREE NEW ITEMS", "en") - 4) <= 1, True)
check("caps acronym pair kept", cal_syllable_count("USA UK", "en"), 5)
check("caps acronym tech pair kept", cal_syllable_count("API URL", "en"), 6)
check("caps contraction stays a word", cal_syllable_count("DON'T STOP", "en"), 2)
check("caps contraction apostrophe variant", cal_syllable_count("IT\u2019S FREE", "en"), 2)
check("caps no-lowercase nonword letters", _abbreviation_syllable_count("USA", "en", False), 3)
check("caps no-lowercase word reads as word", cal_syllable_count("FREE NEW ITEMS", "en") < 6, True)
check("single caps acronym kept", cal_syllable_count("USA", "en"), 3)
check("caps acronym flag on", _abbreviation_syllable_count("USA", "en", True), 3)
check("caps acronym flag off", _abbreviation_syllable_count("FREE", "en", False), None)
check("caps contraction single word", cal_syllable_count("DON'T", "en"), 1)
check("caps contraction single word IT'S", cal_syllable_count("IT'S", "en"), 1)
check("caps contraction U+2018 variant", cal_syllable_count("DON\u2018T STOP", "en"), 2)
check("caps contraction fullwidth variant", cal_syllable_count("DON\uff07T STOP", "en"), 2)
check("caps contraction U+02B9 variant", cal_syllable_count("DON\u02b9T STOP", "en"), 2)
check("caps contraction U+05F3 variant", cal_syllable_count("DON\u05f3T STOP", "en"), 2)
_details = syl.cal_syllable_details("DON'T STOP", "en")
check("details breakdown sums to total",
      sum(item["syllables"] for item in _details["syllable_breakdown"]),
      _details["total_syllables"])
check("spanish dict lowercase key", cal_syllable_count("María", "es"), 3)
check("spanish word in text", cal_syllable_count("Hola María", "es"), 5)

_real_num2words = syl.num2words


def _boom(*_args, **_kwargs):
    raise ValueError("no such language")


syl.num2words = _boom
try:
    value = syl._expand_number("123", "de")
    check("num2words double failure", isinstance(value, str), True)
except Exception as exc:  # noqa: BLE001
    check("num2words double failure", f"raised {type(exc).__name__}", "str")
finally:
    syl.num2words = _real_num2words

section("11 metrics by_constraint denominator")
rows = [
    {
        "prediction_status": "present",
        "if_score": 1.0,
        "quality_score": 1.0,
        "constraint_ids": ["format_preserve", "style_consistency"],
        "hard_constraint_results": {"format_preserve": {"is_valid": True}},
        "soft_constraint_results": {"style_consistency": {"score": 1.0}},
    },
    {
        "prediction_status": "missing",
        "if_score": 0.0,
        "quality_score": None,
        "constraint_ids": ["format_preserve", "style_consistency"],
        "hard_constraint_results": {},
        "soft_constraint_results": {},
    },
]
agg = aggregate_constraints(rows)
check("metrics hard total", agg["format_preserve"]["total"], 2)
check("metrics hard pass", agg["format_preserve"]["pass"], 1)
check("metrics hard scored", agg["format_preserve"]["scored"], 1)
check("metrics hard pass_rate", agg["format_preserve"]["pass_rate"], 0.5)
check("metrics soft total", agg["style_consistency"]["total"], 2)
check("metrics soft scored", agg["style_consistency"]["scored"], 1)
check("metrics soft mean", agg["style_consistency"]["mean_score"], 1.0)
check("metrics bool not a score",
      aggregate_constraints([dict(rows[0], soft_constraint_results={
          "style_consistency": {"score": True}})])["style_consistency"]["mean_score"], None)

section("12 cache key")
keys = []
for base in ("https://api.openai.com/v1", "https://other.example/v1"):
    client = jc.JudgeClient.__new__(jc.JudgeClient)
    client.model = "gpt-4o"
    client.prompt_version = "v1"
    client.base_url = base
    client._use_responses = False
    keys.append(client._key("prompt"))
check("cache key depends on base_url", keys[0] != keys[1], True)

section("4 judge cache validation")


def _make_client(tmp: Path, response: str, max_attempts: int = 1):
    client = jc.JudgeClient.__new__(jc.JudgeClient)
    client.model = "gpt-4o"
    client.prompt_version = "v1"
    client.base_url = "https://example/v1"
    client._use_responses = False
    client.max_attempts = max_attempts
    client.timeout = 1.0
    client.cache_path = tmp / "judge_cache.jsonl"
    client.cache_path.parent.mkdir(parents=True, exist_ok=True)
    client._cache = {}
    client._lock = threading.Lock()
    client._complete_via_chat = lambda prompt: response
    return client


good = lambda text: text.strip() in {"0", "0.5", "1"}  # noqa: E731

with tempfile.TemporaryDirectory() as raw:
    tmp = Path(raw)
    client = _make_client(tmp, "")
    raised = False
    try:
        client.complete("p", validator=lambda text: bool(text.strip()))
    except jc.JudgeRequestError:
        raised = True
    check("empty response raises", raised, True)
    check("empty response not cached", client.cache_entries, 0)
    check("empty response no cache file", client.cache_path.is_file(), False)

    client2 = _make_client(tmp, "")
    raised2 = False
    try:
        client2.complete("p", validator=lambda text: bool(text.strip()))
    except jc.JudgeRequestError:
        raised2 = True
    check("empty not served from cache", raised2, True)

    client3 = _make_client(tmp, "1")
    check("valid response cached first call", client3.complete("p", good), ("1", False))
    check("valid response served from cache", client3.complete("p", good), ("1", True))
    client3.clear_cache()
    check("clear_cache empties memory", client3.cache_entries, 0)
    check("clear_cache deletes file", client3.cache_path.is_file(), False)

    client4 = _make_client(tmp, "banana")
    raised4 = False
    try:
        client4.complete("p", good)
    except jc.JudgeRequestError:
        raised4 = True
    check("unparseable response raises", raised4, True)
    check("unparseable not cached", client4.cache_entries, 0)

section("3 evaluate --limit end-to-end")
with tempfile.TemporaryDirectory() as raw:
    tmp = Path(raw)
    data = tmp / "data.jsonl"
    preds = tmp / "preds.jsonl"
    with data.open("w", encoding="utf-8") as handle:
        for index in range(1, 4):
            handle.write(json.dumps({
                "case_id": f"c{index}",
                "source_text": f"alpha {index}",
                "constraints": ["布局: 换行"],
                "constraint_ids": ["layout_break"],
                "source_lang": "en",
                "target_lang": "zh",
                "scenario": "test",
                "domain": "test",
                "duration_s": [],
            }, ensure_ascii=False) + "\n")
    with preds.open("w", encoding="utf-8") as handle:
        for index in range(1, 4):
            handle.write(json.dumps({"case_id": f"c{index}", "prediction": f"译文{index}"},
                                    ensure_ascii=False) + "\n")
    proc = subprocess.run(
        [PY, str(INSTTRANS_DIR / "evaluate.py"), "--predictions", str(preds),
         "--data-file", str(data), "--output-dir", str(tmp / "out"),
         "--limit", "2", "--skip-judge"],
        capture_output=True, text=True, cwd=str(INSTTRANS_DIR),
    )
    check("evaluate --limit exit code", proc.returncode, 0)
    print((proc.stdout + proc.stderr).strip()[:400])
    summary_path = tmp / "out" / "summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        check("evaluate --limit scored rows", summary["config"]["instances_scored"], 2)
        check("evaluate by_constraint total", summary["by_constraint"]["layout_break"]["total"], 2)

section("P3 extras")
check("layout indent first line only",
      check_layout_preserved("line1\n  indented", "line1\nindented", ["indent"])["is_valid"], True)
check("layout indent still detected",
      check_layout_preserved("  line1", "line1", ["indent"])["is_valid"], False)
from eval.constraints import _extract_visible_text  # noqa: E402

check("visible text drops script",
      _extract_visible_text("<p>hi</p><script>var x = 1;</script>"), "hi")

print()
if FAILURES:
    print(f"RESULT FAIL ({len(FAILURES)} expectations unmet)")
    for failure in FAILURES:
        print(f"  - {failure}")
    sys.exit(1)
print("RESULT PASS")
