<p align="center">English · <a href="README_zh.md">中文</a></p>

<h1 align="center">Index-Translate</h1>
<p align="center"><strong>A Multilingual Translation Model Family</strong><br>Text, Speech, Controlled Dubbing, and Long-Document Translation</p>

<p align="center">
  <a href="https://index-translate.bilibili.com/">🌐&nbsp;Demo</a> ·
  <a href="#option-1-free-online-api-zero-gpu-setup">⚡&nbsp;<b>Free API</b></a> ·
  <a href="https://huggingface.co/collections/IndexTeam/index-translate">🤗&nbsp;Hugging&nbsp;Face</a> ·
  <a href="https://modelscope.cn/collections/IndexTeam/Index-Translate"><img src="docs/assets/modelscope.svg" width="16" height="16" alt="">&nbsp;ModelScope</a> ·
  <a href="https://arxiv.org/abs/2609.40181">📚&nbsp;Report</a> ·
  <a href="https://huggingface.co/collections/IndexTeam/index-translate-papers-6abe1f5452920941ea0682d9">🤗&nbsp;Papers</a> ·
  <a href="https://huggingface.co/collections/IndexTeam/index-translate-benchmarks-6ac16fee5057f40abd7d31b7">🤗&nbsp;Benchmarks</a> ·
  <a href="https://qm.qq.com/q/xSASqaiEGA">🐧&nbsp;QQ</a>
</p>

