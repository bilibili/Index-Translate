# Multimodal Image Translation Tutorial

Index-Translate full family (**2B / 9B / 35B-A3B**) natively supports multimodal image translation, powered by built-in **Visual Encoders (`mmproj`)** for end-to-end visual comprehension and cross-lingual translation.

> [!TIP]
> 🌟 **Full Family Native Visual End-to-End, Zero OCR Dependency!**  
> Traditional image translation relies on a multi-stage pipeline: `OCR Text Recognition -> Text Cleaning -> Translation Model`. This often introduces cascading pipeline errors such as missed characters, awkward line breaks, and disrupted reading orders.  
> **Index-Translate uses a native multimodal architecture**: visual features are projected directly into the model's latent representation space, accurately extracting text while simultaneously understanding image context, layout geometry, and semantic structure—faster, cleaner, and higher quality.

---

## 🌟 Capabilities & Model Specifications Comparison

Index-Translate provides three scales of multimodal models to match diverse deployment environments:

| Model Scale | Vision Projector (`mmproj`) | LLM Quant Size (Rec.) | Hardware Requirements | Target Scenarios |
| :--- | :--- | :--- | :--- | :--- |
| **Index-Translate-2B** | ~360 MB (`Q8_0`) / 670 MB (`f16`) | ~1.5 GB (`Q4_K_M`) | Mobile / Raspberry Pi / Thin Laptops / CPU | On-device, edge computing, ultra-low memory footprint |
| **Index-Translate-9B** | ~360 MB (`Q8_0`) / 670 MB (`f16`) | ~5.5 GB (`Q4_K_M`) | 8GB+ Consumer GPU (RTX 3060/4060) / Apple M series | Production workhorse balancing speed & quality; strict terminology adherence |
| **Index-Translate-35B-A3B** (preview) | ~583 MB (`Q8_0`) / 1.1 GB (`f16`) | ~20 GB (`Q4_K_M`) / ~35 GB (`Q8_0`) | 24GB GPU (RTX 4090/A5000) or Dual-GPU | Flagship preview; complex technical schematics, dense labels, skewed street signs |

### Key Highlights:
1. **Zero External OCR Toolchains**: Fully end-to-end within a single model. No need to deploy PaddleOCR, Tesseract, or paid third-party OCR services.
2. **Broad Scenario Coverage**:
   - 💻 **Desktop / Mobile Screenshots**: UI settings, long web captures, dialog popups, chat records.
   - 📊 **Academic & Technical Diagrams**: Model architecture charts, flowcharts, statistical plots, tables.
   - 🎨 **Comics, Posters & Graphics**: Complex multi-column layouts, stylised typography, speech bubbles.
   - 🛣️ **Physical Scenes & Street Signs**: Road boards, restaurant menus, product labels, exhibition panels.
3. **Flexible Constraint Following**: Supports the full `instTrans` specification (e.g., "preserve terminology", "format as Markdown list", "output valid JSON", etc.).
4. **All-Platform Integration**: Available immediately via Free Public API, Web Demo, zero-dependency Python script, and local llama.cpp / vLLM serving.

---

## 🚀 Method 1: Web Demo (One-Click in Browser)

Use image translation directly in your browser without code:

