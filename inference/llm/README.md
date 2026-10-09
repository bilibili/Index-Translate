# llm · Text-Translation LLMs (Translate / NativeLong / Homura)

[中文](README_zh.md)

Client scripts, serving presets, fixed prompt templates, and captured cases
for the Translate, NativeLong, and Homura families. All of them speak the OpenAI chat
completions API — serve with vLLM (recommended), SGLang, or any compatible
stack, then point the scripts at it.

Index-NativeLong retains the published `IndexTeam/Index-Nailong-*` model IDs and `nailong-*` serving presets. The Index-Translate models cover 150 languages; use a full language name when a language code is not mapped by the client.

## Serve

```bash
pip install -U vllm     # needs a build with Qwen3.5 support (tested on 0.29)

./serve_vllm.sh translate-9b    # IndexTeam/Index-Translate-9B on :8000
./serve_vllm.sh translate-2b
./serve_vllm.sh nailong-9b      # long-doc, 229376 max positions per shipped config
./serve_vllm.sh nailong-2b      # long-doc, 262144
./serve_vllm.sh homura-9b       # syllable-controlled
./serve_vllm.sh homura-2b
```

Extra arguments are passed through to `vllm serve`, e.g.
`./serve_vllm.sh nailong-9b --tensor-parallel-size 4 --data-parallel-size 2`.

GPU memory (bf16): 2B ≈ 8 GB, 9B ≈ 24 GB, plus KV cache for long contexts.

## Use

### Free Public Online API & Immersive Translate Proxy

Call the online **Index-Translate-35B-A3B** model without a local GPU using our zero-dependency [`call_api.py`](call_api.py):

```bash
# Quick command-line translation (stdlib-only; supports -t language, --stream, -g glossary, --instruction)
python call_api.py "你好，世界。" --target en

# Local bridge proxy for browser extensions (Windows users can double-click run_proxy_windows.bat)
python call_api.py --serve
```

> 📖 **Immersive Translate Setup Guide**: Browser extensions require a local bridge proxy due to CORS restrictions, WAF protections, and the need to disable CoT thinking output. Run `python call_api.py --serve`, then follow our step-by-step tutorial: **[【Guide】Immersive Translate Configuration Tutorial](../../docs/immersive_translate.md)**.

### Self-Hosted Local Model Invocation

```bash
pip install openai httpx

# 1. General translation (Index-Translate)
python translate.py "你好，世界。今天天气不错。" --target en
python translate.py "The quick brown fox..." --source en --target zh \
    --model IndexTeam/Index-Translate-2B

# 2. instTrans hard constraint: Terminology / Glossary (-g / --glossary)
python translate.py "王平仲采用了更加昂贵的碳纤维材料。碳纤维的好处就是它抗裂缝。" --target en \
    -g "碳纤维:carbon fiber, 抗裂缝:crack resistance"

# 3. instTrans hard constraint: Structured data & format preservation (-H / --hard)
python translate.py '{"user_id": 1024, "message": "您的订单已支付完成。"}' --target en \
    -H "保留源文中的 JSON 格式标记不变"

# 4. instTrans soft constraint: Style and register (-S / --soft) + genre (-d / --genre)
python translate.py "今天下午的会议临时取消了，改天我们再碰一下商量。" --target en \
    -d "商务邮件" -S "调整为严谨、正式、礼貌的商务公文风格"

# 5. instTrans soft constraint: Domain context and word-sense disambiguation (-S / --soft)
python translate.py "The plant is operating at full capacity after the spring upgrade." --target zh \
    -d "工业制造" -S "语境为工业制造与重工厂房领域，准确消歧专有名词（如 plant 译为工厂而非植物）"

# 6. Combined multi-constraint invocation (repeatable -H and -S flags)
python translate.py '{"1": "回复 @零岭七 :乱说，外购不算消费啦？[藏狐] #每日一喵#"}' --target en \
    -d "评论" \
    -H "保留源文中的 JSON 格式标记不变" \
    -H "保留以下社交元素不变: @零岭七、[藏狐]、#每日一喵#"

# 7. Syllable-controlled translation with optional terminology (Index-Homura)
python syllable_translate.py "我们今天去看电影吧" --syllables 7 --target en \
    --glossary "电影:cinema"

# 8. Long-document translation (Index-NativeLong), fixed direction templates
python doc_translate.py novel.txt --direction zh-en -o novel.en.txt
python doc_translate.py paper.txt --direction en-zh --model IndexTeam/Index-Nailong-2B
```

All scripts default to `--base-url http://127.0.0.1:8000/v1` and take
`--base-url/--model` (or `OPENAI_BASE_URL`/`INDEX_MODEL`) to hit any server.

---

## Instruction Following & Constrained Translation

Index-Translate optimizes translation quality jointly with instruction following via Rubric-as-Reward (RaR) and GRPO, formulated as:
$$R_{\mathrm{inst}} = g_{\mathrm{lang}} \cdot g_{\mathrm{hard}} \cdot \bigl(q_{\mathrm{qual}} + q_{\mathrm{soft}}\bigr)$$