> [!TIP]
> 🚀 **Free Public API Now Available!** Call **Index-Translate-35B-A3B** directly with zero GPU setup. Fully OpenAI-compatible at `https://index-translate.bilibili.com/v1`. Try it in seconds with `python inference/llm/call_api.py "Hello, world!" --target zh`! 👉 [API Quick Start](#option-1-free-online-api-zero-gpu-setup)

Index-Translate is a family of multilingual translation models built on Qwen3.5. The text models cover **150 languages** and follow translation instructions such as terminology, formatting, and content-preservation requirements. The family extends this foundation to speech, syllable-controlled translation, and full-document translation.

- **Index-Translate** translates text, structured content, and community expressions.
- **Index-Echo** produces translated subtitles or speech conditioned on the source speaker's voice.
- **Index-Homura** adjusts translations toward a specified target syllable count.
- **Index-NativeLong** translates complete documents with context across passages.

<p align="center"><img src="docs/assets/benchmark-radar.en.svg" width="760" alt="Seven-category comparison of Index-Translate 35B-A3B preview, 9B, and 2B"></p>

The radar includes **35B-A3B (preview), 9B, and 2B**, with fixed per-axis min–max ranges across all 14 models. Its seven axes are WMT, FLORES, instruction following, low-resource translation, subtitles, MEME, and books/fiction. Instruction following averages instTrans and IFMTBench IFscore. The normalized scale is not an accuracy percentage. The gray dashed line combines the best non-Index score on each axis and does not represent one model. [Raw category scores](docs/assets/seven_category_scores_raw.csv) · [Figure notes](docs/assets/README.md) · [Individual benchmark results](docs/evaluation.md).

[News](#news) · [⚡ Free API](#option-1-free-online-api-zero-gpu-setup) · [Models](#models) · [Quick start](#quick-start) · [Instruction Following](#instruction-following--constrained-translation) · [Examples](#examples) · [Evaluation](#evaluation) · [Benchmarks](#benchmarks) · [Applications](#applications) · [TODO](#todo) · [Papers and citation](#papers-and-citation)

## News

- **2026-10-04:** released free public API endpoints on [index-translate.bilibili.com/v1](https://index-translate.bilibili.com) for Index-Translate-35B-A3B. Fully OpenAI-compatible. Try it with [call_api.py](inference/llm/call_api.py).
- **2026-10-04:** released four [Index-Translate benchmarks](#benchmarks), with datasets/metadata on Hugging Face and evaluation scripts and guides on GitHub.
- **2026-10-03:** released official quantized builds across the family on Hugging Face and ModelScope — **GGUF** for llama.cpp local inference, alongside **FP8** (W8A8) and **NVFP4** (W4A4, Blackwell-optimized) for vLLM serving.
- **2026-09-30:** released Index-Translate, with 2B / 9B / 35B-A3B (preview) text-model weights on Hugging Face and ModelScope, the technical report, and the online demo.

## TODO

- [x] Release official quantized builds (GGUF for llama.cpp local inference, FP8 and NVFP4 for vLLM serving) for the whole family.
- [ ] Release the official version of Index-Translate-35B-A3B.
- [x] Release instTrans, MEME, SandGlass and NAtIveLong data/metadata and evaluation code; see [Benchmarks](#benchmarks).
- [ ] Add support for more languages to Index-Echo.
- [ ] Release larger models.

## Models

The links below provide **2B, 9B, and 35B-A3B (preview)** text-model checkpoints. Evaluation results are included in the [comparison tables](docs/evaluation.md).

| Model | Task and released package coverage | Hugging Face | ModelScope | Inference |
|---|---|---|---|---|
| **Index-Translate** | Text translation and instructions across 150 languages | [2B](https://huggingface.co/IndexTeam/Index-Translate-2B) · [9B](https://huggingface.co/IndexTeam/Index-Translate-9B) · [35B-A3B (preview)](https://huggingface.co/IndexTeam/Index-Translate-35B-A3B-preview) ([⚡Free API](#option-1-free-online-api-zero-gpu-setup)) | [2B](https://modelscope.cn/models/IndexTeam/Index-Translate-2B) · [9B](https://modelscope.cn/models/IndexTeam/Index-Translate-9B) · [35B-A3B (preview)](https://modelscope.cn/models/IndexTeam/Index-Translate-35B-A3B-preview) | [Guide](inference/llm/README.md) · [Free API](inference/llm/call_api.py) |
| **Index-Echo S2TT** | Speech → subtitles; packaged script: zh→en/ja/es | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-2B) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-9B) | [2B](https://modelscope.cn/models/IndexTeam/Index-Echo-S2TT-2B) · [9B](https://modelscope.cn/models/IndexTeam/Index-Echo-S2TT-9B) | [Guide](inference/echo-s2tt/README.md) |
| **Index-Echo S2ST** | Speech → speech; zh→en/es/ja, en→zh/es/ja | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-9B) | [2B](https://modelscope.cn/models/IndexTeam/Index-Echo-S2ST-2B) · [9B](https://modelscope.cn/models/IndexTeam/Index-Echo-S2ST-9B) | [Guide](inference/echo-s2st/README.md) |
| **Index-Homura** | Translation with a target syllable count | [2B](https://huggingface.co/IndexTeam/Index-Homura-2B) · [9B](https://huggingface.co/IndexTeam/Index-Homura-9B) | [2B](https://modelscope.cn/models/IndexTeam/Index-Homura-2B) · [9B](https://modelscope.cn/models/IndexTeam/Index-Homura-9B) | [Guide](inference/llm/README.md) |
| **Index-NativeLong** | Long documents; fixed templates: zh↔en, zh↔ja | [2B](https://huggingface.co/IndexTeam/Index-Nailong-2B) · [9B](https://huggingface.co/IndexTeam/Index-Nailong-9B) | [2B](https://modelscope.cn/models/IndexTeam/Index-Nailong-2B) · [9B](https://modelscope.cn/models/IndexTeam/Index-Nailong-9B) | [Guide](inference/llm/README.md) |

**Naming:** Index-NativeLong is published under the model IDs `IndexTeam/Index-Nailong-2B` and `IndexTeam/Index-Nailong-9B`. Use those IDs in commands. Language support for the speech and long-document packages is listed separately from the text models' 150-language coverage.

**Quantized builds:** every model above is also published in **GGUF** (llama.cpp local inference; all bit-widths in one repository per model, vision mmproj included where applicable), **FP8** (compressed-tensors W8A8, ready for vLLM serving), and **FP4** (compressed-tensors NVFP4 W4A4, for Blackwell GPUs). For the Index-Echo speech models, the GGUF repositories contain the **text LLM backbone only**, while the FP8/FP4 repositories ship the **complete pipeline** with a quantized LLM. All repositories are mirrored on [ModelScope](https://modelscope.cn/organization/IndexTeam).

| Model | GGUF (llama.cpp) | FP8 (vLLM) | FP4 (vLLM, Blackwell) |
|---|---|---|---|
| **Index-Translate** | [2B](https://huggingface.co/IndexTeam/Index-Translate-2B-GGUF) · [9B](https://huggingface.co/IndexTeam/Index-Translate-9B-GGUF) · [35B-A3B (preview)](https://huggingface.co/IndexTeam/Index-Translate-35B-A3B-preview-GGUF) | [2B](https://huggingface.co/IndexTeam/Index-Translate-2B-FP8) · [9B](https://huggingface.co/IndexTeam/Index-Translate-9B-FP8) · [35B-A3B (preview)](https://huggingface.co/IndexTeam/Index-Translate-35B-A3B-preview-FP8) | [2B](https://huggingface.co/IndexTeam/Index-Translate-2B-FP4) · [9B](https://huggingface.co/IndexTeam/Index-Translate-9B-FP4) · [35B-A3B (preview)](https://huggingface.co/IndexTeam/Index-Translate-35B-A3B-preview-FP4) |
| **Index-Homura** | [2B](https://huggingface.co/IndexTeam/Index-Homura-2B-GGUF) · [9B](https://huggingface.co/IndexTeam/Index-Homura-9B-GGUF) | [2B](https://huggingface.co/IndexTeam/Index-Homura-2B-FP8) · [9B](https://huggingface.co/IndexTeam/Index-Homura-9B-FP8) | [2B](https://huggingface.co/IndexTeam/Index-Homura-2B-FP4) · [9B](https://huggingface.co/IndexTeam/Index-Homura-9B-FP4) |
| **Index-NativeLong** | [2B](https://huggingface.co/IndexTeam/Index-Nailong-2B-GGUF) · [9B](https://huggingface.co/IndexTeam/Index-Nailong-9B-GGUF) | [2B](https://huggingface.co/IndexTeam/Index-Nailong-2B-FP8) · [9B](https://huggingface.co/IndexTeam/Index-Nailong-9B-FP8) | [2B](https://huggingface.co/IndexTeam/Index-Nailong-2B-FP4) · [9B](https://huggingface.co/IndexTeam/Index-Nailong-9B-FP4) |
| **Index-Echo S2TT** | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-2B-GGUF) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-9B-GGUF) (LLM backbone) | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-2B-FP8) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-9B-FP8) (full pipeline) | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-2B-FP4) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-9B-FP4) (full pipeline) |
| **Index-Echo S2ST** | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B-GGUF) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-9B-GGUF) (LLM backbone) | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B-FP8) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-9B-FP8) (full pipeline) | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B-FP4) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-9B-FP4) (full pipeline) |