1. Open the online demo: [https://index-translate.bilibili.com/?p=/site/translate.html](https://index-translate.bilibili.com/?p=/site/translate.html)
2. Select your desired model (**2B**, **9B**, or **35B**).
3. In the source pane, click **📸 Image Translation**, press **Ctrl+V / Cmd+V** to paste a clipboard screenshot, or simply **drag & drop** an image into the input box.
4. An image preview thumbnail card will appear. Select your target language (e.g. English, Chinese, Japanese, Korean, German, etc.).
5. Click **Translate** to stream the translation in real time!

---

## 💻 Method 2: Zero-Dependency Python Script `call_api.py`

The official [`inference/llm/call_api.py`](../inference/llm/call_api.py) script uses only Python standard libraries—**no external pip packages required**:

```bash
# 1. Basic image translation (defaults to 35B flagship model, supports local path or URL)
python inference/llm/call_api.py --image path/to/screenshot.png --target zh

# 2. Use lightweight 2B model for ultra-fast on-device image translation
python inference/llm/call_api.py --image photo.jpg --target zh -m Index-Translate-2B

# 3. Use 9B balanced model for technical charts
python inference/llm/call_api.py --image diagram.png --target en -m Index-Translate-9B

# 4. Specify both source and target language (e.g. Japanese image to Chinese)
python inference/llm/call_api.py --image menu_jp.jpg --source ja --target zh

# 5. Image translation with specific instructions or terminology
python inference/llm/call_api.py "Extract key conclusions and translate to Chinese" \
    --image report_chart.png \
    --target zh \
    --instruction "List items cleanly, keeping numbers and units intact" \
    --glossary "Multi-Head Attention:多头注意力机制"

# 6. Streamed output (SSE typewriter effect)
python inference/llm/call_api.py --image meme.png --target zh --stream
```

---

## 🔌 Method 3: Standard OpenAI-Compatible API

The Index-Translate public API conforms strictly to OpenAI Chat Completions multimodal specifications (`image_url` format).

### 1. cURL Example

> [!NOTE]
> Due to WAF protection, please include a standard `User-Agent: Index-Translate-Client/1.0` header with custom API requests.

```bash
IMG_B64=$(base64 -i test.png)

curl -X POST https://index-translate.bilibili.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "User-Agent: Index-Translate-Client/1.0" \
  -d '{
    "model": "Index-Translate-35B-A3B",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "Translate the text in the image into Chinese."},
          {"type": "image_url", "image_url": {"url": "data:image/png;base64,'"$IMG_B64"'"}}
        ]
      }
    ],
    "max_tokens": 1024,
    "temperature": 0.0
  }'
```

### 2. Python (OpenAI SDK) Example

```python
import base64
from openai import OpenAI

# 1. Read local image and encode to base64
with open("screenshot.png", "rb") as f:
    b64_data = base64.b64encode(f.read()).decode("ascii")

# 2. Initialize client with custom User-Agent
client = OpenAI(
    base_url="https://index-translate.bilibili.com/v1",
    api_key="none",
    default_headers={"User-Agent": "Index-Translate-Client/1.0"}
)

# 3. Create multimodal completion (choose Index-Translate-2B / Index-Translate-9B / Index-Translate-35B-A3B)
response = client.chat.completions.create(
    model="Index-Translate-9B",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Translate the text in the image into Chinese, outputting translation only."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_data}"}}
            ]
        }
    ],
    temperature=0.0,
    max_tokens=1024,
    extra_body={"chat_template_kwargs": {"enable_thinking": False}}
)

print(response.choices[0].message.content)
```

---

## 🖥️ Method 4: Local Deployment (llama.cpp / llama-server)

The official GGUF repositories for all three sizes (2B / 9B / 35B) include companion native vision projector weights (`*.mmproj-*.gguf`).

### 1. Download Model Weights and Vision Projectors

| Model | Hugging Face Repository | ModelScope Repository | Key Files |
| :--- | :--- | :--- | :--- |
| **2B** | [IndexTeam/Index-Translate-2B-GGUF](https://huggingface.co/IndexTeam/Index-Translate-2B-GGUF) | [IndexTeam/Index-Translate-2B-GGUF](https://modelscope.cn/models/IndexTeam/Index-Translate-2B-GGUF) | `Index-Translate-2B.Q4_K_M.gguf`<br>`Index-Translate-2B.mmproj-Q8_0.gguf` |
| **9B** | [IndexTeam/Index-Translate-9B-GGUF](https://huggingface.co/IndexTeam/Index-Translate-9B-GGUF) | [IndexTeam/Index-Translate-9B-GGUF](https://modelscope.cn/models/IndexTeam/Index-Translate-9B-GGUF) | `Index-Translate-9B.Q4_K_M.gguf`<br>`Index-Translate-9B.mmproj-Q8_0.gguf` |
| **35B** | [IndexTeam/Index-Translate-35B-A3B-preview-GGUF](https://huggingface.co/IndexTeam/Index-Translate-35B-A3B-preview-GGUF) | [IndexTeam/Index-Translate-35B-A3B-preview-GGUF](https://modelscope.cn/models/IndexTeam/Index-Translate-35B-A3B-preview-GGUF) | `Index-Translate-35B-A3B-preview.Q4_K_M.gguf`<br>`Index-Translate-35B-A3B-preview.mmproj-Q8_0.gguf` |

### 2. Launch llama-server

Mount the vision projector using `--mmproj`. Select the command matching your hardware:

#### 2B Lightweight (Runs smoothly on CPU / Integrated Graphics):
```bash
./llama-server \
  -m Index-Translate-2B.Q4_K_M.gguf \
  --mmproj Index-Translate-2B.mmproj-Q8_0.gguf \
  -ngl 99 \
  -c 16384 \
  --port 8000 \
  --alias Index-Translate-2B
```

#### 9B Balanced (Recommended for RTX 3060/4060):
```bash
./llama-server \
  -m Index-Translate-9B.Q4_K_M.gguf \
  --mmproj Index-Translate-9B.mmproj-Q8_0.gguf \
  -ngl 99 \
  -c 32768 \
  --port 8000 \
  --alias Index-Translate-9B
```

#### 35B-A3B Flagship (Recommended for 24GB VRAM or Dual-GPU):
```bash
./llama-server \
  -m Index-Translate-35B-A3B-preview.Q4_K_M.gguf \
  --mmproj Index-Translate-35B-A3B-preview.mmproj-Q8_0.gguf \
  -ngl 99 \
  -c 65536 \
  --port 8000 \
  --alias Index-Translate-35B-A3B \
  --chat-template-kwargs '{"enable_thinking":false}' \
  --reasoning off
```

Once running, execute `inference/llm/translate.py` for local offline image translation:
```bash
python inference/llm/translate.py --image test.png --target zh -m Index-Translate-9B
```

---

## 📚 Real-World Showcase Cases

### Case 1: Software Settings UI
- **Input**: Screenshot of application settings ("Enable hardware acceleration", "Automatically check for updates", "Restore default settings").
- **Output (All Sizes)**:
  > 启用硬件加速  
  > 自动检查更新  
  > 恢复默认设置  
- **Analysis**: Cascading OCR often drops modifiers or fragments words across tight button margins. Native visual encoders directly comprehend UI elements.

### Case 2: Highway Road Signs
- **Input**: Road photo with "Pedestrian Crossing Ahead · Speed Limit 30 mph".
- **Output (All Sizes)**:
  > 前方行人过街通道 · 限速 30 英里/小时  
- **Analysis**: Glare and perspective distortion confuse traditional OCR (e.g. reading `mph` as meters per hour). Index-Translate combines spatial layout perception with domain knowledge.

### Case 3: Academic Architecture Diagrams
- **Input**: Flowchart containing "Multi-Head Attention", "Feed-Forward Network", "Layer Normalization", "Positional Encoding".
- **Output (All Sizes)**:
  > 多头注意力机制  
  > 前馈神经网络  
  > 层归一化  
  > 位置编码  
- **Analysis**: Generic models give awkward literal translations. Index-Translate standardizes AI and computer science terminology.

### Case 4: Product Packaging & Ingredients
- **Input**: Japanese snack label (【原材料名】小麦粉（国内製造）、植物油脂、食塩、粉末しょうゆ、香辛料／調味料（アミノ酸等）、香料。).
- **Output (All Sizes)**:
  > 【配料表】小麦粉（日本制造）、植物油、食用盐、酱油粉、香辛料／调味料（氨基酸等）、食用香精。  
- **Analysis**: Accurately localizes 「国内製造」 to "Made in Japan", preserving parentheses and slash delimiters.

---

## ❓ FAQ & Troubleshooting

### 1. HTTP 412 Error?
The public gateway enforces WAF rules. If connecting with Python `urllib` or custom scripts, include:
```http
User-Agent: Index-Translate-Client/1.0
```

### 2. Supported Image Formats?
All standard raster formats: `PNG`, `JPEG/JPG`, `WEBP`, `BMP`, `GIF`.

### 3. Recommended Resolution?
- Recommended longest edge between 512px and 2048px.
- Ultra-high resolutions (e.g. 8K) should be downscaled before upload for optimal latency and bandwidth.
