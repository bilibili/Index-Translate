# llm · 文本翻译大模型（Translate / NativeLong / Homura）

[English](README.md)

Translate、NativeLong、Homura 三个家族的客户端脚本、部署预设、固定 prompt 模板和实测用例。
它们都走 OpenAI chat completions 协议——用 vLLM（推荐）、SGLang 或任何兼容栈起服务，然后把脚本指过去即可。

Index-NativeLong 沿用已发布的 `IndexTeam/Index-Nailong-*` 模型 ID 与 `nailong-*` 部署预设。Index-Translate 文本模型覆盖 150 种语言；客户端未映射的语言代码请改用完整语言名称。

## 起服务

```bash
pip install -U vllm     # 需要带 Qwen3.5 支持的版本（实测 0.29）

./serve_vllm.sh translate-9b    # IndexTeam/Index-Translate-9B，端口 :8000
./serve_vllm.sh translate-2b
./serve_vllm.sh nailong-9b      # 长文档，随包 config 上限 229376
./serve_vllm.sh nailong-2b      # 长文档，262144
./serve_vllm.sh homura-9b       # 音节控制
./serve_vllm.sh homura-2b
```

多余参数透传给 `vllm serve`，例如
`./serve_vllm.sh nailong-9b --tensor-parallel-size 4 --data-parallel-size 2`。

显存参考（bf16）：2B ≈ 8 GB，9B ≈ 24 GB，长上下文另需 KV cache。

## 调用

### 免费公网 API 调用与沉浸式翻译本地代理

无需本地显卡，可直接通过零依赖脚本 [`call_api.py`](call_api.py) 调用线上 **Index-Translate-35B-A3B**：

```bash
# 命令行快速调用（标准库即开即用，支持 -t 指定语种、--stream 流式、-g 术语表、--instruction 约束等）
python call_api.py "你好，世界。" --target en

# 沉浸式翻译（Immersive Translate）等浏览器插件本地代理服务（Windows 用户可直接双击运行 run_proxy_windows.bat）
python call_api.py --serve
```

> 📖 **沉浸式翻译图文教程**：沉浸式翻译等浏览器插件直连公网端点时，受限于浏览器跨域限制 (CORS)、WAF 保护以及思维链 (CoT) 格式要求，请在本地运行 `python call_api.py --serve`。详细图文配置步骤与常见问题排查见：**[【图文教程】沉浸式翻译配置指南](../../docs/immersive_translate_zh.md)**。

### 本地私有化部署模型调用

```bash
pip install openai httpx

# 1. 通用基础翻译（Index-Translate）
python translate.py "你好，世界。今天天气不错。" --target en
python translate.py "The quick brown fox..." --source en --target zh \
    --model IndexTeam/Index-Translate-2B

# 2. instTrans 格式化硬约束：术语指定（-g / --glossary，自动格式化为【硬性要求】专名/术语对照）
python translate.py "王平仲采用了更加昂贵的碳纤维材料。碳纤维的好处就是它抗裂缝。" --target en \
    -g "碳纤维:carbon fiber, 抗裂缝:crack resistance"

# 3. instTrans 格式化硬约束：结构化数据与格式保留（-H / --hard）
python translate.py '{"user_id": 1024, "message": "您的订单已支付完成。"}' --target en \
    -H "保留源文中的 JSON 格式标记不变"

# 4. instTrans 格式化软约束：文风与语体（-S / --soft）+ 文体声明（-d / --genre）
python translate.py "今天下午的会议临时取消了，改天我们再碰一下商量。" --target en \
    -d "商务邮件" -S "调整为严谨、正式、礼貌的商务公文风格"

# 5. instTrans 格式化软约束：领域消歧（-S / --soft）
python translate.py "The plant is operating at full capacity after the spring upgrade." --target zh \
    -d "工业制造" -S "语境为工业制造与重工厂房领域，准确消歧专有名词（如 plant 译为工厂而非植物）"

# 6. 多条约束组合传参（支持多次 -H 和 -S）
python translate.py '{"1": "回复 @零岭七 :乱说，外购不算消费啦？[藏狐] #每日一喵#"}' --target en \
    -d "评论" \
    -H "保留源文中的 JSON 格式标记不变" \
    -H "保留以下社交元素不变: @零岭七、[藏狐]、#每日一喵#"

# 7. 音节受控翻译（Index-Homura，支持结合术语约束）
python syllable_translate.py "我们今天去看电影吧" --syllables 7 --target en \
    --glossary "电影:cinema"

# 8. 长文档翻译（Index-NativeLong，固定方向模板）
python doc_translate.py novel.txt --direction zh-en -o novel.en.txt
python doc_translate.py paper.txt --direction en-zh --model IndexTeam/Index-Nailong-2B
```

脚本默认 `--base-url http://127.0.0.1:8000/v1`，可用 `--base-url/--model`（或环境变量 `OPENAI_BASE_URL`/`INDEX_MODEL`）指向任意服务器。

---

## 指令遵循与约束翻译（Instruction Following）

Index-Translate 在训练中通过 Rubric-as-Reward (RaR) 和 GRPO 联合优化翻译质量与指令遵循能力，其奖励函数为：
$$R_{\mathrm{inst}} = g_{\mathrm{lang}} \cdot g_{\mathrm{hard}} \cdot \bigl(q_{\mathrm{qual}} + q_{\mathrm{soft}}\bigr)$$

