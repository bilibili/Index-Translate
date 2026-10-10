# 多模态图片翻译 (Multimodal Image Translation) 使用教程

Index-Translate 原生支持多模态图像翻译能力，基于内置的 **视觉编码器（Visual Encoder `mmproj`）** 实现端到端图像理解与跨语言翻译。

> [!TIP]
> 🌟 **原生视觉端到端，零 OCR 依赖！**  
> 传统图像翻译通常采用 `OCR 文字识别 -> 文本清洗 -> 翻译模型` 的流水线串联方案，容易出现识别漏字、断句错误、排版顺序错乱等问题。  
> **Index-Translate 采用原生多模态架构**，视觉特征直接输入模型隐空间，不仅能精准提取文字，更能深度理解图像上下文语境、版面布局和语义层次，速度更快、质量更高。

---

## 🌟 核心特性与优势

1. **零外部 OCR 工具链**：单模型端到端处理，无需部署 PaddleOCR、Tesseract 或商业 OCR 接口。
2. **多场景全覆盖**：
   - 💻 **电脑/手机截图**：软件界面、网页长图、报错弹窗、聊天记录。
   - 📊 **学术与技术图表**：论文架构图、流程图、带文字的统计图表、表格数据。
   - 🎨 **漫画、海报与宣传图**：排版复杂、花体艺术字、拟声词与气泡对话框。
   - 🛣️ **实景照片与路牌**：街道招牌、菜单、包装说明书、展板。
3. **支持灵活的约束指令**：不仅能翻译图片，还支持结合 instTrans 规范要求（如“保留专业术语”、“以 Markdown 列表整理”、“以 JSON 格式输出”等）。
4. **全平台调用支持**：已上线免费公网 API、在线 Web Demo、Python 零依赖脚本与本地 llama.cpp / vLLM 部署方案。

---

## 🚀 方式一：在官方 Web Demo 中一键使用

无需编写任何代码，直接在网页端使用图片翻译：

