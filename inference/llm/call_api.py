#!/usr/bin/env python3
"""Index-Translate Free Public API Invocation Script.

Directly call the free public Index-Translate API on https://index-translate.bilibili.com/v1.

Usage:
    # 1. Quick translation (defaults to 35B model, translating to English)
    python call_api.py "技术赋能创作，让交流跨越语言的界限。"

    # 2. Specify target language and model
    python call_api.py "Hello, world!" -t zh -m Index-Translate-35B-A3B

    # 3. Stream output (SSE)
    python call_api.py "今天天气真好，我们去公园散步吧。" -t ja --stream

    # 4. Instruction following / constrained translation (instTrans)
    python call_api.py '{"title": "用户协议", "version": "1.0.0"}' -t en \
        --instruction "严格保留合法 JSON 语法格式，仅翻译 value 文本"

    # 5. Terminology / glossary constraint
    python call_api.py "碳纤维的好处就是它抗裂缝。" -t en \
        --glossary "碳纤维:carbon fiber, 抗裂缝:crack resistance"

    # 6. Read from stdin
    cat document.txt | python call_api.py -t en

    # 7. Multimodal image translation (all sizes 2B / 9B / 35B supported)
    python call_api.py --image screenshot.png -t zh
    python call_api.py --image photo.jpg -t zh -m Index-Translate-2B    # Lightweight on-device / fast
    python call_api.py --image diagram.png -t en -m Index-Translate-9B   # Workstation / balanced
    python call_api.py --image paper.jpg -t zh -m Index-Translate-35B-A3B # Flagship / complex layouts

    # 8. Start local OpenAI-compatible bridge proxy (e.g. for Immersive Translate / 沉浸式翻译)
    python call_api.py --serve              # binds 127.0.0.1:8080; add --host 0.0.0.0 to expose on LAN
"""

import argparse
import base64
import http.server
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_API_BASE = "https://index-translate.bilibili.com/v1"
DEFAULT_MODEL = "Index-Translate-35B-A3B"


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


# Language code -> Chinese name, as used by translate.py; kept in sync so both entry
# points build byte-identical prompts.
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


