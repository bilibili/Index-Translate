<p align="center"><a href="README.md">English</a> · 中文</p>

<h1 align="center">Index-Translate</h1>
<p align="center"><strong>多语言翻译模型家族</strong><br>文本、语音、可控配音与长文档翻译</p>

<p align="center">
  <a href="https://index-translate.bilibili.com/">🌐&nbsp;Demo</a> ·
  <a href="#方式一免费公网-api-快速调用无需本地-gpu">⚡&nbsp;<b>免费 API</b></a> ·
  <a href="https://huggingface.co/collections/IndexTeam/index-translate">🤗&nbsp;Hugging&nbsp;Face</a> ·
  <a href="https://modelscope.cn/collections/IndexTeam/Index-Translate"><img src="docs/assets/modelscope.svg" width="16" height="16" alt="">&nbsp;ModelScope</a> ·
  <a href="https://arxiv.org/abs/2609.40181">📚&nbsp;报告</a> ·
  <a href="https://huggingface.co/collections/IndexTeam/index-translate-papers-6abe1f5452920941ea0682d9">🤗&nbsp;论文</a> ·
  <a href="https://huggingface.co/collections/IndexTeam/index-translate-benchmarks-6ac16fee5057f40abd7d31b7">🤗&nbsp;Benchmarks</a> ·
  <a href="https://qm.qq.com/q/xSASqaiEGA">🐧&nbsp;QQ群</a>
</p>

