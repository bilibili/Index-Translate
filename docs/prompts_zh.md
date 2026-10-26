# 提示词示例 (Prompt Examples)

[English](prompts.md) · [返回 README](../README_zh.md)

*注：以下示例中源/目标语言请使用完整语言名（如 英语/English）。所有模板只输出译文，不带额外解释。*

---

## 一、速查总表

| 类型 | 中文提示词 | 英文提示词 |
|---|---|---|
| **默认翻译**（Index-Translate） | 请将以下文本翻译为 `{目标语言}`，直接输出翻译结果，不要进行任何解释：<br><br>`{源文本}` | Translate the following text into `{target_lang}`. Output the translation directly, without any explanation:<br><br>`{source_text}` |
| **术语/约束翻译**（Index-Translate） | 见下方 [instTrans 结构化规范模板](#二-强约束与指令遵循翻译规范insttrans-结构化模板) | See [instTrans Canonical Constrained Template](#二-强约束与指令遵循翻译规范insttrans-结构化模板) below |
| **结构化数据**（Index-Translate） | 将下方 `{格式}` 数据翻译为 `{目标语言}`：仅翻译面向用户的文本字段，严禁改动结构、键名与占位符：<br><br>`{源文本}` | Translate the following `{format_type}` data into `{target_lang}`: translate only user-facing text fields; never alter the structure, keys, or placeholders:<br><br>`{source_text}` |
| **音节受控**（Index-Homura） | 请将以下文本翻译为 `{目标语言}`，译文严格控制在 `N` 个音节。直接输出翻译结果，不要进行任何解释：<br><br>`{源文本}` | Translate the following text into `{target_lang}`, strictly within `N` syllables. Output the translation directly, without any explanation:<br><br>`{source_text}` |
| **长文档**（Index-NativeLong） | 直接粘贴完整文档，使用固定方向模板（见 [inference/llm/prompts](../inference/llm/prompts)），一次生成完整译文 | Paste the complete document with the fixed per-direction template (see [inference/llm/prompts](../inference/llm/prompts)); the full translation is produced in one generation |

---

## 二、 强约束与指令遵循翻译规范（instTrans 结构化模板）

Index-Translate 深度对齐了指令遵循翻译体系（instTrans Benchmark）。当需要**术语强干预、格式结构保护、免译词原样保留或风格语气调整**时，请使用经过强化学习对齐的标准结构化槽位模板，以保证模型 100% 正确遵循。

### 1. 规范模板结构

#### 中文标准模板（推荐，遵循度最高）
```text
请将以下{源语言}{文体}翻译成{目标语言}，并且严格遵循所有约束要求。

【源文】
{源文本}

【约束要求】
1. 【硬性要求】...
2. 【硬性要求】...
3. 【注意】...

只输出译文，不要有任何额外说明。
```

*(当文体未指定时可填“文本”；源语言如不确定可省略)*

#### 英文标准模板
```text
Please translate the following text into {target_lang} and strictly follow all constraints.

[Source]
{source_text}

[Constraints]
1. [Hard Constraint] ...
2. [Hard Constraint] ...
3. [Note] ...

Output only the translation without any explanation.
```

---

## 三、 常见约束指令编写速查表

在【约束要求】中，约束规则按类型分为**硬约束（【硬性要求】）**与**软约束（【注意】）**：

| 场景 | 约束语法与示例 | 说明 |
|---|---|---|
| **术语强制对照** | `1. 【硬性要求】专名/术语对照: 碳纤维→carbon fiber、抗裂缝→crack resistance` | 严格保证术语输出为指定译名，多项用顿号或分号隔开。 |
| **免译词/专名锁定** | `1. 【硬性要求】专名/术语对照: 我喜欢→我喜欢` | **高频自然语言词汇免译必备**。例如需锁定 `<span translate="no">我喜欢</span>` 时，声明等值对照可 100% 抑制翻译。 |
| **HTML / 格式保留** | `1. 【硬性要求】保留源文中的 HTML 格式标记不变` | 保留 `<div>`、`<span>`、`<br>` 等标签语法，仅翻译其自然语言内容。 |
| **代码与标签保护** | `1. 【硬性要求】<code> 标签内的内容保持原样，不要翻译`<br>`2. 【硬性要求】反引号（\`）内的代码片段保持原样，不要翻译` | 保护内联代码、HTML `<code>` 标签内部标识符或函数名不被改动。 |
| **变量与占位符保护** | `1. 【硬性要求】保留源文中的占位符 {v0}、{v1} 不变` | 系统变量、参数占位符（如 `%s`、`{user_name}`）原样保留。 |
| **文体与风格控制** | `1. 【注意】译文保持严谨、正式、礼貌的商务公文风格` | 软约束：支持商务公文、随性口语、社交网络网感、典雅文学等。 |
| **多义词领域消歧** | `1. 【注意】消除歧义——语境为工业制造领域，plant 译为工厂而非植物` | 明确行业语境，使多义词落地到准确的专业词义。 |
| **社交标记保护** | `1. 【硬性要求】保留以下社交元素不变: @用户名、#话题#、[表情代码]` | 适用于社交媒体、弹幕与评论翻译。 |

---

## 四、 最佳实践：HTML 免译标签（`translate="no"`）与占位符处理

### 为什么在 Prompt 中直接用自然语言写“不要翻译某标签内的文字”可能失效？
在翻译大模型的自回归解码中，HTML 标签（如 `<span>`）具有强烈的**“保留标签骨架，翻译其包裹的正文”**归纳偏置。若被包裹的内容是高频日常短语（如“我喜欢”），模型生成的先验概率极容易覆盖笼统的自然语言软提示（如 *“Treat every span as an immutable placeholder”*），进而强行把内容译为 *“I like”*。

针对需要精确免译的场景，推荐以下两种标准解法：

#### 方法 1：提示词显式术语锁定（无需改动工程代码，仅调整 Prompt）
利用 Index-Translate 的术语映射机制，将待免译内容显式列入等值术语对照：
```text
请将以下文本翻译成英语，并且严格遵循所有约束要求。

【源文】
<span translate="no">我喜欢</span>花蓮的山海澎湖的潮汐

【约束要求】
1. 【硬性要求】保留源文中的 HTML 格式标记不变
2. 【硬性要求】专名/术语对照: 我喜欢→我喜欢

只输出译文，不要有任何额外说明。
```
**实测输出：**
`<span translate="no">我喜欢</span> the mountains and seas of Hualien, and the tides of Penghu.`

#### 方法 2：工业级 CAT 占位符掩码方案（生产系统最健壮推荐）
在本地化与翻译流水线工程实践中，最推荐轻量前后置处理：
1. **预处理**：使用正则将 `<span translate="no">.*?</span>` 提取并替换为 `{v0}`、`{v1}`。
2. **翻译调用**：
   ```text
   请将以下文本翻译为 英语。要求：保留原文占位符 {v0}：

   {v0}花蓮的山海澎湖的潮汐
   ```
3. **后处理**：将模型返回译文中的 `{v0}` 还原回 `<span translate="no">我喜欢</span>`。
该方案完全避免模型对免译词产生任何翻译幻觉，且能减少推理生成的 Token 消耗。

---

各家族的解码默认值与输出预算统一见[默认设置总表](../README_zh.md#默认推理参数)。环境安装和可运行命令见[文本推理文档](../inference/llm/README_zh.md)。