def parse_glossary_terms(glossary_input: str) -> list:
    """Parse a glossary given as a JSON file path, an inline JSON string, or delimited pairs.

    Mirrors translate.py::parse_glossary_terms so both entry points accept the same
    inputs and render the same standardized "A→B" term pairs. stdlib only.
    """
    if not glossary_input:
        return []
    glossary_input = glossary_input.strip()

    # Case 1: path of an existing JSON file: {"term": "target"}
    if os.path.isfile(glossary_input):
        try:
            with open(glossary_input, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return [f"{k.strip()}→{str(v).strip()}" for k, v in data.items()]
        except Exception as e:
            sys.stderr.write(f"Warning: failed to read glossary file {glossary_input}: {e}\n")

    # Case 2: inline JSON string: {"term": "target"}
    if glossary_input.startswith("{") and glossary_input.endswith("}"):
        try:
            data = json.loads(glossary_input)
            if isinstance(data, dict):
                return [f"{k.strip()}→{str(v).strip()}" for k, v in data.items()]
        except Exception:
            pass

    # Case 3: delimited pairs — "k:v", "k：v" (full-width colon), "k->v", "k→v",
    # separated by "," or "，" (full-width comma).
    pairs = []
    for item in glossary_input.replace("，", ",").split(","):
        item = item.strip()
        if not item:
            continue
        for sep in ("->", "→", ":", "："):
            if sep in item:
                k, v = item.split(sep, 1)
                pairs.append(f"{k.strip()}→{v.strip()}")
                break
        else:
            pairs.append(item)
    return pairs


def build_prompt(
    text: str,
    target_lang: str,
    source_lang: str = "auto",
    instruction: str = "",
    glossary: str = "",
    genre: str = "文本",
) -> str:
    """Build the canonical Index-Translate instTrans prompt.

    Mirrors translate.py::trans_prompt for the glossary + --instruction usage, so the
    free public API is prompted exactly like a local server. Deliberately stdlib-only:
    this script must run without third-party packages.
    """
    tgt_name = LANG_NAMES.get(target_lang.lower(), target_lang)
    has_source = bool(source_lang) and source_lang.lower() not in ("auto", "")
    src_name = LANG_NAMES.get(source_lang.lower(), source_lang) if has_source else ""

    constraints = []

    # 1. Terminology glossary -> 【硬性要求】专名/术语对照: A→B、C→D
    if glossary:
        terms = parse_glossary_terms(glossary)
        if terms:
            constraints.append(f"【硬性要求】专名/术语对照: {'、'.join(terms)}")

    # 2. Free-form instruction -> 【注意】 unless it already carries a constraint tag
    if instruction:
        for line in instruction.strip().splitlines():
            line = line.strip().lstrip("0123456789. ")
            if not line:
                continue
            if line.startswith(("【硬性要求】", "【注意】", "【软性要求】")):
                constraints.append(line)
            else:
                constraints.append(f"【注意】{line}")

    if constraints:
        header_src = f"{src_name}{genre}" if src_name else genre
        header = f"请将以下{header_src}翻译成{tgt_name}，并且严格遵循所有约束要求。"
        req_lines = [f"{i + 1}. {c}" for i, c in enumerate(constraints)]

        # JSON input + JSON-preservation constraint gets the canonical JSON suffix.
        stripped = text.strip()
        is_json = False
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                is_json = isinstance(json.loads(stripped), dict)
            except Exception:
                is_json = False

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

    if src_name:
        return f"请将以下{src_name}文本翻译为{tgt_name}，直接输出翻译结果，不要进行任何解释。\n\n{text.strip()}"
    return f"请将以下文本翻译为{tgt_name}，直接输出翻译结果，不要进行任何解释。\n\n{text.strip()}"


def strip_think(text: str) -> str:
    """Strip CoT thought blocks if present."""
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    return text.strip().removeprefix("<think>").strip()


def call_completion(
    api_base: str,
    model: str,
    prompt: str,
    max_tokens: int = 1024,
    temperature: float = 0.0,
    stream: bool = False,
):
    url = f"{api_base.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
        # Keep reasoning OFF: the model is trained to emit the translation directly, and
        # with thinking enabled the CoT text can replace the translation in the response.
        # Mirrors translate.py's extra_body and the --serve proxy default.
        "chat_template_kwargs": {"enable_thinking": False},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Index-Translate-Client/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            if stream:
                for line in resp:
                    line = line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data: "):
                        continue
                    body = line[6:]
                    if body == "[DONE]":
                        break
                    try:
                        chunk = json.loads(body)
                    except json.JSONDecodeError:
                        continue
                    # Servers may send chunks without choices (or with an empty list):
                    # guard instead of crashing with IndexError/AttributeError.
                    if not isinstance(chunk, dict):
                        continue
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        sys.stdout.write(content)
                        sys.stdout.flush()
                print()
            else:
                res = json.loads(resp.read().decode("utf-8"))
                content = res["choices"][0]["message"]["content"]
                print(strip_think(content))

    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        sys.stderr.write(f"API Error ({e.code}): {err_msg}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"Request failed: {e}\n")
        sys.exit(1)


def run_proxy_server(port: int = 8080, api_base: str = DEFAULT_API_BASE, host: str = "127.0.0.1"):
    """Run lightweight OpenAI-compatible local proxy server for browser extensions like Immersive Translate.

    Binds loopback only by default: the proxy forwards to a public endpoint without
    authentication, so listening on 0.0.0.0 would expose it to the whole LAN. Pass
    --host 0.0.0.0 explicitly if that is really wanted.
    """

    class ProxyHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            sys.stderr.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {args[0]} {args[1]}\n")

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Access-Control-Max-Age", "86400")
            self.end_headers()

        def do_GET(self):
            if self.path in ("/v1/models", "/models"):
                body = json.dumps({
                    "object": "list",
                    "data": [
                        {"id": "Index-Translate-35B-A3B", "object": "model"},
                        {"id": "Index-Translate-2B", "object": "model"},
                        {"id": "Index-Translate-9B", "object": "model"},
                    ],
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Index-Translate Proxy Ready\n")

        def do_POST(self):
            if not (self.path.endswith("/chat/completions") or self.path.endswith("/completions") or self.path.endswith("/responses")):
                self.send_response(404)
                self.end_headers()
                return

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            # Ensure enable_thinking=False is sent by default to prevent CoT reasoning from replacing translation text
            try:
                payload = json.loads(body.decode("utf-8"))
                if "chat_template_kwargs" not in payload or not isinstance(payload.get("chat_template_kwargs"), dict):
                    payload["chat_template_kwargs"] = {}
                if "enable_thinking" not in payload["chat_template_kwargs"]:
                    payload["chat_template_kwargs"]["enable_thinking"] = False
                if "temperature" not in payload or payload.get("temperature") is None:
                    payload["temperature"] = 0.0
                body = json.dumps(payload).encode("utf-8")
            except Exception:
                pass

            # Forward to the same endpoint that was requested: a client posting to
            # /v1/completions must not be silently rewritten to /chat/completions.
            if self.path.endswith("/chat/completions"):
                upstream_path = "/chat/completions"
            elif self.path.endswith("/completions"):
                upstream_path = "/completions"
            elif self.path.endswith("/responses"):
                upstream_path = "/responses"
            else:
                upstream_path = "/chat/completions"
            upstream_url = f"{api_base.rstrip('/')}{upstream_path}"
            req = urllib.request.Request(
                upstream_url,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Index-Translate-Client/1.0",
                },
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    self.send_response(resp.status)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    for k, v in resp.headers.items():
                        if k.lower() in ("content-type", "cache-control"):
                            self.send_header(k, v)
                    self.end_headers()

                    while True:
                        chunk = resp.read(1024)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
            except urllib.error.HTTPError as e:
                err_data = e.read()
                self.send_response(e.code)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(err_data)
            except Exception as e:
                self.send_response(502)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    server = http.server.ThreadingHTTPServer((host, port), ProxyHandler)
    # 0.0.0.0 / :: are wildcard binds; show a URL that actually works locally.
    display_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    print("=" * 60)
    print(f"Index-Translate Local Proxy listening on {host}:{port} — http://{display_host}:{port}/v1")
    print(f"Upstream API: {api_base}")
    print()
    print("沉浸式翻译 (Immersive Translate) 配置指南:")
    print("  1. 翻译服务选择: 自定义 (OpenAI 兼容)")
    print(f"  2. 接口地址 (API URL): http://{display_host}:{port}/v1")
    print("  3. 模型 (Model): Index-Translate-35B-A3B")
    print("  4. API Key: 随意填写 (如 index)")
    print("=" * 60, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping proxy...")
        server.server_close()


def main():
    ap = argparse.ArgumentParser(description="Call Index-Translate Free Public API")
    ap.add_argument("text", nargs="?", help="Text to translate (reads stdin if omitted)")
    ap.add_argument("--target", "-t", default="en", help="Target language code, e.g. en/zh/ja (default: en)")
    ap.add_argument("--source", "-s", default="auto", help="Source language code (default: auto)")
    ap.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"Model identifier (default: {DEFAULT_MODEL})")
    ap.add_argument("--instruction", "-i", default="", help="Instruction or formatting constraint")
    ap.add_argument("--glossary", "-g", default="", help="Glossary pairs, e.g. 'term1:target1, term2:target2'")
    ap.add_argument("--api-base", default=DEFAULT_API_BASE, help=f"API Base URL (default: {DEFAULT_API_BASE})")
    ap.add_argument("--image", "--img", default=None, help="Path or URL to an image for multimodal image translation")
    ap.add_argument("--max-tokens", type=int, default=1024, help="Max tokens to generate (default: 1024)")
    ap.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature (default: 0.0 for greedy decoding)")
    ap.add_argument("--stream", action="store_true", help="Stream translation tokens (SSE)")
    ap.add_argument(
        "--serve",
        "--proxy",
        nargs="?",
        const=8080,
        type=int,
        default=None,
        dest="serve_port",
        help="Start local OpenAI-compatible bridge proxy (default port: 8080) for tools like Immersive Translate",
    )
    ap.add_argument(
        "--host",
        default="127.0.0.1",
        help="Interface for --serve to bind (default: 127.0.0.1; 0.0.0.0 exposes it on the LAN)",
    )

    args = ap.parse_args()

    if args.serve_port is not None:
        run_proxy_server(port=args.serve_port, api_base=args.api_base, host=args.host)
        return

    if args.text is not None:
        text = args.text.strip()
    elif not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    else:
        text = ""

    if not text and not args.image:
        ap.error("Empty input text (or provide --image)")

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

        if text or args.instruction or args.glossary:
            extras = []
            if text:
                extras.append(f"【参考文本/关注内容】\n{text}")
            if args.instruction:
                extras.append(f"【指令要求】{args.instruction}")
            if args.glossary:
                terms = parse_glossary_terms(args.glossary)
                if terms:
                    extras.append(f"【术语对照】{'、'.join(terms)}")
            prompt_text = f"{base_prompt}\n\n" + "\n\n".join(extras) + "\n\n只输出翻译结果，不要进行任何解释。"
        else:
            prompt_text = base_prompt

        prompt = [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
    else:
        prompt = build_prompt(
            text=text,
            target_lang=args.target,
            source_lang=args.source,
            instruction=args.instruction,
            glossary=args.glossary,
        )

    call_completion(
        api_base=args.api_base,
        model=args.model,
        prompt=prompt,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        stream=args.stream,
    )


if __name__ == "__main__":
    main()