> [!TIP]
> 🚀 **官方免费 API 现已开放！** 无需本地显卡环境，直接免费调用 **Index-Translate-35B-A3B** 旗舰翻译模型。完全兼容 OpenAI 接口规范（Base URL: `https://index-translate.bilibili.com/v1`）。支持免依赖脚本即开即用：`python inference/llm/call_api.py "你好，世界" --target en`！👉 [快速上手指南](#方式一免费公网-api-快速调用无需本地-gpu)

Index-Translate 是基于 Qwen3.5 构建的多语言翻译模型家族。文本模型覆盖**150 种语言**，支持术语、格式、保留内容等翻译指令，并将共同的多语基础扩展到视觉图像、语音、音节可控翻译和长文档翻译。

- **Index-Translate**：翻译文本、多模态图像（基于原生视觉编码器，零 OCR 依赖）、结构化内容与社区表达。
- **Index-Echo**：生成目标语言字幕或配音，配音时参考源语音的说话人声音特征。
- **Index-Homura**：根据指定的目标音节数调整译文。
- **Index-NativeLong**：输入完整文档，利用上下文维持前后联系。

<p align="center"><img src="docs/assets/benchmark-radar.zh.svg" width="760" alt="Index-Translate 35B-A3B preview、9B 与 2B 文本模型的七维翻译能力对比"></p>

新版雷达图包含 **35B-A3B（preview）、9B 和 2B**，归一化范围覆盖全部 14 款模型；七个维度依次为 WMT、FLORES、指令遵循、小语种、字幕翻译、MEME 和书籍网文。指令遵循取 instTrans 与 IFMTBench IFscore 的均值。

雷达图采用官网七类聚合分数，在完整对比模型集合上固定各维度的 min–max 范围进行归一化，并非准确率。灰色虚线是各维度非 Index 模型的最高值组合，不代表一个实际模型。[原始聚合分数](docs/assets/seven_category_scores_raw.csv) · [图表说明](docs/assets/README.md) · [单项评测结果](docs/evaluation_zh.md)。

[最新动态](#最新动态) · [⚡ 免费 API](#方式一免费公网-api-快速调用无需本地-gpu) · [🖼️ 图片翻译](#多模态图片翻译vision) · [模型下载](#模型下载) · [快速上手](#快速上手) · [指令遵循](#指令遵循与约束翻译) · [精选案例](#精选案例) · [评测结果](#评测结果) · [Benchmarks](#benchmarks) · [应用工具](#应用工具) · [TODO](#todo) · [论文与引用](#论文与引用)

## 最新动态

- **2026-10-10：** 全面开放多模态图片翻译（Vision）支持！免费公网 API、在线 Demo、Python 调用脚本（[call_api.py](inference/llm/call_api.py)）与 GGUF mmproj 权重同步支持图像输入，零外部 OCR 依赖。详见 [图文教程](docs/image_translate_zh.md)。
- **2026-10-04：** 正式开放 35B-A3B 免费公网 API 接口（[index-translate.bilibili.com/v1](https://index-translate.bilibili.com)），完全兼容 OpenAI 规范。支持通过 [call_api.py](inference/llm/call_api.py) 免 GPU 快速调用。
- **2026-10-04：** 发布四个 [Index-Translate benchmarks](#benchmarks)；Hugging Face 提供数据／元数据，GitHub 同步评测脚本和运行说明。
- **2026-10-03：** 发布全家族官方量化版本（Hugging Face 与 ModelScope 同步开放）—— 包含适用于 llama.cpp 本地推理的 **GGUF**（含原生视觉 mmproj 权重），以及适用于 vLLM 部署的 **FP8**（W8A8）与 **NVFP4**（W4A4，面向 Blackwell GPU）。
- **2026-09-30：** Index-Translate 正式发布，2B / 9B / 35B-A3B（preview）文本模型权重在 Hugging Face 与 ModelScope 开放，技术报告与在线 Demo 上线。

## TODO

- [x] 发布全家族官方量化版本（GGUF 用于 llama.cpp 本地推理，FP8 与 NVFP4 用于 vLLM 部署）。
- [ ] 发布 Index-Translate-35B-A3B 正式版。
- [x] 发布 instTrans、MEME、SandGlass 与 NAtIveLong 的数据／元数据和评测代码，见 [Benchmarks](#benchmarks)。
- [ ] 为 Index-Echo 增加更多语种支持。
- [ ] 发布更大规模的模型。

## 模型下载

下表提供 **2B、9B 与 35B-A3B（preview）** 文本模型权重，评测结果见[完整评测表](docs/evaluation_zh.md)。

| 模型 | 任务与发布包覆盖 | Hugging Face | ModelScope | 推理 |
|---|---|---|---|---|
| **Index-Translate** | 150 种语言的文本翻译与指令遵循 | [2B](https://huggingface.co/IndexTeam/Index-Translate-2B) · [9B](https://huggingface.co/IndexTeam/Index-Translate-9B) · [35B-A3B (preview)](https://huggingface.co/IndexTeam/Index-Translate-35B-A3B-preview) ([⚡免费API](#方式一免费公网-api-快速调用无需本地-gpu)) | [2B](https://modelscope.cn/models/IndexTeam/Index-Translate-2B) · [9B](https://modelscope.cn/models/IndexTeam/Index-Translate-9B) · [35B-A3B (preview)](https://modelscope.cn/models/IndexTeam/Index-Translate-35B-A3B-preview) | [使用说明](inference/llm/README_zh.md) · [免费API](inference/llm/call_api.py) |
| **Index-Echo S2TT** | 语音转字幕；发布脚本支持中→英/日/西 | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-2B) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-9B) | [2B](https://modelscope.cn/models/IndexTeam/Index-Echo-S2TT-2B) · [9B](https://modelscope.cn/models/IndexTeam/Index-Echo-S2TT-9B) | [使用说明](inference/echo-s2tt/README_zh.md) |
| **Index-Echo S2ST** | 语音配音；中→英/西/日，英→中/西/日 | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-9B) | [2B](https://modelscope.cn/models/IndexTeam/Index-Echo-S2ST-2B) · [9B](https://modelscope.cn/models/IndexTeam/Index-Echo-S2ST-9B) | [使用说明](inference/echo-s2st/README_zh.md) |
| **Index-Homura** | 按指定目标音节数翻译 | [2B](https://huggingface.co/IndexTeam/Index-Homura-2B) · [9B](https://huggingface.co/IndexTeam/Index-Homura-9B) | [2B](https://modelscope.cn/models/IndexTeam/Index-Homura-2B) · [9B](https://modelscope.cn/models/IndexTeam/Index-Homura-9B) | [使用说明](inference/llm/README_zh.md) |
| **Index-NativeLong** | 长文档；固定模板支持中↔英、中↔日 | [2B](https://huggingface.co/IndexTeam/Index-Nailong-2B) · [9B](https://huggingface.co/IndexTeam/Index-Nailong-9B) | [2B](https://modelscope.cn/models/IndexTeam/Index-Nailong-2B) · [9B](https://modelscope.cn/models/IndexTeam/Index-Nailong-9B) | [使用说明](inference/llm/README_zh.md) |

**命名说明：** Index-NativeLong 的实际模型仓库 ID 为 `IndexTeam/Index-Nailong-2B` 和 `IndexTeam/Index-Nailong-9B`，运行命令请使用这两个 ID。语音与长文档发布包的语言覆盖见上表，文本模型的 150 种语言覆盖不等同于每个专门模型的接口覆盖。

**量化版本：** 以上全部模型均同步发布 **GGUF**（适用于 llama.cpp 本地推理；每个模型的全部位宽在同一仓库，含视觉 mmproj）、**FP8**（compressed-tensors W8A8，适用于 vLLM 部署）与 **FP4**（compressed-tensors NVFP4 W4A4，面向 Blackwell GPU）。其中 Index-Echo 语音模型的 GGUF 仓库**仅包含文本 LLM 主干**，FP8/FP4 仓库则包含**完整管线**（LLM 为量化版本）。所有仓库在 [ModelScope](https://modelscope.cn/organization/IndexTeam) 同步开放。

| 模型 | GGUF（llama.cpp） | FP8（vLLM） | FP4（vLLM，Blackwell） |
|---|---|---|---|
| **Index-Translate** | [2B](https://huggingface.co/IndexTeam/Index-Translate-2B-GGUF) · [9B](https://huggingface.co/IndexTeam/Index-Translate-9B-GGUF) · [35B-A3B (preview)](https://huggingface.co/IndexTeam/Index-Translate-35B-A3B-preview-GGUF) | [2B](https://huggingface.co/IndexTeam/Index-Translate-2B-FP8) · [9B](https://huggingface.co/IndexTeam/Index-Translate-9B-FP8) · [35B-A3B (preview)](https://huggingface.co/IndexTeam/Index-Translate-35B-A3B-preview-FP8) | [2B](https://huggingface.co/IndexTeam/Index-Translate-2B-FP4) · [9B](https://huggingface.co/IndexTeam/Index-Translate-9B-FP4) · [35B-A3B (preview)](https://huggingface.co/IndexTeam/Index-Translate-35B-A3B-preview-FP4) |
| **Index-Homura** | [2B](https://huggingface.co/IndexTeam/Index-Homura-2B-GGUF) · [9B](https://huggingface.co/IndexTeam/Index-Homura-9B-GGUF) | [2B](https://huggingface.co/IndexTeam/Index-Homura-2B-FP8) · [9B](https://huggingface.co/IndexTeam/Index-Homura-9B-FP8) | [2B](https://huggingface.co/IndexTeam/Index-Homura-2B-FP4) · [9B](https://huggingface.co/IndexTeam/Index-Homura-9B-FP4) |
| **Index-NativeLong** | [2B](https://huggingface.co/IndexTeam/Index-Nailong-2B-GGUF) · [9B](https://huggingface.co/IndexTeam/Index-Nailong-9B-GGUF) | [2B](https://huggingface.co/IndexTeam/Index-Nailong-2B-FP8) · [9B](https://huggingface.co/IndexTeam/Index-Nailong-9B-FP8) | [2B](https://huggingface.co/IndexTeam/Index-Nailong-2B-FP4) · [9B](https://huggingface.co/IndexTeam/Index-Nailong-9B-FP4) |
| **Index-Echo S2TT** | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-2B-GGUF) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-9B-GGUF)（LLM 主干） | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-2B-FP8) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-9B-FP8)（完整管线） | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-2B-FP4) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-9B-FP4)（完整管线） |
| **Index-Echo S2ST** | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B-GGUF) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-9B-GGUF)（LLM 主干） | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B-FP8) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-9B-FP8)（完整管线） | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B-FP4) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-9B-FP4)（完整管线） |