评测在官方 **instTrans Benchmark**（包含 3,000 个多场景多语种真实评测用例）与 **IFMTBench** 上展开，全面支持以下 **10 种软硬约束**：

### 1. 硬约束（Hard Constraints, $g_{\mathrm{hard}}$ 门控）
硬约束为一票否决制二进制指标（0 或 1），任何一项违背直接判定该用例不达标：
- **术语强对照（term_compliance）**：严格按照给定的映射表输出目标译名。可直接通过 `-g / --glossary "源词:目标词"` 传入，或传入 JSON 字典文件路径，自动组装为 `【硬性要求】专名/术语对照: A→B、C→D`。
- **结构与格式保护（format_preserve）**：在翻译 JSON、CSV、Markdown 表格、HTML 时，严格保护键名、标签、分隔符、数字、布尔值，仅翻译面向用户的文本内容。
- **变量与占位符保护（format_preserve）**：在系统提示、文案本地化中，严格保留 `{user_name}`、`%s`、`[123456]`、URL 链接等变量不被破坏。
- **社交元素保护（social_preserve）**：在翻译社媒动态、弹幕或评论时，原样保留 `@用户名`、`#话题#`、`[表情代码]` 等社交标记。
- **版式与排版保留（layout_break）**：保留源文的分段、换行、缩进及列表对齐。
- **音节长度排序（syllable_order）**：在多句字幕配音中，时长较短的句子译文音节数也必须相应较短。

### 2. 软约束（Soft Constraints, $q_{\mathrm{soft}}$ 连续评分）
软约束关注语义贴合度、行文自然度与语境适配（由 LLM Judge 按 0 / 0.5 / 1 打分）：
- **文体风格与语气（style_consistency）**：正式商务公文（Formal）、日常随性口语（Casual）、海外社交网络网感（Viral / Gen-Z）、文学典雅（Literary）等风格自由切换。
- **领域语境消歧（context_disambiguate）**：输入多义词（如 Plant、Spring、Cell、Crane）时，通过声明领域语境（工业制造 / 温室农业 / 港口工程 / 软件架构），模型能精准选取行业地道译法。
- **指代一致性与代词消解（coref_resolution）**：在多角色多主语文本中明确代词指代（他/她/它），避免跨句角色指代混淆。
- **跨句术语全文统一（term_cross_sentence）**：在篇章级或多句对话中，核心术语全局统一，杜绝同词异译。
- **学术与公式格式保护（academic_format_preserve）**：在学术论文中完整保留 LaTeX 公式（`$...$`、`\[...\]`）、引用标号（`[@citation]`）与命令，仅翻译正文。

### 3. 音节控制与术语协同（Homura Syllable Control with Glossary）
配音与字幕专用模型 **Index-Homura** 不仅支持目标音节数控制（如 `--syllables 7`），**同样支持术语强约束**（`--glossary`）。模型能在紧凑的音节预算下，动态调度虚词与句式，既保证指定术语 100% 出现，又精准贴合目标音节预算。

---

## Prompt 规范

解码与部署默认值统一见[默认设置总表](../../README_zh.md#默认推理参数)。客户端自动根据传入的约束选项组装为与模型训练和官方评测完全一致的 **instTrans 规范格式**：

- **Translate（instTrans 格式化带约束 Prompt）**：
  当指定 `-H` / `-S` / `-g` / `-i` 约束时自动生成：
  ```text
  请将以下{源语言}{文体}翻译成{目标语言}，并且严格遵循所有约束要求。

  【源文】
  {source_text}

  【约束要求】
  1. 【硬性要求】...
  2. 【注意】...

  只输出译文，不要有任何额外说明。
  ```
  *(当源文为 JSON 字典且包含格式保留约束时，结尾会自动替换为 instTrans 标准的 JSON 输出指令)*

- **Translate（基础无约束翻译）**：
  ```text
  请将以下{源语言}文本翻译为{目标语言}，直接输出翻译结果，不要进行任何解释。

  {source_text}
  ```
  （`auto` 时省略源语种）。

- **Homura（音节受控 + 可选术语）**：
  ```text
  请将以下文本翻译为{目标}，译文严格控制在 N 个音节。要求：严格遵守术语映射表【{术语 -> 译名}】。直接输出翻译结果，不要进行任何解释。

  {text}
  ```

- **NativeLong（长文档）**：
  固定方向模板（`prompts/nailong_{zh-en,en-zh,zh-ja,ja-zh}.txt`，把唯一的 `（在这里放入需要翻译的完整…原文）` 占位符替换为全文）。

---

## 用例

- [`cases/translate_cases.jsonl`](cases/translate_cases.jsonl)：基础多语言短文本评测用例。
- [`cases/instruction_cases.jsonl`](cases/instruction_cases.jsonl)：收录覆盖 instTrans 10 大软硬约束（术语对照、JSON/CSV 格式保护、占位符变量保护、社媒元素、正式/网感文风对比、领域多义词消歧、跨句术语一致性、学术公式保护、音节+术语协同）的真实运行样本。
- [`cases/doc_cases.jsonl`](cases/doc_cases.jsonl)：长文档真实输入输出。
- [`cases/syllable_cases.jsonl`](cases/syllable_cases.jsonl)：音节控制基准用例。
