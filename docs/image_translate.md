# Multimodal Image Translation Tutorial

Index-Translate natively supports multimodal image translation, powered by its built-in **Visual Encoder (`mmproj`)** for end-to-end visual comprehension and cross-lingual translation.

> [!TIP]
> 🌟 **Native Visual End-to-End, Zero OCR Dependency!**  
> Traditional image translation relies on a multi-stage pipeline: `OCR Text Recognition -> Text Cleaning -> Translation Model`. This often introduces pipeline cascading errors such as missed characters, awkward line breaks, and disrupted reading orders.  
> **Index-Translate uses a native multimodal architecture.** Visual features are projected directly into the model's latent representation space, accurately extracting text while simultaneously understanding image context, layout geometry, and semantic structure—faster, cleaner, and higher quality.

---

## 🌟 Key Capabilities & Highlights

1. **Zero External OCR Toolchains**: Fully end-to-end within a single model. No need to set up PaddleOCR, Tesseract, or paid third-party OCR services.
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
2. In the source pane, click **📸 Upload Image**, press **Ctrl+V / Cmd+V** to paste a clipboard screenshot, or simply **drag & drop** an image into the input box.
3. An image preview thumbnail card will appear. Select your target language (e.g. English, Chinese, Japanese, etc.).
4. Click **Translate** to stream the translation in real time!

---

## 💻 Method 2: Zero-Dependency Python Script `call_api.py`

The official [`inference/llm/call_api.py`](../inference/llm/call_api.py) script uses only Python standard libraries—**no external pip packages required**:

```bash
# 1. Basic image translation (automatically identifies text language, translates to target)
python inference/llm/call_api.py --image path/to/screenshot.png --target zh

# 2. Translate posters or graphics into English
python inference/llm/call_api.py --image poster.jpg --target en

# 3. Image translation with specific instructions or terminology
python inference/llm/call_api.py "Extract key conclusions and translate to Chinese" \
    --image report_chart.png \
    --target zh \
    --instruction "List items cleanly, keeping numbers and units intact"

# 4. Streamed output (SSE typewriter effect)
python inference/llm/call_api.py --image meme.png --target zh --stream
```

---

## 🔌 Method 3: Standard OpenAI-Compatible API

The Index-Translate public API conforms strictly to OpenAI Chat Completions multimodal specifications (`image_url` format).

### 1. cURL Example

> [!NOTE]
> Due to WAF protection, please include a standard `User-Agent` header with custom API requests.

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

with open("screenshot.png", "rb") as f:
    b64_data = base64.b64encode(f.read()).decode("ascii")

client = OpenAI(
    base_url="https://index-translate.bilibili.com/v1",
    api_key="none",
    default_headers={"User-Agent": "Index-Translate-Client/1.0"}
)

response = client.chat.completions.create(
    model="Index-Translate-35B-A3B",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Translate the text in the image into Chinese."},
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

## 🖥️ Method 4: Self-Hosted Deployment (llama.cpp / llama-server)

The official GGUF repository includes the visual projector weight file (`*.mmproj-*.gguf`):

- LLM backbone: `Index-Translate-35B-A3B-preview.Q8_0.gguf`
- Vision projector: `Index-Translate-35B-A3B-preview.mmproj-Q8_0.gguf` (approx. 583MB)

### Start llama-server:

```bash
./llama-server \
  -m Index-Translate-35B-A3B-preview.Q8_0.gguf \
  --mmproj Index-Translate-35B-A3B-preview.mmproj-Q8_0.gguf \
  -ngl 99 \
  -c 65536 \
  -np 4 \
  --port 8000 \
  --host 0.0.0.0 \
  --alias Index-Translate-35B-A3B \
  --chat-template-kwargs '{"enable_thinking":false}' \
  --reasoning off
```

Then run local inference via `inference/llm/translate.py`:

```bash
python inference/llm/translate.py --image test.png --target zh
```

---

## 📚 Real-World Showcase Cases

### Case 1: Software Settings UI
- **Input Image**: Screenshot of software configuration options ("Enable hardware acceleration", "Automatically check for updates", "Restore default settings").
- **Instruction**: `Translate software interface text to Chinese.`
- **Output**:
  > 启用硬件加速  
  > 自动检查更新  
  > 恢复默认设置

### Case 2: Road Signs & Street View
- **Input Image**: Photo of street sign ("Pedestrian Crossing Ahead · Speed Limit 30 mph").
- **Output**:
  > 前方行人过街通道 · 限速 30 英里/小时

### Case 3: Academic Model Diagram
- **Input Image**: Deep learning architecture diagram showing "Multi-Head Attention", "Feed-Forward Network", "Layer Normalization", "Positional Encoding".
- **Output**:
  > 多头注意力机制  
  > 前馈神经网络  
  > 层归一化  
  > 位置编码

---

## ❓ FAQ & Troubleshooting

1. **Why do I receive an HTTP 412 error?**  
   The gateway WAF filters standard bot User-Agents (like `Python-urllib/3.x`). Please configure `User-Agent: Index-Translate-Client/1.0` in your request headers.
2. **What formats are supported?**  
   All major raster formats: `PNG`, `JPEG`, `WEBP`, `BMP`, `GIF`.
3. **Recommended image resolution?**  
   Longest edge between 512px and 2048px is recommended for optimal speed and visual fidelity.