## 推理

### 快速上手

#### 方式一：免费公网 API 快速调用（无需本地 GPU）

你可以直接免费调用公网 35B-A3B 模型接口，无需本地显卡环境。推荐使用官方零外部依赖 Python 脚本 [`inference/llm/call_api.py`](inference/llm/call_api.py)：

```bash
# 1. 命令行快速翻译（零外部依赖，标准库即开即用）
python inference/llm/call_api.py "你好，世界。今天天气不错，我们去公园散步吧。" --target en

# 2. 多模态图片翻译（无需 OCR，直接识别截图/照片/海报文字并翻译为指定语言）
python inference/llm/call_api.py --image path/to/screenshot.png --target zh

# 3. 沉浸式翻译（Immersive Translate）等浏览器插件配置（需启动本地代理）：
# 浏览器扩展受同源策略 (CORS) 与请求头限制，且需强制关闭思考输出，请在本地启动代理服务：
python inference/llm/call_api.py --serve
# 启动后在沉浸式翻译中配置：
# - 翻译服务: 自定义 / OpenAI
# - 接口地址 (API URL): http://127.0.0.1:8080/v1
# - 模型名称 (Model): Index-Translate-35B-A3B
# - API Key: 随意填写（如 index）

# 选项 A：标准 Chat Completions API（兼容 OpenAI 规范）
curl https://index-translate.bilibili.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Index-Translate-35B-A3B",
    "messages": [{"role": "user", "content": "请将以下文本翻译为英语，直接输出翻译结果，不要进行任何解释。\n\n你好，世界。"}]
  }'

# 选项 B：多模态图片翻译（OpenAI image_url 规范，支持 base64 data URL）
curl https://index-translate.bilibili.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "User-Agent: Index-Translate-Client/1.0" \
  -d '{
    "model": "Index-Translate-35B-A3B",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "请将图片中的英文翻译为中文。"},
          {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="}}
        ]
      }
    ]
  }'

# 选项 C：最新 OpenAI Responses API（适配 client.responses.create / POST /v1/responses）
curl https://index-translate.bilibili.com/v1/responses \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Index-Translate-35B-A3B",
    "input": "请将以下文本翻译为英语，直接输出翻译结果，不要进行任何解释。\n\n你好，世界。"
  }'
```

> [!TIP]
> 🖼️ **多模态图片翻译开箱即用（支持 Web Demo / Python 脚本 / API）！**  
> 基于原生视觉编码器，**零 OCR 依赖**，高保真还原版式与图文语境。  
> 👉 **[【图文使用教程】多模态图片翻译完整指南（含 API 调用、本地部署与实测案例）](docs/image_translate_zh.md)**