Evaluated extensively on the official **instTrans Benchmark** (3,000 real-world multilingual test instances) and **IFMTBench**, the models support **10 distinct constraint categories**:

### 1. Hard Constraints ($g_{\mathrm{hard}}$ Binary Gate)
Hard checks must pass with 100% fidelity; any single violation zeroes out the instance score:
- **Terminology Compliance (`term_compliance`)**: Adhere strictly to user-specified term mappings. Pass mappings directly via `-g / --glossary "term:translation"` or provide a JSON file path, formatted into `【硬性要求】专名/术语对照: A→B、C→D`.
- **Structure & Format Preservation (`format_preserve`)**: In structured documents (JSON, CSV, Markdown tables, HTML), preserve keys, delimiters, tags, numbers, and boolean values intact while translating user-facing text.
- **Placeholders & Code Protection (`format_preserve`)**: In software localization, preserve `{variable}`, `%s`, `[123456]`, URLs, and markup unchanged.
- **Social Elements Preservation (`social_preserve`)**: In social media posts, danmaku, and comments, preserve `@username`, `#hashtag#`, and `[emoji_code]` intact.
- **Layout & Typographic Breaks (`layout_break`)**: Preserve exact paragraphing, line breaks, indentation, and table alignments.
- **Syllable Order Correlation (`syllable_order`)**: In multi-sentence dubbing/subtitling, shorter on-screen duration lines must produce strictly shorter translated syllable counts.

### 2. Soft Constraints ($q_{\mathrm{soft}}$ Graded Score)
Soft constraints assess stylistic nuance, pragmatic intent, and contextual appropriateness (scored 0 / 0.5 / 1 by LLM Judge):
- **Style & Register Consistency (`style_consistency`)**: Fluidly adjust between Formal/Business, Casual/Colloquial, Social Media (Viral / Gen-Z), and Literary styles without tone drifts.
- **Domain Context Disambiguation (`context_disambiguate`)**: For polysemous words (e.g. *Plant*, *Spring*, *Cell*, *Crane*), specifying domain context (industrial manufacturing, greenhouse botany, port engineering, computing) ensures the correct industry-standard translation.
- **Coreference Resolution (`coref_resolution`)**: Accurately resolve pronouns (he/she/it) and prevent character confusion across complex narratives.
- **Cross-Sentence Terminology Uniformity (`term_cross_sentence`)**: Ensure unified translation of specialized terms across entire documents or multi-turn dialogues.
- **Academic & LaTeX Formula Preservation (`academic_format_preserve`)**: In scientific papers, keep LaTeX formulas (`$...$`, `\[...\]`), citations (`[@citation]`), and macros uncorrupted while translating text.

### 3. Syllable Control with Terminology Enforcement (Homura)
**Index-Homura** not only respects strict target syllable budgets (e.g. `--syllables 7`), but **also supports terminology glossaries** (`--glossary`). The model dynamically adjusts syntactic structure and function words to ensure required terms are included while matching the exact rhythm budget.

---

## Prompts

Decoding and serving defaults are collected in the [shared settings table](../../README.md#default-inference-settings). The client automatically formats prompts matching the model's canonical **instTrans format**:

- **Translate (instTrans Formatted Constrained Prompt)**:
  When `-H` / `-S` / `-g` / `-i` constraints are present:
  ```text
  请将以下{源语言}{文体}翻译成{目标语言}，并且严格遵循所有约束要求。

  【源文】
  {source_text}

  【约束要求】
  1. 【硬性要求】...
  2. 【注意】...

  只输出译文，不要有任何额外说明。
  ```
  *(When translating JSON dictionaries under format preservation constraints, the suffix automatically switches to the instTrans standard JSON output instruction)*

- **Translate (Standard Unconstrained Translation)**:
  ```text
  请将以下{源语言}文本翻译为{目标语言}，直接输出翻译结果，不要进行任何解释。

  {source_text}
  ```
  (source omitted when `auto`).

- **Homura (Syllable Control + Optional Glossary)**:
  ```text
  请将以下文本翻译为{目标}，译文严格控制在 N 个音节。要求：严格遵守术语映射表【{术语 -> 译名}】。直接输出翻译结果，不要进行任何解释。

  {text}
  ```

- **NativeLong**:
  Fixed per-direction templates (`prompts/nailong_{zh-en,en-zh,zh-ja,ja-zh}.txt`,
  substitute the single `（在这里放入需要翻译的完整…原文）` marker with the full text).

---

## Cases

- [`cases/translate_cases.jsonl`](cases/translate_cases.jsonl): baseline multilingual short-text evaluation cases.
- [`cases/instruction_cases.jsonl`](cases/instruction_cases.jsonl): recorded real runs covering all 10 instTrans constraint categories (glossary compliance, JSON/CSV format preservation, placeholder protection, social media tags, formal vs. viral styles, domain disambiguation, cross-sentence term consistency, academic LaTeX preservation, and Homura syllable + glossary co-adaptation).
- [`cases/doc_cases.jsonl`](cases/doc_cases.jsonl): native long-document translation cases.
- [`cases/syllable_cases.jsonl`](cases/syllable_cases.jsonl): Homura syllable-controlled cases.
