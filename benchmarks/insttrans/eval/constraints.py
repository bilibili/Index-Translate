"""Rule-based checkers for the five hard constraints.

Ported unchanged from the internal scorer so published scores stay comparable.
Each checker returns ``{"is_valid": bool, ...}`` with diagnostic detail.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .syllable import cal_syllable_count

HARD_CONSTRAINT_IDS = frozenset({
    "format_preserve", "layout_break", "term_compliance",
    "syllable_order", "social_preserve",
})
SOFT_CONSTRAINT_IDS = frozenset({
    "style_consistency", "context_disambiguate", "coref_resolution",
    "term_cross_sentence", "academic_format_preserve",
})


# ======================== Constraint text parsing ========================

def parse_term_targets(constraint_lines: list[str]) -> list[str]:
    """Target-side renderings from a `专名/术语对照: X→Y、...` line."""
    target_terms = []
    for line in constraint_lines:
        if "术语对照" not in line and "专名" not in line:
            continue
        match = re.search(r"(?:专名/?)?术语对照[:：]\s*(.*)", line)
        if not match:
            continue
        for pair in re.split(r"[、,，]", match.group(1)):
            if "→" in pair:
                target = pair.split("→", 1)[1].strip()
                if target:
                    target_terms.append(target)
    return target_terms


def parse_layout_features(constraint_lines: list[str]) -> list[str]:
    features = []
    for line in constraint_lines:
        if "布局" not in line and "排版" not in line:
            continue
        if "换行" in line:
            features.append("newlines")
        if "缩进" in line:
            features.append("indent")
        if "表格" in line:
            features.append("table_align")
    return features if features else ["newlines", "indent"]


def parse_social_elements(constraint_lines: list[str]) -> list[str]:
    elements = []
    for line in constraint_lines:
        if "社交元素" not in line:
            continue
        for sep in (":", "："):
            if sep in line:
                raw = line.split(sep, 1)[1].strip()
                elements.extend(p.strip() for p in re.split(r"[、,，]", raw) if p.strip())
                break
    return elements


def collect_soft_constraint_descs(
    constraint_ids: list[str], constraint_lines: list[str]
) -> dict[str, str]:
    """Map each soft constraint id to the prompt line stating it."""
    keyword_map = {
        "style_consistency": ["语体", "风格"],
        "context_disambiguate": ["歧义", "消歧"],
        "coref_resolution": ["指代", "代词"],
        "term_cross_sentence": ["跨句", "全文统一"],
        "academic_format_preserve": ["学术", "LaTeX", "学术格式"],
    }
    soft_descs: dict[str, str] = {}
    for cid in constraint_ids:
        if cid not in SOFT_CONSTRAINT_IDS:
            continue
        for line in constraint_lines:
            if any(kw in line for kw in keyword_map.get(cid, [])):
                soft_descs[cid] = line
                break
        soft_descs.setdefault(cid, cid)
    return soft_descs


# ======================== Rule-based checkers ========================

# Scripts that do not delimit words with spaces: Han, kana, Hangul and Thai.
# A Latin term glued to them ("这是GPT-4的说明", "이것은GPT-4입니다") must still
# count as present; the previous ASCII-only class accepted these neighbours and
# a narrowed class must not regress them.
_NO_SPACE_SCRIPTS = (
    r"\u0e00-\u0e7f"                            # Thai
    r"\u3000-\u303f"                            # CJK symbols and punctuation (々, 〆, 〇, ...)
    r"\u3040-\u309f\u30a0-\u30ff"              # hiragana, katakana
    r"\u31f0-\u31ff\uff66-\uff9f"               # kana phonetic ext, half-width katakana
    r"\u3400-\u4dbf\u4e00-\u9fff"              # Han (Ext-A + URO)
    r"\uf900-\ufaff"                            # CJK compatibility ideographs
    r"\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f"  # Hangul syllables, Jamo, compat jamo
    r"\ua960-\ua97f\ud7b0-\ud7ff"               # Hangul Jamo Ext-A/B
    r"\uffa0-\uffdc"                            # half-width Hangul variants
    r"\U0001aff0-\U0001afff"                    # kana extended-B
    r"\U0001b000-\U0001b16f"                    # kana supplement / extended-A / small kana
    r"\U00020000-\U0002ee5f"                    # supplementary ideographs (Ext-B..F, I)
    r"\U0002f800-\U0002fa1d"                    # compatibility ideographs supplement
    r"\U00030000-\U000323af"                    # supplementary ideographs (Ext-G/H)
)
_NO_SPACE_CHAR = re.compile(f"[{_NO_SPACE_SCRIPTS}]")


def _build_term_pattern(term: str) -> str:
    escaped = re.escape(term)
    # Terms written in a no-space script have no word boundaries to anchor on.
    if _NO_SPACE_CHAR.search(term):
        return escaped
    # \w is Unicode-aware: an ASCII-only boundary class wrongly accepts term
    # substrings inside other scripts' words ("سلام" inside "السلامة", "Öl"
    # inside "Ölüberfluss"). Keep word boundaries for every non-no-space
    # letter, while still accepting no-space neighbours (\w covers them, so
    # the explicit script alternative re-allows them).
    return (
        rf"(?:(?<!\w)|(?<=[{_NO_SPACE_SCRIPTS}])){escaped}"
        rf"(?:(?!\w)|(?=[{_NO_SPACE_SCRIPTS}]))"
    )


def check_glossary(target_text: str, required_terms: list[str]) -> dict[str, Any]:
    missing = [t for t in required_terms
               if not re.search(_build_term_pattern(t), target_text)]
    return {"is_valid": not missing, "missing_terms": missing}


def check_json_preserved(source_text: str, target_text: str) -> dict[str, Any]:
    def extract_keys(text: str) -> tuple[bool, list[str]]:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return False, []
        keys: list[str] = []

        def walk(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current = f"{path}.{key}" if path else key
                    keys.append(current)
                    walk(value, current)
            elif isinstance(obj, list):
                for index, element in enumerate(obj):
                    walk(element, f"{path}[{index}]")

        walk(parsed)
        return True, keys

    src_valid, src_keys = extract_keys(source_text)
    tgt_valid, tgt_keys = extract_keys(target_text)
    if not src_valid:
        return {"is_valid": False, "issues": ["源文不是有效JSON"]}
    if not tgt_valid:
        return {"is_valid": False, "issues": ["译文不是有效JSON"]}

    issues = []
    missing = set(src_keys) - set(tgt_keys)
    extra = set(tgt_keys) - set(src_keys)
    if missing:
        issues.append(f"缺失key: {missing}")
    if extra:
        issues.append(f"多余key: {extra}")
    return {"is_valid": not issues, "issues": issues}


def _extract_visible_text(html: str) -> str:
    # Script/style bodies are not visible text: leaving them in would score the
    # Chinese-residue ratio on markup and code instead of on what a reader sees.
    without_code = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", html,
                          flags=re.IGNORECASE | re.DOTALL)
    return re.sub(r"<[^>]+>", "", without_code).strip()


def _chinese_ratio(text: str) -> float:
    text = re.sub(r"\s+", "", text)
    if not text:
        return 0.0
    return sum(1 for ch in text if "一" <= ch <= "鿿") / len(text)


def check_html_preserved(
    source_text: str, target_text: str,
    src_lang: str | None = None, tgt_lang: str | None = None,
) -> dict[str, Any]:
    tag_pattern = re.compile(r"</?[a-z][a-z0-9]*\b[^>]*>", re.IGNORECASE)
    src_tag_types = [re.sub(r"\s+.*?>", ">", t) for t in tag_pattern.findall(source_text)]
    tgt_tag_types = [re.sub(r"\s+.*?>", ">", t) for t in tag_pattern.findall(target_text)]

    issues = []
    if src_tag_types != tgt_tag_types:
        issues.append(f"标签不一致: 源文{len(src_tag_types)}个, 译文{len(tgt_tag_types)}个")

    if src_lang == "zh" and tgt_lang not in ("ja", "zh"):
        tgt_visible = _extract_visible_text(target_text)
        if tgt_visible and _extract_visible_text(source_text):
            ratio = _chinese_ratio(tgt_visible)
            if ratio > 0.01:
                issues.append(f"译文中残留中文（占比{ratio:.1%}）")

    return {"is_valid": not issues, "issues": issues}


def check_markdown_preserved(source_text: str, target_text: str) -> dict[str, Any]:
    md_patterns = [
        (r"^#{1,6}\s", "标题"), (r"\*\*[^*]+\*\*", "粗体"),
        (r"\*[^*]+\*", "斜体"), (r"`[^`]+`", "行内代码"),
        (r"```[\s\S]*?```", "代码块"), (r"^[-*+]\s", "列表项"),
        (r"^\d+\.\s", "有序列表"), (r"\[.*?\]\(.*?\)", "链接"),
        (r"!\[.*?\]\(.*?\)", "图片"), (r"^>\s", "引用"),
        (r"\|.*\|", "表格"),
    ]
    issues = []
    for pattern, name in md_patterns:
        if re.search(pattern, source_text, re.MULTILINE) and not re.search(
            pattern, target_text, re.MULTILINE
        ):
            issues.append(f"丢失{name}标记")
    return {"is_valid": not issues, "issues": issues}


# Placeholders a translation must carry over. Money such as "$100" is ordinary
# text and must not be scored as a lost placeholder; only named "$var" forms are.
PLACEHOLDER_PATTERNS = (
    r"\{[a-zA-Z_][a-zA-Z0-9_]*\}",
    r"\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\}",
    r"%[dsf]",
    r"%\([a-zA-Z_][a-zA-Z0-9_]*\)[dsf]",
    r"\$[a-zA-Z_][a-zA-Z0-9_]*",
)
PLACEHOLDER_TRIGGER = re.compile("|".join(PLACEHOLDER_PATTERNS))


def check_placeholder_preserved(source_text: str, target_text: str) -> dict[str, Any]:
    issues = []
    for pattern in PLACEHOLDER_PATTERNS:
        missing = set(re.findall(pattern, source_text)) - set(re.findall(pattern, target_text))
        if missing:
            issues.append(f"丢失占位符: {missing}")
    return {"is_valid": not issues, "issues": issues}


def check_format_preserve(
    source_text: str, target_text: str,
    src_lang: str | None = None, tgt_lang: str | None = None,
) -> dict[str, Any]:
    """Dispatch to whichever format checkers the source text actually triggers."""
    results: dict[str, Any] = {}
    issues: list[str] = []
    stripped = source_text.strip()

    if stripped[:1] in ("{", "["):
        try:
            json.loads(stripped)
            is_json = True
        except json.JSONDecodeError:
            is_json = False
        if is_json:
            sub = check_json_preserved(stripped, target_text.strip())
            results["json"] = sub
            if not sub["is_valid"]:
                issues.extend(sub.get("issues", []))

    if re.search(r"</?[a-z][a-z0-9]*\b[^>]*>", source_text, re.IGNORECASE):
        sub = check_html_preserved(source_text, target_text, src_lang=src_lang, tgt_lang=tgt_lang)
        results["html"] = sub
        if not sub["is_valid"]:
            issues.extend(sub.get("issues", []))

    # Trigger on the same shapes check_markdown_preserved looks for: emphasis,
    # ordered lists and tables were missing here, so a source carrying only those
    # forms was passed without any markdown check at all.
    if re.search(
        r"^#{1,6}\s|\*\*[^*]+\*\*|\*[^*]+\*|`|^[-*+]\s|^\d+\.\s|^>\s|"
        r"\[.*?\]\(.*?\)|\|.*\|",
        source_text, re.MULTILINE,
    ):
        sub = check_markdown_preserved(source_text, target_text)
        results["markdown"] = sub
        if not sub["is_valid"]:
            issues.extend(sub.get("issues", []))

    if PLACEHOLDER_TRIGGER.search(source_text):
        sub = check_placeholder_preserved(source_text, target_text)
        results["placeholder"] = sub
        if not sub["is_valid"]:
            issues.extend(sub.get("issues", []))

    return {"is_valid": not issues, "issues": issues, "sub_results": results}


def check_layout_preserved(
    source_text: str, target_text: str, layout_features: list[str] | None = None
) -> dict[str, Any]:
    layout_features = layout_features or ["newlines", "indent"]
    issues = []

    if "newlines" in layout_features:
        src_nl, tgt_nl = source_text.count("\n"), target_text.count("\n")
        if src_nl != tgt_nl:
            issues.append(f"换行数不一致: 源文{src_nl}, 译文{tgt_nl}")

    if "indent" in layout_features:
        # Only the first line carries the block indent; leading spaces on later
        # lines are content, not layout.
        src_first = source_text.split("\n", 1)[0]
        tgt_first = target_text.split("\n", 1)[0]
        src_indent = len(src_first) - len(src_first.lstrip())
        tgt_indent = len(tgt_first) - len(tgt_first.lstrip())
        if (src_indent > 0) != (tgt_indent > 0):
            issues.append("缩进风格不一致")

    if "table_align" in layout_features:
        src_has = any("|" in l and l.count("|") >= 2 for l in source_text.splitlines())
        tgt_has = any("|" in l and l.count("|") >= 2 for l in target_text.splitlines())
        if src_has and not tgt_has:
            issues.append("源文含表格对齐结构但译文丢失")

    return {"is_valid": not issues, "issues": issues}


def check_social_preserve(target_text: str, elements: list[str]) -> dict[str, Any]:
    if not elements:
        return {"is_valid": True, "note": "no elements to check"}
    missing = [e for e in elements if e not in target_text]
    return {"is_valid": not missing, "missing_elements": missing}


def check_syllable_order(
    prediction: str, durations: list[float], tgt_lang: str
) -> dict[str, Any]:
    """Rank-correlate per-sentence duration against translated syllable count.

    Passes at concordance >= 0.9. Pairs with equal durations, and pairs with equal
    syllable counts, are not counted as inversions.
    """
    if not durations or not prediction:
        return {"is_valid": True, "note": "no duration data"}

    try:
        output = json.loads(prediction)
    except (json.JSONDecodeError, TypeError):
        return {"is_valid": False, "note": "output is not valid JSON"}
    if not isinstance(output, dict):
        return {"is_valid": False, "note": "output is not a JSON object"}

    syllables = []
    for i in range(1, len(durations) + 1):
        sentence = output.get(str(i))
        if not isinstance(sentence, str) or not sentence.strip():
            # A missing or empty sentence has no syllable count, and two of them
            # trivially "agree": they used to pass the concordance check.
            return {"is_valid": False,
                    "note": f"译文第{i}句缺失或为空，无法比较音节数"}
        syllables.append(cal_syllable_count(sentence, tgt_lang))
    if len(syllables) < 2:
        return {"is_valid": True, "note": "too few sentences"}

    inversions = total_pairs = 0
    for i in range(len(durations)):
        for j in range(i + 1, len(durations)):
            if durations[i] == durations[j]:
                continue
            total_pairs += 1
            if syllables[i] == syllables[j]:
                continue
            if (durations[i] > durations[j]) != (syllables[i] > syllables[j]):
                inversions += 1

    if total_pairs == 0:
        return {"is_valid": True, "note": "all durations equal"}

    concordance = 1.0 - inversions / total_pairs
    return {
        "is_valid": concordance >= 0.9,
        "concordance": round(concordance, 3),
        "inversions": inversions,
        "total_pairs": total_pairs,
    }


def check_hard_constraints(row: dict[str, Any], prediction: str) -> dict[str, Any]:
    """Run every hard checker this instance is annotated for."""
    if not prediction:
        return {}

    source_text = row["source_text"]
    constraint_lines = row["constraints"]
    results: dict[str, Any] = {}

    for cid in row["constraint_ids"]:
        if cid not in HARD_CONSTRAINT_IDS:
            continue
        if cid == "format_preserve":
            results[cid] = check_format_preserve(
                source_text, prediction,
                src_lang=row["source_lang"], tgt_lang=row["target_lang"],
            )
        elif cid == "layout_break":
            results[cid] = check_layout_preserved(
                source_text, prediction, parse_layout_features(constraint_lines))
        elif cid == "term_compliance":
            terms = parse_term_targets(constraint_lines)
            results[cid] = (check_glossary(prediction, terms) if terms
                            else {"is_valid": True, "note": "no terms to check"})
        elif cid == "syllable_order":
            results[cid] = check_syllable_order(
                prediction, row.get("duration_s", []), row["target_lang"])
        elif cid == "social_preserve":
            results[cid] = check_social_preserve(
                prediction, parse_social_elements(constraint_lines))

    return results