> [!TIP]
> 🌐 **想要在浏览器一键双语畅读网页？沉浸式翻译 (Immersive Translate) 开箱即用（支持 Windows / macOS / Linux）！**
> 针对浏览器插件特有的跨域保护 (CORS)、WAF 协议头以及大模型思维链 (CoT) 抑制需求，官方提供零配置本地桥接代理（Windows 用户可直接双击运行根目录 `run_proxy_windows.bat`）。
> 👉 **[【图文配置教程】沉浸式翻译对接 Index-Translate 完整指南（Windows / macOS / Linux，附实操截图与避坑）](docs/immersive_translate_zh.md)**

#### 方式二：本地私有化部署（vLLM）

先用 2B 文本模型完成一次翻译。需要 CUDA GPU 和支持 Qwen3.5 的 vLLM 版本，在终端中运行：

```bash
git clone https://github.com/bilibili/Index-Translate.git
cd Index-Translate
pip install -U vllm
pip install -r inference/llm/requirements.txt
vllm serve IndexTeam/Index-Translate-2B --host 127.0.0.1 --port 8000 --max-model-len 4096
```

在**另一个终端**进入同一仓库目录，执行：

```bash
python inference/llm/translate.py \
  "你好，世界。今天天气不错，我们去公园散步吧。" \
  --target en --model IndexTeam/Index-Translate-2B
```

已发布 2B 模型的一次实际输出为：

> Hello, world. The weather is nice today. Let's go for a walk in the park.

更多内容见[实测案例](inference/llm/cases/translate_cases.jsonl)、[文本推理](inference/llm/README_zh.md)及[提示词示例](docs/prompts_zh.md)。上面的 4,096 token 配置用于短文本示例；部署预设见下面的总表。

语音任务请进入对应的 [S2TT 字幕教程](inference/echo-s2tt/README_zh.md)或 [S2ST 配音教程](inference/echo-s2st/README_zh.md)。

### 指令遵循与约束翻译（硬约束 / 软约束）

Index-Translate 深度融合了指令遵循（instTrans）与结构化约束能力。模型不仅能高质量翻译，还支持**硬约束（格式保留、术语字典强干预）**与**软约束（文风语气、领域消歧）**，并通过 `translate.py` 和 `syllable_translate.py` 直接调用：

```bash
# 硬约束 1：术语强对照（-g / --glossary，自动组装为 instTrans 规范的【硬性要求】专名/术语对照）
python inference/llm/translate.py \
  "王平仲采用了更加昂贵的碳纤维材料。碳纤维的好处就是它抗裂缝。" \
  --target en -g "碳纤维:carbon fiber, 抗裂缝:crack resistance"

# 硬约束 2：格式与结构保护（-H / --hard，严格保留 JSON、CSV、Markdown、变量占位符不变）
python inference/llm/translate.py \
  '{"user_id": 1024, "event": "purchase", "message": "您的订单已支付完成。"}' \
  --target en -H "保留源文中的 JSON 格式标记不变"

# 软约束 1：文风与语体（-S / --soft，配合 -d / --genre 声明文体）
python inference/llm/translate.py \
  "今天下午的会议临时取消了，改天我们再碰一下商量。" \
  --target en -d "商务邮件" -S "调整为严谨、正式、礼貌的商务公文风格"

# 软约束 2：领域语境与多义词消歧（-S / --soft）
python inference/llm/translate.py \
  "The plant is operating at full capacity after the spring upgrade." \
  --target zh -d "工业制造" -S "语境为工业制造与重工厂房领域，准确消歧专有名词（如 plant 译为工厂而非植物）"

# 音节控制协同：Index-Homura 支持在严格控制目标音节数的同时遵循术语强约束
python inference/llm/syllable_translate.py \
  "我们今天去看电影吧" --syllables 7 --target en --glossary "电影:cinema"
```

> **instTrans 规范与约束类型说明：**
> - **规范化 Prompt**：客户端统一按 instTrans 评测基准格式自动拼装（`【源文】` + 编号列表 `1. 【硬性要求】...` / `2. 【注意】...` + 结尾指令）。
> - **硬约束（Hard Constraints）**：格式保护（JSON/CSV/代码/占位符）、术语指定（Glossary）、社交标记保护、音节排序。违背一项即判 0 分，训练采用硬门控保证执行。
> - **软约束（Soft Constraints）**：风格语气（正式/口语/文学/社交网感）、多义词消歧、跨句指代一致性、学术公式保护。渐进打分，兼顾译文地道与语义传达。
> - 完整实现与更多实测用例见[文本推理说明](inference/llm/README_zh.md)与[实测案例集](inference/llm/cases/instruction_cases.jsonl)。

### 默认推理参数

这张总表统一列出仓库客户端与发布 Echo 模型包的默认设置。Translate 包含 **2B / 9B / 35B-A3B（preview）**，其余家族包含 **2B / 9B**；同一家族各尺寸使用相同的解码参数。

**未设置**表示客户端继承后端／模型配置；**—**表示不适用。Echo 的文本生成参数用于转写和翻译，声音生成参数另列。

