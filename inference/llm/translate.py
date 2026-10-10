#!/usr/bin/env python3
"""Translate text with Index-Translate-2B / Index-Translate-9B / Index-Translate-35B
via any OpenAI-compatible server (vLLM, SGLang, ...).

Supports standard translation as well as instruction following with hard and soft constraints:
  - Hard constraints: format preservation (JSON, CSV, markdown, code, placeholders),
    terminology / glossary enforcement.
  - Soft constraints: tone/register (formal, casual, viral social media),
    domain context and word-sense disambiguation.

Usage:
    # Standard translation
    python translate.py "你好，世界" --target en

    # Hard constraint: Terminology / Glossary enforcement
    python translate.py "碳纤维的好处就是它抗裂缝。" --target en \
        --glossary "碳纤维:carbon fiber, 抗裂缝:crack resistance"

    # Hard constraint: Structured data preservation (JSON, CSV, etc.)
    python translate.py '{"title": "用户协议", "version": "1.0.0"}' --target en \
        --instruction "仅翻译键值内容，严格保留合法 JSON 语法格式与键名"

    # Soft constraint: Style and tone adjustment
    python translate.py "今天下午的会议临时取消了，改天我们再碰一下商量。" --target en \
        --instruction "调整为严谨、正式、礼貌的商务公文风格"

    # Soft constraint: Domain context and disambiguation
    python translate.py "The plant is operating at full capacity after the spring upgrade." --target zh \
        --instruction "语境为工业制造与重工厂房领域，准确消歧专有名词"

    # Reading from stdin:
    echo "Hello world" | python translate.py --target zh

Defaults assume a local server:  vllm serve IndexTeam/Index-Translate-9B
Override with --base-url / --model, or env OPENAI_BASE_URL / INDEX_MODEL.
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
from urllib.parse import urlparse


def encode_image_to_data_url(image_path_or_url: str) -> str:
    """Convert local image file or URL into standard OpenAI base64 data URL."""
    image_str = image_path_or_url.strip()
    if image_str.startswith(("http://", "https://", "data:image/")):
        return image_str

    if not os.path.isfile(image_str):
        raise FileNotFoundError(f"Image file not found: {image_str}")

    mime, _ = mimetypes.guess_type(image_str)
    if not mime:
        ext = os.path.splitext(image_str)[1].lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
        }
        mime = mime_map.get(ext, "image/png")

    with open(image_str, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64_data}"


def make_client(base_url: str, api_key: str):
    """OpenAI client; handle proxies properly for local or internal servers."""
    try:
        from openai import OpenAI
        import httpx
    except ImportError:
        sys.stderr.write("Error: missing required packages 'openai' or 'httpx'.\nPlease install via: pip install openai httpx\n")
        sys.exit(1)

    host = urlparse(base_url).hostname or ""
    proxy = os.environ.get("OPENAI_PROXY") or os.environ.get("ALL_PROXY") or os.environ.get("all_proxy")

    default_headers = {"User-Agent": "Index-Translate-Client/1.0"}
    if host in ("127.0.0.1", "localhost", "::1"):
        return OpenAI(base_url=base_url, api_key=api_key, default_headers=default_headers,
                      http_client=httpx.Client(trust_env=False))
    if proxy:
        return OpenAI(base_url=base_url, api_key=api_key, default_headers=default_headers,
                      http_client=httpx.Client(proxy=proxy, trust_env=False))
    return OpenAI(base_url=base_url, api_key=api_key, default_headers=default_headers)


# Language code -> Chinese name, as used by the training-side prompt builder.
# Keys are lowercase: lookups normalize the user-supplied code with .lower().
LANG_NAMES = {
    "en": "英语", "zh": "中文", "de": "德语", "fr": "法语", "es": "西班牙语",
    "ja": "日语", "ko": "韩语", "pt": "葡萄牙语", "ru": "俄语", "ar": "阿拉伯语",
    "it": "意大利语", "nl": "荷兰语", "pl": "波兰语", "ro": "罗马尼亚语",
    "sv": "瑞典语", "tr": "土耳其语", "hi": "印地语", "vi": "越南语",
    "th": "泰语", "id": "印尼语", "ms": "马来语", "fil": "菲律宾语",
    "ukr_cyrl": "乌克兰语", "fas_arab": "波斯语", "ces_latn": "捷克语",
    "ell_grek": "希腊语", "dan_latn": "丹麦语", "hun_latn": "匈牙利语",
    "fin_latn": "芬兰语", "nob_latn": "书面挪威语", "slk_latn": "斯洛伐克语",
    "bul_cyrl": "保加利亚语",
}

DEFAULT_MODEL = "IndexTeam/Index-Translate-9B"


def parse_glossary_terms(glossary_input: str) -> list[str]:
    """Parse glossary input from a JSON file, JSON string, or comma-separated pairs.
    Returns a list of standardized term pairs like ['term1→target1', 'term2→target2']."""
    if not glossary_input:
        return []
    glossary_input = glossary_input.strip()

    # Case 1: Existing JSON file
    if os.path.isfile(glossary_input):
        try:
            with open(glossary_input, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return [f"{k.strip()}→{str(v).strip()}" for k, v in data.items()]
        except Exception as e:
            sys.stderr.write(f"Warning: failed to read glossary file {glossary_input}: {e}\n")

    # Case 2: JSON string format: {"term": "target"}
    if glossary_input.startswith("{") and glossary_input.endswith("}"):
        try:
            data = json.loads(glossary_input)
            if isinstance(data, dict):
                return [f"{k.strip()}→{str(v).strip()}" for k, v in data.items()]
        except Exception:
            pass

    # Case 3: Delimited pairs, e.g. "term:trans, term2:trans2" or "term->trans" / "term→trans"
    pairs = []
    for item in glossary_input.replace("，", ",").split(","):
        item = item.strip()
        if not item:
            continue
        if "->" in item:
            k, v = item.split("->", 1)
            pairs.append(f"{k.strip()}→{v.strip()}")
        elif "→" in item:
            k, v = item.split("→", 1)
            pairs.append(f"{k.strip()}→{v.strip()}")
        elif ":" in item:
            k, v = item.split(":", 1)
            pairs.append(f"{k.strip()}→{v.strip()}")
        elif "：" in item:
            k, v = item.split("：", 1)
            pairs.append(f"{k.strip()}→{v.strip()}")
        else:
            pairs.append(item)
    return pairs


def trans_prompt(
    text: str,
    target_lang: str,
    source_lang: str = "auto",
    hard_constraints: list[str] = None,
    soft_constraints: list[str] = None,
    glossary: str = "",
    instruction: str = "",
    genre: str = "文本",
) -> str:
    """Construct prompt matching the model's canonical instTrans training and benchmark format.
    
    Format:
        请将以下{源语言}{文体}翻译成{目标语言}，并且严格遵循所有约束要求。

        【源文】
        {source_text}

        【约束要求】
        1. 【硬性要求】...
        2. 【注意】...

        只输出译文，不要有任何额外说明。
    """
    tgt_name = LANG_NAMES.get(target_lang.lower(), target_lang)
    has_source = source_lang and source_lang.lower() not in ("auto", "")
    src_name = LANG_NAMES.get(source_lang.lower(), source_lang) if has_source else ""

    constraints = []

    # 1. Collect hard constraints
    if hard_constraints:
        for c in hard_constraints:
            if not c:
                continue
            for line in c.splitlines():
                line = line.strip().lstrip("0123456789. ")
                if not line:
                    continue
                if not line.startswith("【硬性要求】"):
                    line = f"【硬性要求】{line}"
                constraints.append(line)

    # 2. Terminology glossary -> 【硬性要求】专名/术语对照: A→B、C→D
    if glossary:
        terms = parse_glossary_terms(glossary)
        if terms:
            constraints.append(f"【硬性要求】专名/术语对照: {'、'.join(terms)}")

    # 3. Collect soft constraints
    if soft_constraints:
        for c in soft_constraints:
            if not c:
                continue
            for line in c.splitlines():
                line = line.strip().lstrip("0123456789. ")
                if not line:
                    continue
                if not (line.startswith("【注意】") or line.startswith("【软性要求】")):
                    line = f"【注意】{line}"
                constraints.append(line)

    # 4. General instruction (backward compatibility)
    if instruction:
        inst = instruction.strip()
        if inst:
            for line in inst.splitlines():
                line = line.strip().lstrip("0123456789. ")
                if not line:
                    continue
                if line.startswith("【硬性要求】") or line.startswith("【注意】") or line.startswith("【软性要求】"):
                    constraints.append(line)
                else:
                    constraints.append(f"【注意】{line}")

    if constraints:
        # Canonical instTrans formatted prompt
        header_src = f"{src_name}{genre}" if src_name else genre
        header = f"请将以下{header_src}翻译成{tgt_name}，并且严格遵循所有约束要求。"
        req_lines = [f"{i + 1}. {c}" for i, c in enumerate(constraints)]

        # Check if input is a JSON dict and JSON format preservation is requested
        stripped = text.strip()
        is_json = False
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                obj = json.loads(stripped)
                if isinstance(obj, dict):
                    is_json = True
            except Exception:
                pass

        if is_json and any("JSON" in c or "json" in c for c in constraints):
            suffix = "请以相同的 JSON 格式输出翻译结果，key 保持不变，value 为对应译文。只输出 JSON，不要有任何额外说明。"
        else:
            suffix = "只输出译文，不要有任何额外说明。"

        return (
            f"{header}\n\n"
            f"【源文】\n"
            f"{stripped}\n\n"
            f"【约束要求】\n"
            f"{chr(10).join(req_lines)}\n\n"
            f"{suffix}"
        )

    # Plain translation prompt without constraints
    if src_name:
        return f"请将以下{src_name}文本翻译为{tgt_name}，直接输出翻译结果，不要进行任何解释。\n\n{text.strip()}"
    return f"请将以下文本翻译为{tgt_name}，直接输出翻译结果，不要进行任何解释。\n\n{text.strip()}"


def strip_think(text: str) -> str:
    """Safety net: drop a <think>...</think> block if the model emits one."""
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    return text.strip().removeprefix("<think>").strip()


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Translate text with Index-Translate models (with instTrans formatted instruction following)"
    )
    ap.add_argument("text", nargs="?", help="text to translate (stdin if omitted)")
    ap.add_argument("--target", "-t", default="en", help="target language code, e.g. en/zh/ja (default: en)")
    ap.add_argument("--source", "-s", default="auto", help="source language code (default: auto)")
    ap.add_argument("--hard", "-H", action="append", default=[],
                    help="hard constraint(s) (format preservation, placeholder protection, etc.). Can be repeated.")
    ap.add_argument("--soft", "-S", action="append", default=[],
                    help="soft constraint(s) (style/tone, domain context disambiguation, etc.). Can be repeated.")
    ap.add_argument("--glossary", "-g", default="",
                    help="terminology glossary: 'k:v, k2:v2' or JSON file path; formatted as hard terminology constraint")
    ap.add_argument("--genre", "-d", "--domain", default="文本",
                    help="genre or domain of the source text (default: 文本, e.g. 专栏文章 / 学术论文 / 字幕 / 评论 / 结构化数据)")
    ap.add_argument("--instruction", "-i", default="",
                    help="general task instruction or constraint (formatted into instTrans constraints)")
    ap.add_argument("--raw-prompt", action="store_true",
                    help="send input text directly as raw prompt without template wrapping")
    ap.add_argument("--image", "--img", default=None, help="Path or URL to an image for multimodal image translation")
    ap.add_argument("--model", "-m", default=os.environ.get("INDEX_MODEL", DEFAULT_MODEL))
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1"))
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", "EMPTY"))
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--temperature", type=float, default=0.0)
    args = ap.parse_args()

    if args.text is not None:
        text = args.text.strip()
    elif not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    else:
        text = ""

    if not text and not args.image:
        ap.error("empty input text (or provide --image)")

    if args.image:
        try:
            data_url = encode_image_to_data_url(args.image)
        except Exception as e:
            sys.stderr.write(f"Image load error: {e}\n")
            sys.exit(1)

        tgt_name = LANG_NAMES.get(args.target.lower(), args.target)
        has_source = bool(args.source) and args.source.lower() not in ("auto", "")
        src_name = LANG_NAMES.get(args.source.lower(), args.source) if has_source else ""

        base_prompt = (
            f"请将图片中的{src_name}文本翻译为{tgt_name}，直接输出翻译结果，不要进行任何解释。"
            if src_name
            else f"请将图片中的文本翻译为{tgt_name}，直接输出翻译结果，不要进行任何解释。"
        )

        if text or args.hard or args.soft or args.glossary or args.instruction:
            extras = []
            if text:
                extras.append(f"【参考文本/关注内容】\n{text}")
            if args.instruction:
                extras.append(f"【指令要求】{args.instruction}")
            if args.hard:
                for h in args.hard:
                    extras.append(f"【硬性要求】{h}")
            if args.soft:
                for s in args.soft:
                    extras.append(f"【软性要求】{s}")
            if args.glossary:
                terms = parse_glossary_terms(args.glossary)
                if terms:
                    extras.append(f"【专名/术语对照】{'、'.join(terms)}")
            prompt_text = f"{base_prompt}\n\n" + "\n\n".join(extras) + "\n\n只输出翻译结果，不要进行任何解释。"
        else:
            prompt_text = base_prompt

        messages_content = [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
    else:
        if args.raw_prompt:
            prompt_content = text
        else:
            prompt_content = trans_prompt(
                text=text,
                target_lang=args.target,
                source_lang=args.source,
                hard_constraints=args.hard,
                soft_constraints=args.soft,
                glossary=args.glossary,
                instruction=args.instruction,
                genre=args.genre,
            )
        messages_content = prompt_content

    client = make_client(args.base_url, args.api_key)
    resp = client.chat.completions.create(
        model=args.model,
        messages=[{"role": "user", "content": messages_content}],
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    print(strip_think(resp.choices[0].message.content))


if __name__ == "__main__":
    main()
