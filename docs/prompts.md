# Prompt Examples

[中文](prompts_zh.md) · [Back to README](../README.md)

*Note: in the following examples, use full language names (e.g. 英语/English). All templates output the translation only, with no extra explanation.*

---

## 1. Quick Reference Table

| Type | Chinese prompt | English prompt |
|---|---|---|
| **Default translation** (Index-Translate) | 请将以下文本翻译为 `{target_lang}`，直接输出翻译结果，不要进行任何解释：<br><br>`{source_text}` | Translate the following text into `{target_lang}`. Output the translation directly, without any explanation:<br><br>`{source_text}` |
| **Terminology / constrained translation** (Index-Translate) | 见 [instTrans 结构化规范模板](prompts_zh.md#二-强约束与指令遵循翻译规范insttrans-结构化模板) | See [instTrans Canonical Constrained Template](#2-canonical-constrained-translation-insttrans-template) below |
| **Structured data** (Index-Translate) | 将下方 `{format_type}` 数据翻译为 `{target_lang}`：仅翻译面向用户的文本字段，严禁改动结构、键名与占位符：<br><br>`{source_text}` | Translate the following `{format_type}` data into `{target_lang}`: translate only user-facing text fields; never alter the structure, keys, or placeholders:<br><br>`{source_text}` |
| **Syllable-controlled** (Index-Homura) | 请将以下文本翻译为 `{target_lang}`，译文严格控制在 `N` 个音节。直接输出翻译结果，不要进行任何解释：<br><br>`{source_text}` | Translate the following text into `{target_lang}`, strictly within `N` syllables. Output the translation directly, without any explanation:<br><br>`{source_text}` |
| **Long document** (Index-NativeLong) | 直接粘贴完整文档，使用固定方向模板（见 [inference/llm/prompts](../inference/llm/prompts)），一次生成完整译文 | Paste the complete document with the fixed per-direction template (see [inference/llm/prompts](../inference/llm/prompts)); the full translation is produced in one generation |

---

## 2. Canonical Constrained Translation (instTrans Template)

Index-Translate is deeply aligned with the `instTrans Benchmark` instruction-following system. When you need **terminology enforcement, structural/format preservation, untranslatable text protection, or stylistic adjustments**, use the canonical slot-based template below to ensure 100% adherence.

### Template Formats

#### Chinese Standard Template (Highest Adherence)
```text
请将以下{源语言}{文体}翻译成{目标语言}，并且严格遵循所有约束要求。

【源文】
{source_text}

【约束要求】
1. 【硬性要求】...
2. 【硬性要求】...
3. 【注意】...

只输出译文，不要有任何额外说明。
```

*(If genre is not specified, you can use `文本`; source language can be omitted if auto-detected)*

#### English Standard Template
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

## 3. Constraint Directives Cheat Sheet

Under `[Constraints]`, rules are divided into **Hard Constraints (`[Hard Constraint]` / `【硬性要求】`)** and **Soft Constraints (`[Note]` / `【注意】`)**:

| Scenario | Directive Syntax & Example | Description |
|---|---|---|
| **Terminology Glossary** | `1. [Hard Constraint] Terminology mapping: carbon fiber -> 碳纤维, crack resistance -> 抗裂缝` | Strictly enforces designated translations. Delimit multiple items with commas or semicolons. |
| **Untranslatable Text / Span Lock** | `1. [Hard Constraint] Terminology mapping: 我喜欢 -> 我喜欢` | **Essential for locking untranslatable words**. For instance, protecting `<span translate="no">我喜欢</span>` by setting an identity mapping completely suppresses translation. |
| **HTML / Format Preservation** | `1. [Hard Constraint] Preserve all HTML format tags in the source text` | Keeps `<div>`, `<span>`, `<br>`, and other markup syntax intact while translating user-facing content. |
| **Code & Tag Protection** | `1. [Hard Constraint] Content inside <code> tags must be kept as-is, do not translate`<br>`2. [Hard Constraint] Code snippets inside backticks (\`) must be kept as-is, do not translate` | Preserves inline identifiers, function names, and code tokens. |
| **Placeholders & Variables** | `1. [Hard Constraint] Preserve placeholders {v0}, {v1} in the source text` | Preserves system variables and formatting tokens (`%s`, `{user_name}`) untouched. |
| **Style & Register Control** | `1. [Note] Maintain a formal, rigorous, and polite business document tone` | Soft constraint: supports Formal, Casual, Social Media (Viral / Gen-Z), and Literary styles. |
| **Domain Disambiguation** | `1. [Note] Disambiguation -- domain is industrial manufacturing; translate 'plant' as factory rather than vegetation` | Clarifies specialized context for polysemous words. |
| **Social Media Tags** | `1. [Hard Constraint] Keep social elements unchanged: @username, #topic#, [emojis]` | For social media posts, comments, and danmaku. |

---

## 4. Best Practices: HTML Untranslatable Tags (`translate="no"`) & Placeholders

### Why does plain natural language instruction like "do not translate text inside span" fail?
During bilingual pre-training on massive web corpora, language models develop a strong **inductive bias for HTML tags**: *"preserve the tag wrapper, but translate the inner natural language text"*. When the inner content consists of high-frequency everyday words (e.g. `我喜欢`), the generative decoding prior easily overrules generic negative prompt instructions like *"Treat every span as an immutable placeholder"*, causing the model to output `I like`.

To achieve deterministic protection, we recommend the following two proven methods:

#### Method 1: Prompt-Level Identity Terminology Mapping (No Code Changes)
Leverage Index-Translate's terminology alignment by explicitly registering the untranslatable text as an identity mapping:
```text
Please translate the following text into English and strictly follow all constraints.

[Source]
<span translate="no">我喜欢</span>花蓮的山海澎湖的潮汐

[Constraints]
1. [Hard Constraint] Preserve all HTML tags unchanged
2. [Hard Constraint] Terminology mapping: <span translate="no">我喜欢</span> -> <span translate="no">我喜欢</span>

Output only the translation without any explanation.
```
**Model Output:**
`<span translate="no">我喜欢</span> the mountains and seas of Hualien, and the tides of Penghu.`

#### Method 2: Industrial CAT Placeholder Masking (Production Recommended)
In enterprise translation and localization pipelines, the safest industry standard practice is lightweight pre- and post-processing:
1. **Pre-processing**: Extract `<span translate="no">.*?</span>` via regex and replace with `{v0}`, `{v1}`, etc.
2. **Translation**:
   ```text
   Translate the following text into English. Requirements: preserve placeholders ({v0}):

   {v0}花蓮的山海澎湖的潮汐
   ```
3. **Post-processing**: Restore `{v0}` back to `<span translate="no">我喜欢</span>`.
This completely prevents any translation hallucinations and reduces token consumption during generation.

---

Decoding defaults and output budgets for all families are collected in the [shared settings table](../README.md#default-inference-settings). See the [text inference guide](../inference/llm/README.md) for setup and runnable commands.