| 参数 | [Index-Translate](inference/llm/README_zh.md) | [Index-Homura](inference/llm/README_zh.md) | [Index-NativeLong](inference/llm/README_zh.md) | [Echo S2TT](inference/echo-s2tt/README_zh.md) | [Echo S2ST](inference/echo-s2st/README_zh.md) |
|---|---|---|---|---|---|
| 调用入口 | `translate.py` | `syllable_translate.py` | `doc_translate.py` | `s2tt.py` → 模型包 `infer.py` | `dub.py` → 模型包 `DubbingBridgeModel` |
| 默认权重 | 9B | 9B | 9B（`Index-Nailong`） | 2B | 本地 `./Index-Echo-S2ST-2B` |
| 文本解码 | 贪心 | 采样 | 贪心 | 贪心（`do_sample=False`） | 贪心（`do_sample=False`） |
| `temperature` | `0` | `0.3` | `0` | `0` | `0`（文本） |
| `top_p` | 未设置 | 未设置 | `1` | 未设置 | 未设置（文本） |
| `top_k` | 未设置 | 未设置 | `-1` | 未设置 | 未设置（文本） |
| `min_p` | 未设置 | 未设置 | `0` | 未设置 | 未设置（文本） |
| `presence_penalty` | 未设置 | 未设置 | `0` | — | — |
| `repetition_penalty` | 未设置 | 未设置 | `1` | 未设置 | 未设置（文本） |
| `seed` | 未设置 | 未设置 | `42` | 未设置 | `42`（声音） |
| 思考控制 | `enable_thinking=False` | `enable_thinking=False` | `enable_thinking=False` | 预填空 `<think>` 块 | 预填空 `<think>` 块 |
| 文本输出预算 | `max_tokens=1024` | `max_tokens=max(512, 3 * len(text))` | 不传 `max_tokens`，由服务端确定上限 | 每窗口 `max_new_tokens=2000` | `max_new_tokens=1024` |
| 文本停止条件 | 未设置 | 未设置 | `stop_token_ids=[248044, 248046]`；`ignore_eos=False` | Tokenizer EOS / `<\|im_end\|>` | Tokenizer EOS / `<\|im_end\|>` |
| 流式输出 | 否 | 否 | `stream=True` | 逐窗返回结果 | 声音生成 `stream=False` |
| `serve_vllm.sh` 窗口（输入 + 输出） | 2B / 9B：`32768`；无 35B 预设 | `32768` | 2B：`262144`；9B：`229376` | — | — |
| 默认语种／约束 | 源语种 `auto`，目标 `en` | 目标 `en`；必须传 `--syllables` | `zh-en` | `zh-en` | 必须传 `--lang`；源语种按 zh/en 判定 |
| 音频切窗／历史上下文 | — | — | — | `--max-win 60` 秒；`--ctx-k 5` 个先前窗口 | 建议单句 ≤30 秒；`chunk=False` |
| 声音采样器 | — | — | — | — | 固定实参 `sampling=25`；CosyVoice RAS 默认 `top_p=0.8`、`top_k=25` |
| 声音 token 预算 | — | — | — | — | 上限 `min(1500, 20 * m)`；下限 `2 * m` |
| 声音语速／采样率 | — | — | — | — | `speed=1.0`；`24000` Hz |
| 主要可调入口 | `--model`、`--instruction`、`--glossary`、`--temperature`、`--max-tokens` | `--model`、`--syllables`、`--glossary`、`--temperature`、`--max-tokens` | `--model`、`--direction`、`--max-tokens` | `--size`、`--temperature`、`--max-new-tokens`、`--max-win`、`--ctx-k`、`--glossary` | `--model-dir`、`--lang`；预算／seed 使用底层 API |