## Inference

### Quick start

#### Option 1: Free Online API (Zero GPU Setup)

You can call our free online API directly without local GPUs. We recommend using our zero-dependency Python script [`inference/llm/call_api.py`](inference/llm/call_api.py):

```bash
# 1. Quick command-line translation (zero dependencies, works out-of-the-box)
python inference/llm/call_api.py "你好，世界。今天天气不错，我们去公园散步吧。" --target en

# 2. Local proxy bridge for browser extensions (e.g. Immersive Translate / 沉浸式翻译)
# Browser extensions require a local bridge proxy due to CORS/WAF headers and thinking tag suppression:
python inference/llm/call_api.py --serve
# Then configure Immersive Translate:
# - Service: Custom / OpenAI
# - API URL: http://127.0.0.1:8080/v1
# - Model: Index-Translate-35B-A3B
# - API Key: Any string (e.g. index)

# Option A: Standard Chat Completions API (OpenAI-compatible)
curl https://index-translate.bilibili.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Index-Translate-35B-A3B",
    "messages": [{"role": "user", "content": "请将以下文本翻译为英语，直接输出翻译结果，不要进行任何解释。\n\n你好，世界。"}]
  }'

# Option B: Modern OpenAI Responses API (compatible with client.responses.create / POST /v1/responses)
curl https://index-translate.bilibili.com/v1/responses \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Index-Translate-35B-A3B",
    "input": "请将以下文本翻译为英语，直接输出翻译结果，不要进行任何解释。\n\n你好，世界。"
  }'
```

> [!TIP]
> 🌐 **Bilingual Web Browsing? Immersive Translate is supported out-of-the-box (Windows / macOS / Linux)!**
> Browser extensions benefit from our zero-config local bridge proxy (Windows users can simply double-click `run_proxy_windows.bat` in the root folder).
> 👉 **[【Setup Guide】Immersive Translate Configuration Tutorial (Windows / macOS / Linux, with Screenshots & Troubleshooting)](docs/immersive_translate.md)**

#### Option 2: Self-hosted local vLLM

Start with the 2B text model on a CUDA GPU using a vLLM build with Qwen3.5 support. From a terminal:

```bash
git clone https://github.com/bilibili/Index-Translate.git
cd Index-Translate
pip install -U vllm
pip install -r inference/llm/requirements.txt
vllm serve IndexTeam/Index-Translate-2B --host 127.0.0.1 --port 8000 --max-model-len 4096
```

From the same repository directory in **another terminal**:

```bash
python inference/llm/translate.py \
  "你好，世界。今天天气不错，我们去公园散步吧。" \
  --target en --model IndexTeam/Index-Translate-2B
```

