<p align="center"><a href="README.md">English</a> · <a href="README_zh.md">中文</a> · 日本語</p>

<h1 align="center">Index-Translate</h1>
<p align="center"><strong>多言語・マルチモーダル翻訳モデルファミリー</strong><br>マルチモーダル翻訳（画像・音声）、尺制御吹き替え、長文ドキュメント翻訳</p>

<p align="center">
  <a href="https://index-translate.bilibili.com/">🌐&nbsp;デモ</a> ·
  <a href="#option-1-free-online-api-zero-gpu-setup">⚡&nbsp;<b>無料 API</b></a> ·
  <a href="https://huggingface.co/collections/IndexTeam/index-translate">🤗&nbsp;Hugging&nbsp;Face</a> ·
  <a href="https://modelscope.cn/collections/IndexTeam/Index-Translate"><img src="docs/assets/modelscope.svg" width="16" height="16" alt="">&nbsp;ModelScope</a> ·
  <a href="https://arxiv.org/abs/2609.40181">📚&nbsp;技術レポート</a> ·
  <a href="https://huggingface.co/collections/IndexTeam/index-translate-papers-6abe1f5452920941ea0682d9">🤗&nbsp;論文</a> ·
  <a href="https://huggingface.co/collections/IndexTeam/index-translate-benchmarks-6ac16fee5057f40abd7d31b7">🤗&nbsp;ベンチマーク</a> ·
  <a href="https://qm.qq.com/q/xSASqaiEGA">🐧&nbsp;QQ</a>
</p>