- **文本客户端：** 默认地址为 `http://127.0.0.1:8000/v1`，API key 为 `EMPTY`。用 `--base-url`／`--api-key` 或 `OPENAI_BASE_URL`／`OPENAI_API_KEY` 覆盖；`--model` 优先于 `INDEX_MODEL` 和默认权重。35B-A3B 需手动部署，再传 `--model IndexTeam/Index-Translate-35B-A3B-preview`。
- **预算：** Homura 的 `len(text)` 为输入去除首尾空白后的 Python 字符数。NativeLong 不传 `max_tokens` 时，由服务端确定输出上限，仍受上下文容量和服务端限制影响；传正数 `--max-tokens` 可显式指定上限。窗口包括完整提示词和生成结果，部署时可用 `--max-model-len` 覆盖。
- **Echo S2ST：** `m` 为对齐后的目标文本 token 数。`sampling=25` 是模型包代码中的固定实参，不是 CLI 开关。公共 `DubbingBridgeModel.dub` 不暴露 `seed` 或 token 预算；请使用[模型卡](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B#configurable-api-parameters)中的底层 `extract`／`synth` API。`chunk=True` 尚未实现。
- **口径：** 本表是日常推理默认值。技术报告的评测解码与窗口配置另见[评测说明](docs/evaluation_zh.md)。

## 精选案例

以下案例来自[官方 Demo](https://index-translate.bilibili.com/?p=/site/home.html#benchmark-cases)，用于展示具体样本中的输出。完整模型对照与任务设置见 Demo 和技术报告。

### 翻译内容，同时保留指定标签

**要求：** 将下面的 JSON 翻译为韩文，保留结构、星号和中文话题标签。

```json
{"title": "⭐2月13日例行维护公告⭐", "content": "#热血航线大和登场#"}
```

**Index-Translate-9B 输出：**

```json
{"title": "⭐2월 13일 정기 점검 공지⭐", "content": "#热血航线大和登场#"}
```

公告标题被翻译，用户指定的话题标签保持原样。[体验文本翻译](https://index-translate.bilibili.com/?p=/site/translate.html&lang=zh)。

### 多模态图片翻译（Vision）：软件 UI 与技术图表（零 OCR 依赖）

**要求：** 识别图像中的文字，深度结合视觉上下文与版面布局，端到端直接输出高质量译文。

| 图像类型 | 图像源文字 (英文) | Index-Translate-35B 译文 (中文) | 优势特性 |
|---|---|---|---|
| **软件设置截图** | "Enable hardware-accelerated GPU scheduling (requires restart)" | 启用硬件加速 GPU 计划（需要重启） | 精准识别系统 UI 选项，语义贴切 |
| **技术流程图** | "Client -> Load Balancer -> Worker Pool (Least-Conn Routing)" | 客户端 → 负载均衡器 → 工作节点池（最小连接数路由） | 识别流程指向，保留系统架构术语 |
| **实景街道路牌** | "Pedestrian Crossing Ahead · Speed Limit 30 mph" | 前方行人过街通道 · 限速 30 英里/小时 | 复杂自然实景抗畸变，度量单位标准转换 |

无需配置任何 OCR 工具链，直接在 [在线 Demo](https://index-translate.bilibili.com/?p=/site/translate.html) 粘贴或上传图片即可体验。详细教程见 [多模态图片翻译指南](docs/image_translate_zh.md)。

### 翻出社区表达中的意思

**原文：** 狒瘾犯了就去打。在这个游戏社区语境中，“狒瘾”指想玩《最终幻想 XIV》的劲头又上来了。

| 模型 | 英文译文 |
|---|---|
| Index-Translate-9B | When the FFXIV itch hits, just go play. |
| Index-Translate-2B | Go play when my FFXIV addiction kicks in. |
| Hy-MT2-7B | If you get monkey addiction, go fight. |

### 按指定音节数调整译文

**原文：** 生活两天，是一种什么体验。同一句话设置三个目标长度，Index-Homura-9B 给出不同措辞：

| 目标 / 实际音节数 | 英文译文 |
|---|---|
| 10 / 10 | to live for two days. What would that be like? |
| 14 / 14 | What would it be like to live there for two days, I wonder? |
| 18 / 18 | What would it be like to live there for two days, trying to get by somehow? |

这三个样例均命中目标；整体上音节控制仍是近似约束，实际配音时长还受语速与停顿影响。[体验 Index-Homura](https://index-translate.bilibili.com/?p=/site/syllable.html&lang=zh)。

### 长文翻到后面，人名仍然一致

在一篇约 32K tokens 的奇幻文本中，“王妃”是人物姓名。下表对比原生全文翻译，与同一 9B 模型采用相邻上下文及自动词表的分块翻译。

| 原文位置 | Index-NativeLong-9B 原生全文 | 同一 9B 分块翻译 |
|---|---|---|
| 31.3% | Mentor Wang Fei | Instructor Wangfei |
| 56.6% | Wang Fei | the Dean |
| 84.8% | Wang Fei | The Queen Consort |

位置按原文字符计算。原生全文译文在这些位置保持了人名；官网也展示了使用外部词表修复分块结果的情况。[体验 Index-NativeLong](https://index-translate.bilibili.com/?p=/site/doc.html&lang=zh)。

### 观看语音翻译演示

![Index-Echo 评测](docs/assets/echo_benchmark_overview.zh.svg)

S2ST 图对比落地版 2B、级联 Pipeline 与 SeamlessM4T-v2，与报告中的六方向同规模对比口径不同；SeamlessM4T-v2 未做音色克隆。

<table>
<tr><th>语音配音</th><th>多语言字幕</th></tr>
<tr>
<td align="center"><a href="https://index-translate.bilibili.com/?p=/site/assets/blog/echo-demo.mp4"><img src="docs/assets/echo-s2st.png" height="180" alt="观看 Index-Echo 英文视频转日语配音演示"></a></td>
<td align="center"><a href="https://index-translate.bilibili.com/?p=/site/assets/blog/echo-demo-s2tt.mp4"><img src="docs/assets/echo-s2tt.png" height="180" alt="观看 Index-Echo 多语言字幕演示"></a></td>
</tr>
<tr><td>英文视频搭配日语配音</td><td>同一视频搭配多种语言的译文</td></tr>
</table>

点击预览图观看视频，或[进入 Index-Echo](https://index-translate.bilibili.com/?p=/site/index.html&lang=zh)体验。官网演示与已发布推理接口的语言覆盖有所不同，发布接口支持范围见[模型下载表](#模型下载)。

## 评测结果

![文本翻译最新评测](docs/assets/text_benchmark_overview.zh.svg)

柱状图沿用新版 Demo 的对比模型和汇总方式，*35B-A3B 为 preview。指令翻译 Quality 为 instTrans 质量分与 IFMTBench XCOMET-XXL 的均值，IFscore 为两项指令遵循分数的均值；下表仍分别列出各项原始指标。

下面分别展示通用文本翻译、小语种通用翻译与小语种指令遵循结果。FLORES 使用 COMET-22，WMT26 使用 judge 分数；instTrans 分别统计译文质量和指令遵循，MEME 关注社区与文化表达的翻译质量。下方第一张表各列均为越高越好，不同列的量纲不宜直接比较。

| 模型 | FLORES ↑ | WMT26 ↑ | instTrans 质量 ↑ | instTrans 指令遵循 ↑ | MEME ↑ |
|---|---:|---:|---:|---:|---:|
| **Index-Translate-35B-A3B (preview)** | 0.8794 | 76.76 | 0.6901 | 0.8336 | 0.7405 |
| **Index-Translate-9B** | 0.8789 | 75.35 | 0.6771 | 0.8209 | 0.7387 |
| **Index-Translate-2B** | 0.8655 | 60.26 | 0.5391 | 0.7569 | 0.6443 |
| Hy-MT2-7B | 0.8747 | 60.51 | 0.5143 | 0.6079 | 0.5139 |
| Hy-MT2-30B-A3B | 0.8787 | 66.81 | 0.5725 | 0.6415 | 0.5812 |
| DeepSeek-V4.1-Flash | 0.8762 | 83.55 | 0.6068 | 0.6374 | 0.7424 |
| GPT-5.6-Sol | 0.8650 | 89.10 | 0.6902 | 0.7624 | 0.7194 |
| Gemini 3.5 Flash Lite | 0.8750 | 79.52 | 0.6068 | 0.6374 | 0.7034 |

### 小语种翻译与指令遵循

FLORES_minor_pair 衡量小语种通用翻译，instTrans_minor 分别衡量译文质量与指令遵循。off-target 为未使用目标语言的输出比例，越低越好；其余指标越高越好。加粗表示本表各列最优值。

| 模型 | FLORES_minor_pair<br>COMET-22 ↑ | FLORES_minor_pair<br>XCOMET-XXL ↑ | FLORES_minor_pair<br>off-target ↓ | instTrans_minor<br>Quality ↑ | instTrans_minor<br>IFscore ↑ | instTrans_minor<br>off-target ↓ |
|---|---:|---:|---:|---:|---:|---:|
| **Index-Translate-35B-A3B (preview)** | 0.8168 | 0.7164 | 2.4% | 0.5151 | 0.7715 | 4.05% |
| **Index-Translate-9B** | 0.7992 | 0.6805 | 4.0% | 0.5222 | **0.7725** | **3.47%** |
| **Index-Translate-2B** | 0.7377 | 0.4817 | 4.2% | 0.3050 | 0.6586 | 3.97% |
| Hy-MT2-7B | 0.4626 | 0.3334 | 35.7% | 0.1121 | 0.2405 | 45.40% |
| Hy-MT2-30B-A3B | 0.6746 | 0.5359 | 14.5% | 0.2246 | 0.4449 | 15.47% |
| DeepSeek-V4.1-Flash | **0.8333** | **0.7297** | **1.3%** | 0.4793 | 0.5854 | 5.73% |
| GPT-5.6-Sol | 0.7669 | 0.6918 | 10.4% | **0.5757** | 0.6866 | 7.73% |
| Gemini 3.5 Flash Lite | 0.8122 | 0.6995 | 3.3% | 0.3927 | 0.5584 | 12.18% |

在三个 Index-Translate 模型中，35B-A3B (preview) 的 FLORES_minor_pair COMET-22 和 XCOMET-XXL 最高，分别为 **0.8168 / 0.7164**，off-target 为 **2.4%**。在 instTrans_minor 上，Index-Translate-9B 在全部对比模型中取得最高 IFscore（**0.7725**）和最低 off-target（**3.47%**），译文质量为 **0.5222**。

[完整评测表](docs/evaluation_zh.md)保留全部对比模型，以及完整小语种指标、WMT24++、IFMTBench、垂类均值、通用能力、语音、SandGlass 和长文档结果。详细设置与分析见[技术报告](https://arxiv.org/abs/2609.40181)。

专门模型方面，Index-Homura-9B 在 SandGlass 上有 **81.92%** 的输出与目标音节数偏差不超过 10%；Index-NativeLong-9B 在 GuoFeng / BWB / Books 上的得分分别为 **0.7891 / 0.7683 / 0.8848**。完整表格同时给出译文质量权衡和评测说明。

### Index-Homura 与 Index-NativeLong

![Index-Homura 评测](docs/assets/homura_benchmark_overview.zh.svg)

沿用 Demo 的 SandGlass 综合分与音节控制命中率；综合分与明细表中的独立翻译质量指标不同。

![Index-NativeLong 64K 评测](docs/assets/nativelong_benchmark_overview.zh.svg)

GuoFeng 与 BWB Track A3 的 64K 中文侧 token 档位结果。

## Benchmarks

数据与元数据收录于 [🤗 Index-Translate Benchmarks 合集](https://huggingface.co/collections/IndexTeam/index-translate-benchmarks-6ac16fee5057f40abd7d31b7)，评测脚本、固定版本的数据下载工具和运行说明见 [benchmarks/](benchmarks/README.md)。

| Benchmark | 公开内容 | 数据下载 | 评测代码与说明 |
|---|---|---|---|
| **instTrans** | 3,000 条翻译指令任务；10 类约束 | [🤗 InstTrans-Bench](https://huggingface.co/datasets/IndexTeam/InstTrans-Bench) | [insttrans](benchmarks/insttrans/README.md) |
| **MEME** | 3,638 条中译英样例；703 个词语、857 个词义 | [🤗 Meme-Translation-Bench](https://huggingface.co/datasets/IndexTeam/Meme-Translation-Bench) | [meme](benchmarks/meme/README.md) |
| **SandGlass** | 3,600 条案例：300 句字幕 × 4 种目标语言 × 3 档长度预算 | [🤗 Sandglass-Bench](https://huggingface.co/datasets/IndexTeam/Sandglass-Bench) | [sandglass](benchmarks/sandglass/README.md) |
| **NAtIveLong** | BWB / GuoFeng 各 84 条长文档案例的元数据、评测代码和获取说明 | [🤗 NAtIveLong](https://huggingface.co/datasets/IndexTeam/NAtIveLong) | [nativelong](benchmarks/nativelong/README.md) |

NAtIveLong 不包含小说原文或参考译文；BWB 需自行获取官方语料，GuoFeng 提供本地重建工具。以上 instTrans 发布包不包含评测表中的 2,793 条低资源扩展任务。评测脚本保留原有 prompt；审查修复与验证范围记录在各目录的 `RELEASE_REVIEW.md`，历史成绩未重新评测。各 benchmark 的许可分别见其目录，不能直接套用仓库根目录许可。

[完整评测设置](docs/evaluation_zh.md)与 [IFMTBench 处理说明](docs/evaluation_zh.md#ifmtbench-处理说明)另行列出。

## 应用工具

- **[沉浸式翻译配置教程](docs/immersive_translate_zh.md)：** 图文教程，支持 Windows（提供一键 `.bat` 启动脚本）/ macOS / Linux，通过公网 35B 免费 API 或本地模型为「沉浸式翻译 (Immersive Translate)」插件提供高品质网页双语对照翻译。
- **[内置浏览器扩展](extension/README_zh.md)：** 官方内置极简网页翻译插件，支持 Chrome、Edge 与 Firefox，纯原生 JS 零构建。
- **[视频配音管线](video-dub/README_zh.md)：** 完成音频提取、人声分离、语音切分、翻译配音及时间轴对齐，输出配音视频。

## 交流社区

欢迎加入 [QQ 交流群（960123527）](https://qm.qq.com/q/xSASqaiEGA)，交流使用体验、反馈问题与建议。也可以扫描下方二维码加入群聊。

<p align="center"><a href="https://qm.qq.com/q/xSASqaiEGA"><img src="docs/assets/qq-group.jpg" width="320" alt="QQ 交流群 960123527 加群二维码"></a></p>

## 论文与引用

三篇论文集中收录于 [🤗 Hugging Face Papers 合集](https://huggingface.co/collections/IndexTeam/index-translate-papers-6abe1f5452920941ea0682d9)。

- **Index-Translate：** [A Multilingual Translation Model Family — Text, Speech, Controlled Dubbing, and Long-Document Translation](https://arxiv.org/abs/2609.40181) · [🤗 HF Papers](https://huggingface.co/papers/2609.40181)
- **HOMURA：** [Taming the Sand-Glass for Time-Constrained LLM Translation via Reinforcement Learning](https://arxiv.org/abs/2601.10187) · [🤗 HF Papers](https://huggingface.co/papers/2601.10187)
- **RIVAL：** [Reinforcement Learning with Iterative and Adversarial Optimization for Machine Translation](https://arxiv.org/abs/2506.05070) · [🤗 HF Papers](https://huggingface.co/papers/2506.05070)

如果使用本系列模型或相关方法，欢迎引用对应论文：

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

## 许可证与反馈

[Apache-2.0](LICENSE)。欢迎通过 [GitHub Issues](https://github.com/bilibili/Index-Translate/issues)反馈问题与建议。