An output recorded with the released 2B model is:

> Hello, world. The weather is nice today. Let's go for a walk in the park.

See [captured cases](inference/llm/cases/translate_cases.jsonl), [text inference](inference/llm/README.md), and [prompt examples](docs/prompts.md). The 4,096-token setting above is a short-text example; the serving presets are listed in the table below.

For audio, use the dedicated [S2TT subtitle guide](inference/echo-s2tt/README.md) or [S2ST dubbing guide](inference/echo-s2st/README.md).

### Instruction Following & Constrained Translation

Index-Translate deeply integrates instruction-following capabilities (instTrans). It supports both **hard constraints (format preservation, strict terminology glossary enforcement)** and **soft constraints (tone & style, domain disambiguation)** out of the box via `translate.py` and `syllable_translate.py`:

```bash
# Hard constraint 1: Strict terminology glossary enforcement (-g / --glossary)
python inference/llm/translate.py \
  "王平仲采用了更加昂贵的碳纤维材料。碳纤维的好处就是它抗裂缝。" \
  --target en -g "碳纤维:carbon fiber, 抗裂缝:crack resistance"

# Hard constraint 2: Format & structure preservation (-H / --hard)
python inference/llm/translate.py \
  '{"user_id": 1024, "event": "purchase", "message": "您的订单已支付完成。"}' \
  --target en -H "保留源文中的 JSON 格式标记不变"

# Soft constraint 1: Tone and style adjustment (-S / --soft) + genre (-d / --genre)
python inference/llm/translate.py \
  "今天下午的会议临时取消了，改天我们再碰一下商量。" \
  --target en -d "商务邮件" -S "调整为严谨、正式、礼貌的商务公文风格"

# Soft constraint 2: Domain context and word-sense disambiguation (-S / --soft)
python inference/llm/translate.py \
  "The plant is operating at full capacity after the spring upgrade." \
  --target zh -d "工业制造" -S "语境为工业制造与重工厂房领域，准确消歧专有名词（如 plant 译为工厂而非植物）"

# Syllable control synergy: Index-Homura strictly respects syllable budgets while embedding glossaries
python inference/llm/syllable_translate.py \
  "我们今天去看电影吧" --syllables 7 --target en --glossary "电影:cinema"
```

> **instTrans Specification & Constraint Details:**
> - **Canonical Prompt**: Automatically formatted by the client into the instTrans benchmark structure (`【源文】` + numbered `1. 【硬性要求】...` / `2. 【注意】...` + suffix instructions).
> - **Hard Constraints**: Structural formatting (JSON/CSV/code/placeholders), terminology glossaries, social elements, and syllable ordering. Binary gated ($g_{\mathrm{hard}}$); any single failure zeroes the instance score.
> - **Soft Constraints**: Tone/style adaptation, contextual sense disambiguation, cross-sentence consistency, and LaTeX preservation. Evaluated on a graded scale ($q_{\mathrm{soft}}$).
> - See the [text inference guide](inference/llm/README.md) and [instruction cases](inference/llm/cases/instruction_cases.jsonl) for full examples.

### Default inference settings

This is the shared reference for the repository clients and the released Echo packages. Translate covers **2B / 9B / 35B-A3B (preview)**; the other families cover **2B / 9B**. Decoding defaults are shared across sizes within each family.

**Not set** means the client inherits the backend/model configuration; **—** means the setting does not apply. Text-generation rows describe transcription/translation for Echo; speech generation has separate rows.