1. 打开在线演示网站：[https://index-translate.bilibili.com/?p=/site/translate.html](https://index-translate.bilibili.com/?p=/site/translate.html)
2. 在左侧原文输入区，点击 **📸 上传图片** 按钮选择本地图片，或者直接在页面上按 **Ctrl+V / Cmd+V** 粘贴剪贴板截图，也可以直接将图片**拖拽**至输入框。
3. 页面将显示图片缩略预览卡片。选择目标语言（如中文、英语、日语等）。
4. 点击 **开始翻译**，右侧将实时流式呈现翻译结果！

---

## 💻 方式二：使用官方零依赖脚本 `call_api.py`

官方提供的 [`inference/llm/call_api.py`](../inference/llm/call_api.py) 脚本使用 Python 标准库编写，**无需安装任何第三方库**即可直接调用公网免费 35B 视觉翻译 API：

```bash
# 1. 基础图片翻译（自动识别图片语言，翻译为指定语种，支持本地路径或网络 URL）
python inference/llm/call_api.py --image path/to/screenshot.png --target zh

# 2. 翻译带艺术字或海报的图片为英文
python inference/llm/call_api.py --image poster.jpg --target en

# 3. 带特定指令要求的图片翻译（例如整理要点或指定术语）
python inference/llm/call_api.py "提取图片中的核心结论并翻译为中文" \
    --image report_chart.png \
    --target zh \
    --instruction "请按条目列出关键指标，保留数值与单位"

# 4. 流式输出（实时打字机效果）
python inference/llm/call_api.py --image meme.png --target zh --stream
```

---

## 🔌 方式三：标准 OpenAI 兼容 API 调用

Index-Translate 公网 API 完全兼容 OpenAI Chat Completions 多模态规范（`image_url` 格式），支持 Python、cURL、Node.js 等任意语言接入。

### 1. cURL 调用示例

> [!NOTE]
> 针对公网 WAF 保护，自定义请求请携带标准浏览器或应用 `User-Agent` 请求头。

```bash
# 将本地图片转为 base64 data URL 并发起请求
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
          {"type": "text", "text": "请将图片中的文本翻译为中文，直接输出翻译结果。"},
          {"type": "image_url", "image_url": {"url": "data:image/png;base64,'"$IMG_B64"'"}}
        ]
      }
    ],
    "max_tokens": 1024,
    "temperature": 0.0
  }'
```

### 2. Python (OpenAI SDK) 调用示例

```python
import base64
import httpx
from openai import OpenAI

# 1. 读取本地图片并转换为 base64
with open("screenshot.png", "rb") as f:
    b64_data = base64.b64encode(f.read()).decode("ascii")

# 2. 初始化客户端（配置 User-Agent 防止被 WAF 拦截）
client = OpenAI(
    base_url="https://index-translate.bilibili.com/v1",
    api_key="none",
    default_headers={"User-Agent": "Index-Translate-Client/1.0"}
)

# 3. 发起多模态聊天补全
response = client.chat.completions.create(
    model="Index-Translate-35B-A3B",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "请将图片中的文本翻译为中文。"},
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

## 🖥️ 方式四：本地私有化部署（llama.cpp / llama-server）

官方发布的 GGUF 仓库已随包提供对应模型的原生视觉权重文件（`*.mmproj-*.gguf`）。

### 1. 下载模型权重

- LLM 主干权重：`Index-Translate-35B-A3B-preview.Q8_0.gguf`（或 Q4_K_M / Q6_K 等位宽）
- 视觉投影权重：`Index-Translate-35B-A3B-preview.mmproj-Q8_0.gguf`（约 583MB）

下载地址：
- Hugging Face: [IndexTeam/Index-Translate-35B-A3B-preview-GGUF](https://huggingface.co/IndexTeam/Index-Translate-35B-A3B-preview-GGUF)
- ModelScope: [IndexTeam/Index-Translate-35B-A3B-preview-GGUF](https://modelscope.cn/models/IndexTeam/Index-Translate-35B-A3B-preview-GGUF)

### 2. 启动 llama-server 服务

使用 `--mmproj` 参数挂载视觉投影层：

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

服务启动后，在本地执行 `inference/llm/translate.py` 即可进行本地离线图像翻译：

```bash
python inference/llm/translate.py --image test.png --target zh
```

---

## 📚 典型案例展示 (Showcase Cases)

### 案例 1：英文软件设置截图翻译

- **输入图像**：一段包含各类设置选项的软件 UI 截图（"Enable hardware acceleration", "Automatically check for updates", "Restore default settings"）。
- **指令**：`将图片中的软件界面文本翻译为中文。`
- **模型输出**：
  > 启用硬件加速  
  > 自动检查更新  
  > 恢复默认设置

### 案例 2：海外路标与街景照片

- **输入图像**：包含 "Pedestrian Crossing Ahead · Speed Limit 30 mph" 的实景道路指示牌。
- **指令**：`翻译路牌文本。`
- **模型输出**：
  > 前方行人过街通道 · 限速 30 英里/小时

### 案例 3：学术论文架构图 / 流程图

- **输入图像**：深度学习模型架构框图，包含 "Multi-Head Attention", "Feed-Forward Network", "Layer Normalization", "Positional Encoding"。
- **指令**：`请翻译图表中的架构模块名称。`
- **模型输出**：
  > 多头注意力机制  
  > 前馈神经网络  
  > 层归一化  
  > 位置编码

### 案例 4：商品标签与说明书

- **输入图像**：日文零食包装袋背面配料表。
- **指令**：`翻译商品配料表为中文，保留清晰排版。`
- **模型输出**：
  > 【原材料名称】小麦粉（日本制造）、植物油、食盐、酱油粉、香辛料／调味料（氨基酸等）、香精。

---

## ❓ 常见问题排查 (FAQ)

### 1. 为什么返回 HTTP 412 错误？
公网接入层配置了 Web 应用防火墙 (WAF)。如果使用 Python `urllib` 或第三方客户端，默认 User-Agent（如 `Python-urllib/3.x`）可能会被拦截。请在请求头中加上：
```http
User-Agent: Index-Translate-Client/1.0
```

### 2. 支持哪些图片格式？
支持常见的绝大多数栅格图像格式：`PNG`、`JPEG/JPG`、`WEBP`、`BMP`、`GIF`。

### 3. 图片分辨率建议多大？
- 建议图像最长边在 512px ~ 2048px 之间。
- 过低分辨率（如文字高度小于 10 像素）可能导致文字细节模糊；
- 超高分辨率（如 8K 扫描件）建议在上传前缩放至适中尺寸，以获得最快推理速度和最小网络传输开销。