> [!TIP]
> 🚀 **無料の公開 API を提供開始！** GPU の準備なしで **Index-Translate-35B-A3B** を直接呼び出せます。`https://index-translate.bilibili.com/v1` で完全に OpenAI 互換です。`python inference/llm/call_api.py "Hello, world!" --target zh` で数秒で試せます！👉 [API クイックスタート](#option-1-free-online-api-zero-gpu-setup)

Index-Translate は、Qwen3.5 をベースに構築された多言語・マルチモーダル翻訳モデルのファミリーです。テキストモデルは **150 言語**をカバーし、用語・書式・内容保持の要件といった翻訳指示に従います。このファミリーは、統一された多言語基盤をマルチモーダル翻訳（画像と音声）、音節数制御翻訳、ドキュメント全体の翻訳へと拡張しています。

- **Index-Translate（テキスト & 画像マルチモーダル）**: 150 言語のテキスト翻訳に対応し、マルチモーダル画像翻訳（ネイティブ視覚エンコーダ、OCR 依存なし）、構造化コンテンツ、ハード／ソフト制約の指示追従、コミュニティ特有の表現をネイティブにサポートします。
- **Index-Echo（音声マルチモーダル）**: エンドツーエンドの音声→字幕（S2TT）と、言語をまたいだ声質クローン吹き替え（S2ST）に対応し、翻訳しながら元の話者の声の特徴を保持します。
- **Index-Homura（尺制御吹き替え）**: 指定した目標音節数に合わせて訳文を動的に調整し、音節レベルでのタイミング合わせを実現します。
- **Index-NativeLong（長文ドキュメント）**: ドキュメント全体を長文コンテキストとして入力でき、段落をまたいで用語や登場人物名の一貫性を保ちます。

<p align="center"><img src="docs/assets/benchmark-radar.en.svg" width="760" alt="Index-Translate 35B-A3B preview、9B、2B の 7 カテゴリ比較"></p>

このレーダーチャートには **35B-A3B（preview）、9B、2B** が含まれ、各軸の min–max 範囲は全 14 モデルで固定しています。7 つの軸は WMT、FLORES、指示追従、低リソース翻訳、字幕、MEME、書籍／小説です。指示追従は instTrans と IFMTBench の IFscore の平均です。正規化されたスケールは正解率（%）ではありません。灰色の破線は各軸における Index 以外の最高スコアを組み合わせたもので、特定の 1 モデルを表すものではありません。[カテゴリ別の生スコア](docs/assets/seven_category_scores_raw.csv) · [図の注記](docs/assets/README.md) · [個別ベンチマーク結果](docs/evaluation.md)

[ニュース](#news) · [⚡ 無料 API](#option-1-free-online-api-zero-gpu-setup) · [✨ マルチモーダル翻訳](#multimodal-translation-showcase-vision--audio) · [モデル](#models) · [クイックスタート](#quick-start) · [指示追従](#instruction-following--constrained-translation) · [使用例](#examples) · [評価](#evaluation) · [ベンチマーク](#benchmarks) · [アプリケーション](#applications) · [TODO](#todo) · [論文と引用](#papers-and-citation)

<a id="news"></a>
## ニュース

- **2026-10-10:** **マルチモーダル画像翻訳**を正式サポートしました！ファミリー全体（**Index-Translate 2B / 9B / 35B-A3B**）がエンドツーエンドの画像翻訳にネイティブ対応しています。無料公開 API、Web デモ、Python スクリプト（[call_api.py](inference/llm/call_api.py)）、GGUF `mmproj` 重みのすべてが、外部 OCR に依存せず画像入力をサポートします。[チュートリアルガイド](docs/image_translate.md)をご覧ください。
- **2026-10-04:** Index-Translate-35B-A3B の無料公開 API エンドポイントを [index-translate.bilibili.com/v1](https://index-translate.bilibili.com) で公開しました。完全に OpenAI 互換です。[call_api.py](inference/llm/call_api.py) でお試しください。
- **2026-10-04:** 4 つの [Index-Translate ベンチマーク](#benchmarks)を公開しました。データセット／メタデータは Hugging Face に、評価スクリプトとガイドは GitHub にあります。
- **2026-10-03:** ファミリー全体の公式量子化ビルドを Hugging Face と ModelScope で公開しました。llama.cpp でのローカル推論向けの **GGUF**（画像用 `mmproj` 重みを含む）に加え、vLLM サービング向けの **FP8**（W8A8）と **NVFP4**（W4A4、Blackwell 最適化）を提供しています。
- **2026-09-30:** Index-Translate をリリースしました。2B / 9B / 35B-A3B（preview）のテキストモデル重みを Hugging Face と ModelScope で公開し、技術レポートとオンラインデモも公開しました。

<a id="todo"></a>
## TODO

- [x] ファミリー全体の公式量子化ビルド（llama.cpp ローカル推論向けの GGUF、vLLM サービング向けの FP8 と NVFP4）を公開する。
- [x] instTrans、MEME、SandGlass、NAtIveLong のデータ／メタデータと評価コードを公開する。[ベンチマーク](#benchmarks)を参照。
- [ ] Index-Translate メインモデルで統一的なマルチモーダル翻訳をサポートする：音声・動画翻訳および長文ドキュメントをメインモデルに統合する。
- [ ] Index-Echo-S2ST：対応言語を追加する。
- [ ] スケールアウト（100B 以上）。

<a id="models"></a>
## モデル

以下のリンクから **2B、9B、35B-A3B（preview）** のテキストモデルのチェックポイントを入手できます。評価結果は[比較表](docs/evaluation.md)に掲載しています。

| カテゴリ | モデル | タスクと公開パッケージの対応範囲 | Hugging Face | ModelScope | 推論ガイド |
|---|---|---|---|---|---|
| **テキスト & 画像マルチモーダル** | **Index-Translate** | 150 言語のテキスト & マルチモーダル画像翻訳、指示追従 | [2B](https://huggingface.co/IndexTeam/Index-Translate-2B) · [9B](https://huggingface.co/IndexTeam/Index-Translate-9B) · [35B-A3B (preview)](https://huggingface.co/IndexTeam/Index-Translate-35B-A3B-preview) ([⚡無料 API](#option-1-free-online-api-zero-gpu-setup)) | [2B](https://modelscope.cn/models/IndexTeam/Index-Translate-2B) · [9B](https://modelscope.cn/models/IndexTeam/Index-Translate-9B) · [35B-A3B (preview)](https://modelscope.cn/models/IndexTeam/Index-Translate-35B-A3B-preview) | [ガイド](inference/llm/README.md) · [無料 API](inference/llm/call_api.py) · [画像ガイド](docs/image_translate.md) |
| **音声マルチモーダル** | **Index-Echo S2TT** | 音声 → 字幕。同梱スクリプト：zh→en/ja/es | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-2B) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-9B) | [2B](https://modelscope.cn/models/IndexTeam/Index-Echo-S2TT-2B) · [9B](https://modelscope.cn/models/IndexTeam/Index-Echo-S2TT-9B) | [ガイド](inference/echo-s2tt/README.md) |
| **音声マルチモーダル** | **Index-Echo S2ST** | 音声 → 音声。zh→en/es/ja、en→zh/es/ja（声質クローン） | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-9B) | [2B](https://modelscope.cn/models/IndexTeam/Index-Echo-S2ST-2B) · [9B](https://modelscope.cn/models/IndexTeam/Index-Echo-S2ST-9B) | [ガイド](inference/echo-s2st/README.md) |
| **尺制御吹き替え** | **Index-Homura** | 目標音節数を指定した翻訳 | [2B](https://huggingface.co/IndexTeam/Index-Homura-2B) · [9B](https://huggingface.co/IndexTeam/Index-Homura-9B) | [2B](https://modelscope.cn/models/IndexTeam/Index-Homura-2B) · [9B](https://modelscope.cn/models/IndexTeam/Index-Homura-9B) | [ガイド](inference/llm/README.md) |
| **長文ドキュメント** | **Index-NativeLong** | 長文ドキュメント。固定テンプレート：zh↔en、zh↔ja | [2B](https://huggingface.co/IndexTeam/Index-Nailong-2B) · [9B](https://huggingface.co/IndexTeam/Index-Nailong-9B) | [2B](https://modelscope.cn/models/IndexTeam/Index-Nailong-2B) · [9B](https://modelscope.cn/models/IndexTeam/Index-Nailong-9B) | [ガイド](inference/llm/README.md) |

**名称について:** Index-NativeLong はモデル ID `IndexTeam/Index-Nailong-2B` および `IndexTeam/Index-Nailong-9B` で公開されています。コマンドではこれらの ID を使用してください。音声パッケージと長文ドキュメントパッケージの対応言語は、テキストモデルの 150 言語対応とは別に記載しています。

**量子化ビルド:** 上記のすべてのモデルは、**GGUF**（llama.cpp ローカル推論。各モデルにつき 1 リポジトリに全ビット幅を収録し、該当するものは画像用 mmproj を含む）、**FP8**（compressed-tensors W8A8、vLLM サービングにそのまま利用可能）、**FP4**（compressed-tensors NVFP4 W4A4、Blackwell GPU 向け）でも公開しています。Index-Echo 音声モデルについては、GGUF リポジトリには**テキスト LLM バックボーンのみ**が含まれ、FP8/FP4 リポジトリには量子化 LLM を含む**完全なパイプライン**が含まれます。すべてのリポジトリは [ModelScope](https://modelscope.cn/organization/IndexTeam) にもミラーされています。

| モデル | GGUF (llama.cpp) | FP8 (vLLM) | FP4 (vLLM, Blackwell) |
|---|---|---|---|
| **Index-Translate** | [2B](https://huggingface.co/IndexTeam/Index-Translate-2B-GGUF) · [9B](https://huggingface.co/IndexTeam/Index-Translate-9B-GGUF) · [35B-A3B (preview)](https://huggingface.co/IndexTeam/Index-Translate-35B-A3B-preview-GGUF) | [2B](https://huggingface.co/IndexTeam/Index-Translate-2B-FP8) · [9B](https://huggingface.co/IndexTeam/Index-Translate-9B-FP8) · [35B-A3B (preview)](https://huggingface.co/IndexTeam/Index-Translate-35B-A3B-preview-FP8) | [2B](https://huggingface.co/IndexTeam/Index-Translate-2B-FP4) · [9B](https://huggingface.co/IndexTeam/Index-Translate-9B-FP4) · [35B-A3B (preview)](https://huggingface.co/IndexTeam/Index-Translate-35B-A3B-preview-FP4) |
| **Index-Homura** | [2B](https://huggingface.co/IndexTeam/Index-Homura-2B-GGUF) · [9B](https://huggingface.co/IndexTeam/Index-Homura-9B-GGUF) | [2B](https://huggingface.co/IndexTeam/Index-Homura-2B-FP8) · [9B](https://huggingface.co/IndexTeam/Index-Homura-9B-FP8) | [2B](https://huggingface.co/IndexTeam/Index-Homura-2B-FP4) · [9B](https://huggingface.co/IndexTeam/Index-Homura-9B-FP4) |
| **Index-NativeLong** | [2B](https://huggingface.co/IndexTeam/Index-Nailong-2B-GGUF) · [9B](https://huggingface.co/IndexTeam/Index-Nailong-9B-GGUF) | [2B](https://huggingface.co/IndexTeam/Index-Nailong-2B-FP8) · [9B](https://huggingface.co/IndexTeam/Index-Nailong-9B-FP8) | [2B](https://huggingface.co/IndexTeam/Index-Nailong-2B-FP4) · [9B](https://huggingface.co/IndexTeam/Index-Nailong-9B-FP4) |
| **Index-Echo S2TT** | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-2B-GGUF) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-9B-GGUF)（LLM バックボーン） | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-2B-FP8) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-9B-FP8)（完全パイプライン） | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-2B-FP4) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-9B-FP4)（完全パイプライン） |
| **Index-Echo S2ST** | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B-GGUF) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-9B-GGUF)（LLM バックボーン） | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B-FP8) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-9B-FP8)（完全パイプライン） | [2B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B-FP4) · [9B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-9B-FP4)（完全パイプライン） |

## 推論

<a id="quick-start"></a>
### クイックスタート

<a id="option-1-free-online-api-zero-gpu-setup"></a>
#### 方法 1：無料オンライン API（GPU 不要）

ローカル GPU なしで、無料のオンライン API を直接呼び出せます。依存ライブラリ不要の Python スクリプト [`inference/llm/call_api.py`](inference/llm/call_api.py) の利用をおすすめします。

```bash
# 1. コマンドラインでの簡単な翻訳（依存ライブラリ不要、そのまま動作）
python inference/llm/call_api.py "你好，世界。今天天气不错，我们去公园散步吧。" --target en

# 2. マルチモーダル画像翻訳（2B / 9B / 35B すべてネイティブ対応、OCR 依存なし）
python inference/llm/call_api.py --image path/to/screenshot.png --target zh               # デフォルトは 35B フラッグシップ
python inference/llm/call_api.py --image photo.jpg --target zh -m Index-Translate-2B    # 2B エッジ向け軽量版
python inference/llm/call_api.py --image diagram.png --target en -m Index-Translate-9B   # 9B ワークステーション向けバランス版

# 3. ブラウザ拡張機能向けローカルプロキシブリッジ（例：Immersive Translate / 沉浸式翻译）
# CORS/WAF ヘッダーと thinking タグの抑制のため、ブラウザ拡張機能にはローカルブリッジプロキシが必要です：
python inference/llm/call_api.py --serve
# その後、Immersive Translate を次のように設定します：
# - サービス: Custom / OpenAI
# - API URL: http://127.0.0.1:8080/v1
# - モデル: Index-Translate-35B-A3B
# - API キー: 任意の文字列（例：index）

# オプション A：標準の Chat Completions API（OpenAI 互換）
curl https://index-translate.bilibili.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Index-Translate-35B-A3B",
    "messages": [{"role": "user", "content": "请将以下文本翻译为英语，直接输出翻译结果，不要进行任何解释。\n\n你好，世界。"}]
  }'

# オプション B：マルチモーダル画像翻訳 API（OpenAI の image_url 形式、base64 対応）
curl https://index-translate.bilibili.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "User-Agent: Index-Translate-Client/1.0" \
  -d '{
    "model": "Index-Translate-35B-A3B",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "Translate the text in the image into Chinese."},
          {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="}}
        ]
      }
    ]
  }'

# オプション C：新しい OpenAI Responses API（client.responses.create / POST /v1/responses 互換）
curl https://index-translate.bilibili.com/v1/responses \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Index-Translate-35B-A3B",
    "input": "请将以下文本翻译为英语，直接输出翻译结果，不要进行任何解释。\n\n你好，世界。"
  }'
```

> [!TIP]
> ✨ **マルチモーダル翻訳（画像 & 音声）が全面的に利用可能に！**  
> - 🖼️ **画像マルチモーダル（画像翻訳）**: 全サイズ（2B / 9B / 35B）が内蔵の視覚エンコーダでネイティブ対応。**OCR 依存なし**で、レイアウトとマルチモーダルな文脈を保持します。👉 **[【チュートリアル】マルチモーダル画像翻訳 完全ガイド（API、セルフホスト、事例）](docs/image_translate.md)**  
> - 🎙️ **音声マルチモーダル（音声字幕 & 吹き替え）**: Index-Echo はエンドツーエンドの音声→字幕（S2TT）と声質クローン吹き替え（S2ST）に対応しています。👉 **[S2TT 字幕ガイド](inference/echo-s2tt/README.md)** · **[S2ST 吹き替えガイド](inference/echo-s2st/README.md)**

> [!TIP]
> 🌐 **対訳で Web を閲覧したい？Immersive Translate にすぐ対応（Windows / macOS / Linux）！**
> ブラウザ拡張機能は、設定不要のローカルブリッジプロキシで利用できます（Windows ユーザーはルートフォルダの `run_proxy_windows.bat` をダブルクリックするだけです）。
> 👉 **[【設定ガイド】Immersive Translate 設定チュートリアル（Windows / macOS / Linux、スクリーンショット & トラブルシューティング付き）](docs/immersive_translate.md)**

#### 方法 2：ローカル vLLM でのセルフホスト

Qwen3.5 に対応した vLLM ビルドを使い、CUDA GPU 上で 2B テキストモデルから始めます。ターミナルで次を実行します。

```bash
git clone https://github.com/bilibili/Index-Translate.git
cd Index-Translate
pip install -U vllm
pip install -r inference/llm/requirements.txt
vllm serve IndexTeam/Index-Translate-2B --host 127.0.0.1 --port 8000 --max-model-len 4096
```

同じリポジトリのディレクトリで、**別のターミナル**から次を実行します。

```bash
python inference/llm/translate.py \
  "你好，世界。今天天气不错，我们去公园散步吧。" \
  --target en --model IndexTeam/Index-Translate-2B
```

公開済みの 2B モデルで記録された出力例：

> Hello, world. The weather is nice today. Let's go for a walk in the park.

[記録済みの事例](inference/llm/cases/translate_cases.jsonl)、[テキスト推論](inference/llm/README.md)、[プロンプト例](docs/prompts.md)を参照してください。上記の 4,096 トークン設定は短文向けの例です。サービング用のプリセットは下の表に記載しています。

音声については、専用の [S2TT 字幕ガイド](inference/echo-s2tt/README.md) または [S2ST 吹き替えガイド](inference/echo-s2st/README.md) を使用してください。

<a id="instruction-following--constrained-translation"></a>
### 指示追従と制約付き翻訳

Index-Translate は指示追従能力（instTrans）を深く統合しています。`translate.py` と `syllable_translate.py` により、**ハード制約（書式の保持、用語集の厳密な適用）**と**ソフト制約（トーン・文体、分野に応じた語義の曖昧性解消）**の両方を標準でサポートします。

```bash
# ハード制約 1：用語集の厳密な適用（-g / --glossary）
python inference/llm/translate.py \
  "王平仲采用了更加昂贵的碳纤维材料。碳纤维的好处就是它抗裂缝。" \
  --target en -g "碳纤维:carbon fiber, 抗裂缝:crack resistance"

# ハード制約 2：書式と構造の保持（-H / --hard）
python inference/llm/translate.py \
  '{"user_id": 1024, "event": "purchase", "message": "您的订单已支付完成。"}' \
  --target en -H "保留源文中的 JSON 格式标记不变"

# ソフト制約 1：トーンと文体の調整（-S / --soft）+ ジャンル（-d / --genre）
python inference/llm/translate.py \
  "今天下午的会议临时取消了，改天我们再碰一下商量。" \
  --target en -d "商务邮件" -S "调整为严谨、正式、礼貌的商务公文风格"

# ソフト制約 2：分野の文脈と語義の曖昧性解消（-S / --soft）
python inference/llm/translate.py \
  "The plant is operating at full capacity after the spring upgrade." \
  --target zh -d "工业制造" -S "语境为工业制造与重工厂房领域，准确消歧专有名词（如 plant 译为工厂而非植物）"

# 音節制御との併用：Index-Homura は用語集を適用しつつ音節数を厳守します
python inference/llm/syllable_translate.py \
  "我们今天去看电影吧" --syllables 7 --target en --glossary "电影:cinema"
```

> **instTrans の仕様と制約の詳細:**
> - **標準プロンプト**: クライアントが自動的に instTrans ベンチマークの構造（`【源文】` + 番号付きの `1. 【硬性要求】...` / `2. 【注意】...` + 末尾の指示）に整形します。
> - **ハード制約**: 構造的な書式（JSON/CSV/コード/プレースホルダー）、用語集、ソーシャル要素、音節の順序。二値で判定され（$g_{\mathrm{hard}}$）、1 つでも失敗するとそのインスタンスのスコアは 0 になります。
> - **ソフト制約**: トーン／文体の適応、文脈に応じた語義の曖昧性解消、文をまたいだ一貫性、LaTeX の保持。段階的なスケールで評価されます（$q_{\mathrm{soft}}$）。
> - 完全な例は[テキスト推論ガイド](inference/llm/README.md)と[指示の事例](inference/llm/cases/instruction_cases.jsonl)を参照してください。

### デフォルトの推論設定

これはリポジトリのクライアントと公開済み Echo パッケージに共通するリファレンスです。Translate は **2B / 9B / 35B-A3B（preview）**、その他のファミリーは **2B / 9B** を対象とします。デコードのデフォルト値は、各ファミリー内でサイズ間共通です。

**未設定**はクライアントがバックエンド／モデルの設定を継承することを意味し、**—** はその設定が該当しないことを意味します。テキスト生成の行は Echo の書き起こし／翻訳についての設定で、音声生成は別の行に記載しています。

| 設定 | [Index-Translate](inference/llm/README.md) | [Index-Homura](inference/llm/README.md) | [Index-NativeLong](inference/llm/README.md) | [Echo S2TT](inference/echo-s2tt/README.md) | [Echo S2ST](inference/echo-s2st/README.md) |
|---|---|---|---|---|---|
| エントリポイント | `translate.py` | `syllable_translate.py` | `doc_translate.py` | `s2tt.py` → パッケージの `infer.py` | `dub.py` → パッケージの `DubbingBridgeModel` |
| デフォルトのチェックポイント | 9B | 9B | 9B（`Index-Nailong`） | 2B | ローカルの `./Index-Echo-S2ST-2B` |
| テキストのデコード | Greedy | サンプリング | Greedy | Greedy（`do_sample=False`） | Greedy（`do_sample=False`） |
| `temperature` | `0` | `0.3` | `0` | `0` | `0`（テキスト） |
| `top_p` | 未設定 | 未設定 | `1` | 未設定 | 未設定（テキスト） |
| `top_k` | 未設定 | 未設定 | `-1` | 未設定 | 未設定（テキスト） |
| `min_p` | 未設定 | 未設定 | `0` | 未設定 | 未設定（テキスト） |
| `presence_penalty` | 未設定 | 未設定 | `0` | — | — |
| `repetition_penalty` | 未設定 | 未設定 | `1` | 未設定 | 未設定（テキスト） |
| `seed` | 未設定 | 未設定 | `42` | 未設定 | `42`（音声） |
| Thinking | `enable_thinking=False` | `enable_thinking=False` | `enable_thinking=False` | 空の `<think>` ブロックを事前入力 | 空の `<think>` ブロックを事前入力 |
| テキスト出力の上限 | `max_tokens=1024` | `max_tokens=max(512, 3 * len(text))` | `max_tokens` は省略。上限はサーバーが決定 | ウィンドウごとに `max_new_tokens=2000` | `max_new_tokens=1024` |
| テキストの停止条件 | 未設定 | 未設定 | `stop_token_ids=[248044, 248046]`、`ignore_eos=False` | トークナイザーの EOS / `<\|im_end\|>` | トークナイザーの EOS / `<\|im_end\|>` |
| 出力ストリーミング | なし | なし | `stream=True` | ウィンドウごとに逐次出力 | 音声は `stream=False` |
| `serve_vllm.sh` のコンテキスト長（入力 + 出力） | 2B / 9B: `32768`。35B のプリセットなし | `32768` | 2B: `262144`、9B: `229376` | — | — |
| デフォルトの言語／制約 | ソース `auto`、ターゲット `en` | ターゲット `en`。`--syllables` は必須 | `zh-en` | `zh-en` | `--lang` は必須。ソースは zh/en から推定 |
| 音声ウィンドウ／履歴 | — | — | — | `--max-win 60` 秒、`--ctx-k 5` 個前までのウィンドウ | 発話は 30 秒以下を推奨、`chunk=False` |
| 音声サンプラー | — | — | — | — | `sampling=25` で固定。CosyVoice RAS のデフォルト `top_p=0.8`、`top_k=25` |
| 音声トークンの上限 | — | — | — | — | 最大 `min(1500, 20 * m)`、最小 `2 * m` |
| 音声の速度／サンプルレート | — | — | — | — | `speed=1.0`、`24000` Hz |
| 主な上書きオプション | `--model`、`--instruction`、`--glossary`、`--temperature`、`--max-tokens` | `--model`、`--syllables`、`--glossary`、`--temperature`、`--max-tokens` | `--model`、`--direction`、`--max-tokens` | `--size`、`--temperature`、`--max-new-tokens`、`--max-win`、`--ctx-k`、`--glossary` | `--model-dir`、`--lang`。上限／seed は下位レベル API で指定 |

- **テキストクライアント:** デフォルトでは `http://127.0.0.1:8000/v1`、API キー `EMPTY` を使用します。`--base-url` / `--api-key` または `OPENAI_BASE_URL` / `OPENAI_API_KEY` で変更できます。`--model` は `INDEX_MODEL` とデフォルトのチェックポイントより優先されます。35B-A3B は手動でサーブし、`--model IndexTeam/Index-Translate-35B-A3B-preview` で選択してください。
- **上限:** Homura の `len(text)` は、入力をトリムした後の Python の文字数です。NativeLong で `max_tokens` を省略した場合、出力の上限はサーバーに委ねられますが、コンテキスト容量とサーバーの制限は引き続き適用されます。明示的に上限を設定するには正の値の `--max-tokens` を渡してください。コンテキストにはプロンプト全体と生成出力が含まれます。サービング時の上限は `--max-model-len` で変更できます。
- **Echo S2ST:** `m` はアラインメントされたターゲットテキストのトークン数です。`sampling=25` はパッケージコード内の固定引数で、CLI オプションではありません。公開されている `DubbingBridgeModel.dub` ラッパーは `seed` もトークン上限も公開していません。[モデルカード](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B#configurable-api-parameters)に記載されている下位レベルの `extract` / `synth` API を使用してください。`chunk=True` は未実装です。
- **適用範囲:** これらは利用時のデフォルト値です。技術レポートのベンチマークにおけるデコードおよびコンテキスト設定は、[評価](docs/evaluation.md)に別途記載しています。

<a id="examples"></a>
## 使用例

以下の例は[公式デモ](https://index-translate.bilibili.com/?p=/site/home.html#benchmark-cases)から抜粋したものです。下記の出力は個別の事例を示すもので、完全な比較とタスク設定はデモとレポートで確認できます。

<a id="multimodal-translation-showcase-vision--audio"></a>
### マルチモーダル翻訳のショーケース（画像 & 音声）

#### 1. 画像マルチモーダル：ソフトウェア UI、技術図、道路標識（OCR 依存なし）

**プロンプト:** 画像内の英語テキストを自然な中国語に翻訳します。外部 OCR ツールを使わず、全モデルサイズ（2B / 9B / 35B）で視覚的なレイアウトと文脈を深く統合します。

| 画像カテゴリ | 画像内の英語原文 | Index-Translate（2B / 9B / 35B）の出力（中国語） | 主なポイント |
|---|---|---|---|
| **ソフトウェアの設定 UI** | "Enable hardware-accelerated GPU scheduling (requires restart)" | 启用硬件加速 GPU 计划（需要重启） | システム用語の正確さとすっきりした区切り |
| **技術的なフローチャート** | "Client -> Load Balancer -> Worker Pool (Least-Conn Routing)" | 客户端 → 负载均衡器 → 工作节点池（最小连接数路由） | アーキテクチャの概念とフローの方向を保持 |
| **実際の道路標識** | "Pedestrian Crossing Ahead · Speed Limit 30 mph" | 前方行人过街通道 · 限速 30 英里/小时 | 撮影時の歪みに強く、単位も標準的に変換 |

3 サイズ（2B / 9B / 35B）すべてに、対応する GGUF `mmproj` 視覚重みを提供しています。[オンラインデモ](https://index-translate.bilibili.com/?p=/site/translate.html)で画像をアップロードまたは貼り付けて直接お試しください。詳細は[画像翻訳ガイド](docs/image_translate.md)を参照してください。

#### 2. 音声マルチモーダル：Index-Echo による音声吹き替えと多言語字幕

![Index-Echo の評価](docs/assets/echo_benchmark_overview.en.svg)

S2ST のパネルでは、デプロイ済みの 2B システム、パイプライン方式、SeamlessM4T-v2 を比較しています。このデモでの比較は、レポート内の 6 方向のマッチド比較とは別のものです。SeamlessM4T-v2 は元の話者の声をクローンしません。

<table>
<tr><th>音声吹き替え（S2ST）</th><th>多言語字幕（S2TT）</th></tr>
<tr>
<td align="center"><a href="https://index-translate.bilibili.com/?p=/site/assets/blog/echo-demo.mp4"><img src="docs/assets/echo-s2st.png" height="180" alt="Index-Echo の英語→日本語吹き替えデモを見る"></a></td>
<td align="center"><a href="https://index-translate.bilibili.com/?p=/site/assets/blog/echo-demo-s2tt.mp4"><img src="docs/assets/echo-s2tt.png" height="180" alt="Index-Echo の多言語字幕デモを見る"></a></td>
</tr>
<tr><td>英語動画の日本語吹き替え（声質クローン）</td><td>同じ動画に複数言語の字幕を付与</td></tr>
</table>

プレビューをクリックすると動画を視聴できます。また、[Index-Echo をオンラインで試す](https://index-translate.bilibili.com/?p=/site/index.html&lang=en)こともできます。Web サイトのデモと同梱の推論インターフェースでは対応言語が異なります。公開済みのインターフェースは[モデル表](#models)に記載しています。

### テキスト & 指示追従のショーケース

#### 3. ハッシュタグを保持したままテキストを翻訳（JSON のハード制約）

**タスク:** この JSON を韓国語に翻訳し、構造、星記号、中国語のハッシュタグを保持する。

```json
{"title": "⭐2月13日例行维护公告⭐", "content": "#热血航线大和登场#"}
```

**Index-Translate-9B:**

```json
{"title": "⭐2월 13일 정기 점검 공지⭐", "content": "#热血航线大和登场#"}
```

タイトルは翻訳され、指定したハッシュタグはそのまま保持されています。[テキスト翻訳を試す](https://index-translate.bilibili.com/?p=/site/translate.html&lang=en)

#### 4. コミュニティ特有の表現の意味を保つ（MEME & 文化的スラング）

**原文:** 狒瘾犯了就去打 — このゲームの文脈では、「狒瘾」は Final Fantasy XIV をプレイしたい衝動を指します。

| モデル | 英語の出力 |
|---|---|
| Index-Translate-9B | When the FFXIV itch hits, just go play. |
| Index-Translate-2B | Go play when my FFXIV addiction kicks in. |
| Hy-MT2-7B | If you get monkey addiction, go fight. |

### 特化分野のショーケース（尺制御吹き替え & 長文ドキュメント）

#### 5. 訳文の音節数を指定する（Index-Homura）

**原文:** 生活两天，是一种什么体验。Index-Homura-9B は、指定された 3 つの長さに対して異なる言い回しを生成します。

| 目標 / 実際の音節数 | 英語の出力 |
|---|---|
| 10 / 10 | to live for two days. What would that be like? |
| 14 / 14 | What would it be like to live there for two days, I wonder? |
| 18 / 18 | What would it be like to live there for two days, trying to get by somehow? |

この 3 例は目標を満たしていますが、一般に音節制御は近似的なものであり、発話時間は話し方にも左右されます。[Index-Homura を試す](https://index-translate.bilibili.com/?p=/site/syllable.html&lang=en)

#### 6. ドキュメント全体で登場人物の名前を一貫させる（Index-NativeLong）

約 32K トークンのファンタジー作品の中で、「王妃」は登場人物の名前です。以下の抜粋では、ドキュメント全体をネイティブに翻訳した場合と、同じ 9B モデルを使い、近傍の文脈と自動生成の用語集を用いたチャンク分割ワークフローで翻訳した場合を比較しています。

| 原文中の位置 | Index-NativeLong-9B（ドキュメント全体） | 同じ 9B（チャンク分割） |
|---|---|---|
| 31.3% | Mentor Wang Fei | Instructor Wangfei |
| 56.6% | Wang Fei | the Dean |
| 84.8% | Wang Fei | The Queen Consort |

位置は原文の文字数で測定しています。ドキュメント全体の出力ではこれらの位置で名前が一貫しています。デモでは、外部から与えた用語集によってチャンク分割の結果を修正できる様子も示しています。[Index-NativeLong を試す](https://index-translate.bilibili.com/?p=/site/doc.html&lang=en)

<a id="evaluation"></a>
## 評価

![更新されたテキスト翻訳ベンチマーク](docs/assets/text_benchmark_overview.en.svg)

これらのチャートは、更新されたデモの比較を再現したものです。*35B-A3B は preview モデルです。指示追従のパネルは instTrans と IFMTBench の平均です。Quality は instTrans の品質と IFMTBench の XCOMET-XXL を組み合わせたもの、IFscore は両者の指示スコアの平均です。個別のベンチマーク指標は以下の表で別々に示しています。

以下の表は、一般的なテキスト翻訳、低リソース翻訳、低リソースでの指示追従を対象としています。FLORES は COMET-22、WMT26 はジャッジスコアを使用します。instTrans は翻訳品質と指示追従を別々に報告します。MEME はコミュニティ特有の表現や文化的表現の翻訳品質を測定します。最初の表のすべての指標は値が高いほど良く、列ごとにスケールが異なります。

| モデル | FLORES ↑ | WMT26 ↑ | instTrans quality ↑ | instTrans IFscore ↑ | MEME ↑ |
|---|---:|---:|---:|---:|---:|
| **Index-Translate-35B-A3B (preview)** | 0.8794 | 76.76 | 0.6901 | 0.8336 | 0.7405 |
| **Index-Translate-9B** | 0.8789 | 75.35 | 0.6771 | 0.8209 | 0.7387 |
| **Index-Translate-2B** | 0.8655 | 60.26 | 0.5391 | 0.7569 | 0.6443 |
| Hy-MT2-7B | 0.8747 | 60.51 | 0.5143 | 0.6079 | 0.5139 |
| Hy-MT2-30B-A3B | 0.8787 | 66.81 | 0.5725 | 0.6415 | 0.5812 |
| DeepSeek-V4.1-Flash | 0.8762 | 83.55 | 0.6068 | 0.6374 | 0.7424 |
| GPT-5.6-Sol | 0.8650 | 89.10 | 0.6902 | 0.7624 | 0.7194 |
| Gemini 3.5 Flash Lite | 0.8750 | 79.52 | 0.6068 | 0.6374 | 0.7034 |

### 低リソース翻訳と指示追従

FLORES_minor_pair は低リソース言語での一般的な翻訳を評価し、instTrans_minor は翻訳品質と指示追従を別々に報告します。Off-target はターゲット言語以外の言語で出力された割合で、低いほど良い指標です。その他の指標は高いほど良くなります。太字はこの表の各列における最良値です。

| モデル | FLORES_minor_pair<br>COMET-22 ↑ | FLORES_minor_pair<br>XCOMET-XXL ↑ | FLORES_minor_pair<br>off-target ↓ | instTrans_minor<br>Quality ↑ | instTrans_minor<br>IFscore ↑ | instTrans_minor<br>off-target ↓ |
|---|---:|---:|---:|---:|---:|---:|
| **Index-Translate-35B-A3B (preview)** | 0.8168 | 0.7164 | 2.4% | 0.5151 | 0.7715 | 4.05% |
| **Index-Translate-9B** | 0.7992 | 0.6805 | 4.0% | 0.5222 | **0.7725** | **3.47%** |
| **Index-Translate-2B** | 0.7377 | 0.4817 | 4.2% | 0.3050 | 0.6586 | 3.97% |
| Hy-MT2-7B | 0.4626 | 0.3334 | 35.7% | 0.1121 | 0.2405 | 45.40% |
| Hy-MT2-30B-A3B | 0.6746 | 0.5359 | 14.5% | 0.2246 | 0.4449 | 15.47% |
| DeepSeek-V4.1-Flash | **0.8333** | **0.7297** | **1.3%** | 0.4793 | 0.5854 | 5.73% |
| GPT-5.6-Sol | 0.7669 | 0.6918 | 10.4% | **0.5757** | 0.6866 | 7.73% |
| Gemini 3.5 Flash Lite | 0.8122 | 0.6995 | 3.3% | 0.3927 | 0.5584 | 12.18% |

3 つの Index-Translate モデルの中では、35B-A3B（preview）が FLORES_minor_pair の COMET-22 と XCOMET-XXL で最高スコア（**0.8168 / 0.7164**）を記録し、off-target 率は **2.4%** です。instTrans_minor では、Index-Translate-9B が比較対象の全モデル中で最高の IFscore（**0.7725**）と最低の off-target 率（**3.47%**）を達成しており、品質スコアは **0.5222** です。

[完全な表](docs/evaluation.md)には、すべての比較モデル、低リソースの指標、WMT24++、IFMTBench、ドメイン別平均、汎用能力、音声、SandGlass、長文ドキュメントの結果を掲載しています。詳細な設定と分析は[技術レポート](https://arxiv.org/abs/2609.40181)にあります。

### Index-Homura と Index-NativeLong

![Index-Homura の評価](docs/assets/homura_benchmark_overview.en.svg)

デモにおける SandGlass の総合スコアと長さの遵守率です。総合スコアは、詳細な表にある翻訳品質の指標とは別のものです。

![Index-NativeLong 64K の評価](docs/assets/nativelong_benchmark_overview.en.svg)

中国語側 64K トークンでの GuoFeng と BWB Track A3 の結果です。

特化モデルについては、Index-Homura-9B が SandGlass で **81.92% の出力を目標音節数の ±10% 以内**に収めています。Index-NativeLong-9B は GuoFeng / BWB / Books で **0.7891 / 0.7683 / 0.8848** のスコアを記録しています。完全な表には、翻訳品質とのトレードオフや評価に関する注記も含まれています。

<a id="benchmarks"></a>
## ベンチマーク

データセットとメタデータは [🤗 Index-Translate Benchmarks コレクション](https://huggingface.co/collections/IndexTeam/index-translate-benchmarks-6ac16fee5057f40abd7d31b7)にあります。評価スクリプト、バージョン固定のデータダウンローダー、実行手順は [benchmarks/](benchmarks/README.md) にあります。

| ベンチマーク | 公開内容 | データセット | 評価コードとガイド |
|---|---|---|---|
| **instTrans** | 3,000 件の翻訳指示タスク、10 種類の制約 | [🤗 InstTrans-Bench](https://huggingface.co/datasets/IndexTeam/InstTrans-Bench) | [insttrans](benchmarks/insttrans/README.md) |
| **MEME** | 3,638 件の中国語→英語の事例、703 語・857 語義 | [🤗 Meme-Translation-Bench](https://huggingface.co/datasets/IndexTeam/Meme-Translation-Bench) | [meme](benchmarks/meme/README.md) |
| **SandGlass** | 3,600 件：字幕 300 件 × ターゲット言語 4 種 × 長さ指定 3 種 | [🤗 Sandglass-Bench](https://huggingface.co/datasets/IndexTeam/Sandglass-Bench) | [sandglass](benchmarks/sandglass/README.md) |
| **NAtIveLong** | BWB 84 件と GuoFeng 84 件の長文ドキュメント事例のメタデータ、評価コード、データ取得手順 | [🤗 NAtIveLong](https://huggingface.co/datasets/IndexTeam/NAtIveLong) | [nativelong](benchmarks/nativelong/README.md) |

NAtIveLong には原作小説や参照訳は含まれていません。公式の BWB データは別途入手してください。GuoFeng についてはローカルで再構築するツールを提供しています。instTrans の公開データには、評価表にある 2,793 件の低リソース拡張タスクは含まれていません。元のプロンプトはそのまま保持しており、各ディレクトリの `RELEASE_REVIEW.md` にレビューによる変更点と検証上の制限を記録しています。過去のスコアは再計測していません。各ベンチマークには個別のライセンス条項があり、リポジトリのルートライセンスがそれらに優先することはありません。

その他の結果については、[評価設定の全容](docs/evaluation.md)と [IFMTBench の前処理](docs/evaluation.md#ifmtbench-preprocessing)を参照してください。

<a id="applications"></a>
## アプリケーション

- **[Immersive Translate ガイド](docs/immersive_translate.md):** Windows（ワンクリックの `.bat` スクリプトを提供）/ macOS / Linux で、無料公開の 35B API またはローカルモデルを Immersive Translate で使うための、スクリーンショット付きのステップバイステップのチュートリアルです。
- **[マルチモーダル画像翻訳ガイド](docs/image_translate.md):** ネイティブ視覚エンコーダの使い方、ローカルデプロイ、OpenAI API の形式を網羅したガイドです。
- **[マルチモーダル動画吹き替えパイプライン](video-dub/README.md):** 動画からの音声抽出、ボーカル分離、音声セグメンテーション、翻訳、吹き替え、タイムラインの位置合わせまでを行う完全なツールチェーンです。
- **[ネイティブブラウザ拡張機能](extension/README.md):** Chrome、Edge、Firefox に対応した軽量な組み込み型 Web ページ翻訳ツールです。

## コミュニティ & エコシステムのプロジェクト

Index-Translate を使って構築されたオープンソースプロジェクトとアプリケーション：

- **[simul-subtitle](https://github.com/KorenKrita/simul-subtitle)**（作者：[@KorenKrita](https://github.com/KorenKrita)）：Android 向けのリアルタイムなオンデバイス字幕翻訳アプリ。日本語／英語の音声を認識し、Index-Translate により 22 言語に翻訳して、あらゆるアプリの上にライブ字幕をフローティング表示します。

## コミュニティ

議論やフィードバックは [QQ グループ（960123527）](https://qm.qq.com/q/xSASqaiEGA)へどうぞ。下の QR コードを読み取って参加することもできます。

<p align="center"><a href="https://qm.qq.com/q/xSASqaiEGA"><img src="docs/assets/qq-group.jpg" width="320" alt="QQ グループ 960123527 に参加するための QR コード"></a></p>

<a id="papers-and-citation"></a>
## 論文と引用

3 本の論文はすべて [🤗 Hugging Face Papers コレクション](https://huggingface.co/collections/IndexTeam/index-translate-papers-6abe1f5452920941ea0682d9)で閲覧できます。

- **Index-Translate:** [A Multilingual Translation Model Family — Text, Speech, Controlled Dubbing, and Long-Document Translation](https://arxiv.org/abs/2609.40181) · [🤗 HF Papers](https://huggingface.co/papers/2609.40181)
- **HOMURA:** [Taming the Sand-Glass for Time-Constrained LLM Translation via Reinforcement Learning](https://arxiv.org/abs/2601.10187) · [🤗 HF Papers](https://huggingface.co/papers/2601.10187)
- **RIVAL:** [Reinforcement Learning with Iterative and Adversarial Optimization for Machine Translation](https://arxiv.org/abs/2506.05070) · [🤗 HF Papers](https://huggingface.co/papers/2506.05070)

本モデルファミリーまたは関連手法を使用する場合は、該当する論文を引用してください。

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

## ライセンスとフィードバック

[Apache-2.0](LICENSE)。ご質問やフィードバックは [GitHub Issues](https://github.com/bilibili/Index-Translate/issues) までお寄せください。