| Setting | [Index-Translate](inference/llm/README.md) | [Index-Homura](inference/llm/README.md) | [Index-NativeLong](inference/llm/README.md) | [Echo S2TT](inference/echo-s2tt/README.md) | [Echo S2ST](inference/echo-s2st/README.md) |
|---|---|---|---|---|---|
| Entry point | `translate.py` | `syllable_translate.py` | `doc_translate.py` | `s2tt.py` → package `infer.py` | `dub.py` → package `DubbingBridgeModel` |
| Default checkpoint | 9B | 9B | 9B (`Index-Nailong`) | 2B | Local `./Index-Echo-S2ST-2B` |
| Text decoding | Greedy | Sampling | Greedy | Greedy (`do_sample=False`) | Greedy (`do_sample=False`) |
| `temperature` | `0` | `0.3` | `0` | `0` | `0` (text) |
| `top_p` | Not set | Not set | `1` | Not set | Not set (text) |
| `top_k` | Not set | Not set | `-1` | Not set | Not set (text) |
| `min_p` | Not set | Not set | `0` | Not set | Not set (text) |
| `presence_penalty` | Not set | Not set | `0` | — | — |
| `repetition_penalty` | Not set | Not set | `1` | Not set | Not set (text) |
| `seed` | Not set | Not set | `42` | Not set | `42` (speech) |
| Thinking | `enable_thinking=False` | `enable_thinking=False` | `enable_thinking=False` | Empty `<think>` block prefilled | Empty `<think>` block prefilled |
| Text output budget | `max_tokens=1024` | `max_tokens=max(512, 3 * len(text))` | `max_tokens` omitted; server selects the cap | `max_new_tokens=2000` per window | `max_new_tokens=1024` |
| Text stop conditions | Not set | Not set | `stop_token_ids=[248044, 248046]`; `ignore_eos=False` | Tokenizer EOS / `<\|im_end\|>` | Tokenizer EOS / `<\|im_end\|>` |
| Output streaming | No | No | `stream=True` | Sequential window results | Speech `stream=False` |
| `serve_vllm.sh` context (input + output) | 2B / 9B: `32768`; no 35B preset | `32768` | 2B: `262144`; 9B: `229376` | — | — |
| Default language / constraint | Source `auto`, target `en` | Target `en`; `--syllables` required | `zh-en` | `zh-en` | `--lang` required; source inferred as zh/en |
| Audio window / history | — | — | — | `--max-win 60` seconds; `--ctx-k 5` prior windows | Utterances ≤30 seconds recommended; `chunk=False` |
| Speech sampler | — | — | — | — | Fixed `sampling=25`; CosyVoice RAS defaults `top_p=0.8`, `top_k=25` |
| Speech-token budget | — | — | — | — | Maximum `min(1500, 20 * m)`; minimum `2 * m` |
| Speech speed / sample rate | — | — | — | — | `speed=1.0`; `24000` Hz |
| Main overrides | `--model`, `--instruction`, `--glossary`, `--temperature`, `--max-tokens` | `--model`, `--syllables`, `--glossary`, `--temperature`, `--max-tokens` | `--model`, `--direction`, `--max-tokens` | `--size`, `--temperature`, `--max-new-tokens`, `--max-win`, `--ctx-k`, `--glossary` | `--model-dir`, `--lang`; lower-level API for budgets / seed |

- **Text clients:** default to `http://127.0.0.1:8000/v1` with API key `EMPTY`. Use `--base-url` / `--api-key` or `OPENAI_BASE_URL` / `OPENAI_API_KEY`; `--model` overrides `INDEX_MODEL` and the default checkpoint. Serve 35B-A3B manually and select it with `--model IndexTeam/Index-Translate-35B-A3B-preview`.
- **Budgets:** Homura's `len(text)` is the Python character count after trimming input. NativeLong's omitted `max_tokens` leaves the output cap to the server; context capacity and server limits still apply. Pass a positive `--max-tokens` for an explicit cap. Context includes the full prompt and generated output; override serving limits with `--max-model-len`.
- **Echo S2ST:** `m` is the aligned target-text token count. `sampling=25` is a fixed package-code argument, not a CLI option. The public `DubbingBridgeModel.dub` wrapper exposes neither `seed` nor token budgets; use the lower-level `extract` / `synth` API documented in the [model card](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B#configurable-api-parameters). `chunk=True` is not implemented.
- **Scope:** these are usage defaults. The technical report's benchmark decoding and context settings are documented separately in [Evaluation](docs/evaluation.md).

## Examples

These examples are drawn from the [official demo](https://index-translate.bilibili.com/?p=/site/home.html#benchmark-cases). Outputs below illustrate individual cases; full comparisons and task settings are available on the demo and in the report.

### Translate text while preserving a hashtag

**Task:** translate this JSON into Korean, preserving its structure, stars, and the Chinese hashtag.

```json
{"title": "⭐2月13日例行维护公告⭐", "content": "#热血航线大和登场#"}
```

**Index-Translate-9B:**

```json
{"title": "⭐2월 13일 정기 점검 공지⭐", "content": "#热血航线大和登场#"}
```

The title is translated while the requested hashtag remains unchanged. [Try text translation](https://index-translate.bilibili.com/?p=/site/translate.html&lang=en).

### Keep the meaning of a community expression

**Source:** 狒瘾犯了就去打 — in this gaming context, “狒瘾” refers to the urge to play Final Fantasy XIV.

| Model | English output |
|---|---|
| Index-Translate-9B | When the FFXIV itch hits, just go play. |
| Index-Translate-2B | Go play when my FFXIV addiction kicks in. |
| Hy-MT2-7B | If you get monkey addiction, go fight. |

### Set the translation's syllable budget

**Source:** 生活两天，是一种什么体验. Index-Homura-9B produces different wording for three requested lengths:

| Target / observed syllables | English output |
|---|---|
| 10 / 10 | to live for two days. What would that be like? |
| 14 / 14 | What would it be like to live there for two days, I wonder? |
| 18 / 18 | What would it be like to live there for two days, trying to get by somehow? |

These three examples meet their targets; syllable control is approximate in general, and spoken duration also depends on delivery. [Try Index-Homura](https://index-translate.bilibili.com/?p=/site/syllable.html&lang=en).

### Keep a character's name consistent across a document

In a roughly 32K-token fantasy document, “王妃” is a character's name. The following extracts compare native full-document translation with the same 9B model in a chunked workflow using neighboring context and an automatic glossary.

| Source position | Index-NativeLong-9B full document | Same 9B with chunking |
|---|---|---|
| 31.3% | Mentor Wang Fei | Instructor Wangfei |
| 56.6% | Wang Fei | the Dean |
| 84.8% | Wang Fei | The Queen Consort |

Positions are measured by source characters. The full-document output keeps the name at these locations; the demo also shows how an externally supplied glossary can repair the chunked result. [Try Index-NativeLong](https://index-translate.bilibili.com/?p=/site/doc.html&lang=en).

### Watch speech translation

![Index-Echo evaluation](docs/assets/echo_benchmark_overview.en.svg)

The S2ST panels compare the deployed 2B system, a pipeline, and SeamlessM4T-v2. This demo comparison is separate from the six-direction matched study in the report; SeamlessM4T-v2 does not clone the source voice.

<table>
<tr><th>Speech-to-speech dubbing</th><th>Multilingual subtitles</th></tr>
<tr>
<td align="center"><a href="https://index-translate.bilibili.com/?p=/site/assets/blog/echo-demo.mp4"><img src="docs/assets/echo-s2st.png" height="180" alt="Watch the Index-Echo English-to-Japanese dubbing demo"></a></td>
<td align="center"><a href="https://index-translate.bilibili.com/?p=/site/assets/blog/echo-demo-s2tt.mp4"><img src="docs/assets/echo-s2tt.png" height="180" alt="Watch the Index-Echo multilingual subtitle demo"></a></td>
</tr>
<tr><td>English video with Japanese dubbing</td><td>Video with translations in multiple languages</td></tr>
</table>

Click either preview to watch the video, or [open Index-Echo](https://index-translate.bilibili.com/?p=/site/index.html&lang=en). The website demonstration and the packaged inference interfaces have different language coverage; the [model table](#models) lists the released interfaces.

## Evaluation

![Updated text translation benchmarks](docs/assets/text_benchmark_overview.en.svg)

The charts reproduce the updated demo comparison. *35B-A3B is the preview model. The instruction panels average instTrans and IFMTBench: Quality combines instTrans quality and IFMTBench XCOMET-XXL, while IFscore averages their instruction scores. Individual benchmark metrics remain separate in the tables below.

The following tables cover general text translation, low-resource translation, and low-resource instruction following. FLORES uses COMET-22; WMT26 uses a judge score. instTrans reports translation quality and instruction following separately. MEME measures translation quality for community and cultural expressions. Higher is better for every metric in the first table below; scales differ across columns.

| Model | FLORES ↑ | WMT26 ↑ | instTrans quality ↑ | instTrans IFscore ↑ | MEME ↑ |
|---|---:|---:|---:|---:|---:|
| **Index-Translate-35B-A3B (preview)** | 0.8794 | 76.76 | 0.6901 | 0.8336 | 0.7405 |
| **Index-Translate-9B** | 0.8789 | 75.35 | 0.6771 | 0.8209 | 0.7387 |
| **Index-Translate-2B** | 0.8655 | 60.26 | 0.5391 | 0.7569 | 0.6443 |
| Hy-MT2-7B | 0.8747 | 60.51 | 0.5143 | 0.6079 | 0.5139 |
| Hy-MT2-30B-A3B | 0.8787 | 66.81 | 0.5725 | 0.6415 | 0.5812 |
| DeepSeek-V4.1-Flash | 0.8762 | 83.55 | 0.6068 | 0.6374 | 0.7424 |
| GPT-5.6-Sol | 0.8650 | 89.10 | 0.6902 | 0.7624 | 0.7194 |
| Gemini 3.5 Flash Lite | 0.8750 | 79.52 | 0.6068 | 0.6374 | 0.7034 |

### Low-resource translation and instruction following

FLORES_minor_pair evaluates general translation in low-resource languages; instTrans_minor reports translation quality and instruction following separately. Off-target is the percentage of outputs in a language other than the target language; lower is better. Higher is better for the other metrics. Bold marks the best value in each column of this table.

| Model | FLORES_minor_pair<br>COMET-22 ↑ | FLORES_minor_pair<br>XCOMET-XXL ↑ | FLORES_minor_pair<br>off-target ↓ | instTrans_minor<br>Quality ↑ | instTrans_minor<br>IFscore ↑ | instTrans_minor<br>off-target ↓ |
|---|---:|---:|---:|---:|---:|---:|
| **Index-Translate-35B-A3B (preview)** | 0.8168 | 0.7164 | 2.4% | 0.5151 | 0.7715 | 4.05% |
| **Index-Translate-9B** | 0.7992 | 0.6805 | 4.0% | 0.5222 | **0.7725** | **3.47%** |
| **Index-Translate-2B** | 0.7377 | 0.4817 | 4.2% | 0.3050 | 0.6586 | 3.97% |
| Hy-MT2-7B | 0.4626 | 0.3334 | 35.7% | 0.1121 | 0.2405 | 45.40% |
| Hy-MT2-30B-A3B | 0.6746 | 0.5359 | 14.5% | 0.2246 | 0.4449 | 15.47% |
| DeepSeek-V4.1-Flash | **0.8333** | **0.7297** | **1.3%** | 0.4793 | 0.5854 | 5.73% |
| GPT-5.6-Sol | 0.7669 | 0.6918 | 10.4% | **0.5757** | 0.6866 | 7.73% |
| Gemini 3.5 Flash Lite | 0.8122 | 0.6995 | 3.3% | 0.3927 | 0.5584 | 12.18% |

Among the three Index-Translate models, 35B-A3B (preview) has the highest FLORES_minor_pair COMET-22 and XCOMET-XXL scores (**0.8168 / 0.7164**), with a **2.4%** off-target rate. On instTrans_minor, Index-Translate-9B achieves the highest IFscore (**0.7725**) and lowest off-target rate (**3.47%**) among all compared models; its quality score is **0.5222**.

[Full tables](docs/evaluation.md) retain all comparison models, low-resource metrics, WMT24++, IFMTBench, domain averages, general capabilities, speech, SandGlass, and long-document results. Detailed settings and analysis are in the [technical report](https://arxiv.org/abs/2609.40181).

### Index-Homura and Index-NativeLong

![Index-Homura evaluation](docs/assets/homura_benchmark_overview.en.svg)

SandGlass overall score and length adherence from the demo; the overall score differs from the separate translation-quality metric in the detailed tables.

![Index-NativeLong 64K evaluation](docs/assets/nativelong_benchmark_overview.en.svg)

GuoFeng and BWB Track A3 at 64K Chinese-side tokens.

For the specialized models, Index-Homura-9B reaches **81.92% within 10% of the target syllable count** on SandGlass. Index-NativeLong-9B scores **0.7891 / 0.7683 / 0.8848** on GuoFeng / BWB / Books. The full tables include translation-quality tradeoffs and evaluation notes.

## Benchmarks

Find the datasets and metadata in the [🤗 Index-Translate Benchmarks collection](https://huggingface.co/collections/IndexTeam/index-translate-benchmarks-6ac16fee5057f40abd7d31b7). Evaluation scripts, a pinned data downloader and run instructions are available in [benchmarks/](benchmarks/README.md).

| Benchmark | Public release | Dataset | Evaluation code and guide |
|---|---|---|---|
| **instTrans** | 3,000 translation instruction tasks; 10 constraint types | [🤗 InstTrans-Bench](https://huggingface.co/datasets/IndexTeam/InstTrans-Bench) | [insttrans](benchmarks/insttrans/README.md) |
| **MEME** | 3,638 Chinese-to-English cases; 703 terms and 857 senses | [🤗 Meme-Translation-Bench](https://huggingface.co/datasets/IndexTeam/Meme-Translation-Bench) | [meme](benchmarks/meme/README.md) |
| **SandGlass** | 3,600 cases: 300 subtitles × 4 target languages × 3 length budgets | [🤗 Sandglass-Bench](https://huggingface.co/datasets/IndexTeam/Sandglass-Bench) | [sandglass](benchmarks/sandglass/README.md) |
| **NAtIveLong** | Metadata for 84 BWB and 84 GuoFeng long-document cases, evaluation code and acquisition instructions | [🤗 NAtIveLong](https://huggingface.co/datasets/IndexTeam/NAtIveLong) | [nativelong](benchmarks/nativelong/README.md) |

NAtIveLong includes no source novels or reference translations: obtain official BWB data separately; GuoFeng provides a local reconstruction tool. The instTrans release does not include the 2,793 low-resource extension tasks in the evaluation tables. Original prompts are preserved; each directory's `RELEASE_REVIEW.md` records review changes and validation limits. Historical scores have not been rerun. Each benchmark has its own licensing terms; the repository's root license does not replace them.

See the [full evaluation settings](docs/evaluation.md) and [IFMTBench preprocessing](docs/evaluation.md#ifmtbench-preprocessing) for other results.

## Applications

- **[Immersive Translate Guide](docs/immersive_translate.md):** step-by-step tutorial with screenshots for Windows (one-click `.bat` script provided) / macOS / Linux to use the free public 35B API or local models with Immersive Translate.
- **[Native Browser extension](extension/README.md):** lightweight built-in webpage translator supporting Chrome, Edge, and Firefox.
- **[Video dubbing pipeline](video-dub/README.md):** extract audio, separate vocals, segment speech, translate and dub, then align the result to the original video.

## Community

Join the [QQ group (960123527)](https://qm.qq.com/q/xSASqaiEGA) for discussion and feedback. You can also scan the QR code below to join.

<p align="center"><a href="https://qm.qq.com/q/xSASqaiEGA"><img src="docs/assets/qq-group.jpg" width="320" alt="QR code to join QQ group 960123527"></a></p>

## Papers and citation

Browse all three papers in the [🤗 Hugging Face Papers collection](https://huggingface.co/collections/IndexTeam/index-translate-papers-6abe1f5452920941ea0682d9).

- **Index-Translate:** [A Multilingual Translation Model Family — Text, Speech, Controlled Dubbing, and Long-Document Translation](https://arxiv.org/abs/2609.40181) · [🤗 HF Papers](https://huggingface.co/papers/2609.40181)
- **HOMURA:** [Taming the Sand-Glass for Time-Constrained LLM Translation via Reinforcement Learning](https://arxiv.org/abs/2601.10187) · [🤗 HF Papers](https://huggingface.co/papers/2601.10187)
- **RIVAL:** [Reinforcement Learning with Iterative and Adversarial Optimization for Machine Translation](https://arxiv.org/abs/2506.05070) · [🤗 HF Papers](https://huggingface.co/papers/2506.05070)

If you use this model family or its related methods, please cite the relevant papers:

```bibtex
@techreport{indextranslate2026,
  author={Tianjiao Li and Mengran Yu and Chenyu Shi and Lusheng Zhang and
          Qisi Chen and Yanshan Zhou and Ji Qi and Jingying Liu and
          Yuang Feng and Ziang Cui and Tianxing Yan},
  title={Index-Translate: A Multilingual Translation Model Family --- Text, Speech, Controlled Dubbing, and Long-Document Translation},
  institution={Index LLM Team},
  year={2026},
  month={September},
  eprint={2609.40181},
  archivePrefix={arXiv},
  primaryClass={cs.CL},
  url={https://arxiv.org/abs/2609.40181}
}

@misc{homura2026,
  author={Ziang Cui and Mengran Yu and Chenyu Shi and Yingxuan Shi and Tianjiao Li},
  title={HOMURA: Taming the Sand-Glass for Time-Constrained LLM Translation via Reinforcement Learning},
  year={2026},
  eprint={2601.10187},
  archivePrefix={arXiv},
  primaryClass={cs.CL},
  url={https://arxiv.org/abs/2601.10187}
}

@misc{rival2025,
  author={Tianjiao Li and Mengran Yu and Chenyu Shi and Yanjun Zhao and
          Xiaojing Liu and Qiang Zhang and Qi Zhang and Xuanjing Huang and Jiayin Wang},
  title={RIVAL: Reinforcement Learning with Iterative and Adversarial Optimization for Machine Translation},
  year={2025},
  eprint={2506.05070},
  archivePrefix={arXiv},
  primaryClass={cs.CL},
  url={https://arxiv.org/abs/2506.05070}
}
```

## License and feedback

[Apache-2.0](LICENSE). Questions and feedback are welcome through [GitHub Issues](https://github.com/bilibili/Index-Translate/issues).
