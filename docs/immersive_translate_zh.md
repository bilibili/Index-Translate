# 沉浸式翻译 (Immersive Translate) 插件配置教程

本教程介绍如何将 **[沉浸式翻译 (Immersive Translate)](https://immersivetranslate.com/)** 浏览器扩展连接至 **Index-Translate** 翻译大模型，实现极速、高质量、零隐私泄露的网页与文档双语对照翻译。

---

## 🌟 核心优势

- **免费畅享 35B 大模型**：通过官方提供的免费公网 API（搭载 Index-Translate-35B-A3B 旗舰翻译大模型），无需本地 GPU 算力即可畅享顶级翻译质量。
- **支持 100% 本地离线私有化**：亦可连接本地 vLLM / SGLang 部署的 2B / 9B 模型，所有网页和文档数据不出内网。
- **自动思考抑制与极速响应**：通过官方桥接代理自动抑制模型的 CoT 思维链输出，首字延迟低至 150ms，杜绝页面出现思考标签或乱码。
- **完美双语排版**：无缝融入沉浸式翻译的网页双语排版、划词翻译、PDF 与 EPUB 电子书阅读器。

---

## 🛠️ 架构说明：为什么需要本地代理？

浏览器插件在直接访问外部大模型接口时，通常面临以下技术限制：
1. **浏览器同源策略 (CORS) 与安全限制**：浏览器对插件后台请求的自定义 Headers 和跨域响应校验极为严苛。
2. **大模型思维链 (CoT) 输出抑制**：Index-Translate-35B 具备深度推理能力。在网页沉浸式翻译场景下，需要强制关闭思考模式（`enable_thinking=False`）并启用贪心解码（`temperature=0.0`），否则思维链内容会导致插件解析失败或译文延迟过高。
3. **WAF 协议保护**：避免浏览器插件直连公网端点时误触安全挑战机制。

为此，官方在 [`inference/llm/call_api.py`](../inference/llm/call_api.py) 中内置了**轻量级本地代理网桥**，零额外依赖，一条命令即可启动。

```
[浏览器 / 沉浸式翻译插件]
         │ (HTTP 127.0.0.1:8080/v1)
         ▼
[本地代理网桥 call_api.py --serve]
   - 自动 CORS 透传
   - 注入 enable_thinking=False
   - 注入 temperature=0.0
         │ (HTTPS 加密直连)
         ▼
[Index-Translate 公网网关 / 本地 vLLM]
```

---

## 📖 详细配置步骤

### 第一步：安装沉浸式翻译扩展

如果尚未安装插件，可在主流浏览器应用商店免费安装：
- [Chrome 网上应用店](https://chromewebstore.google.com/detail/immersive-translate/bpoadfkcbjbfhfodiogcnhhhpibjhbnh)
- [Edge 外接程序](https://microsoftedge.microsoft.com/addons/detail/immersive-translate/amkbmndfnliijdhojkpoglbnaaahippg)
- [Firefox 附加组件](https://addons.mozilla.org/firefox/addon/immersive-translate/)
- [Safari (Mac / iOS)](https://apps.apple.com/app/immersive-translate/id6447957425)

---

### 第二步：启动后端服务（二选一）

#### 选项 A：使用免费公网 35B API（推荐，无需本地显卡）

本代理为**零依赖**设计（仅使用 Python 3 标准库，无需 `pip install`）。

##### 🪟 Windows 用户（三种任选）

- **方法一：一键双击批处理（最推荐）**  
  克隆或下载解压仓库后，在文件管理器中直接**双击运行根目录的 `run_proxy_windows.bat`**。脚本会自动检测 Python 环境、展示配置提示并启动代理服务。
- **方法二：命令提示符 (CMD) 或 PowerShell**  
  ```cmd
  cd Index-Translate
  python inference\llm\call_api.py --serve
  REM 若系统使用的是 py 启动器：
  py -3 inference\llm\call_api.py --serve
  ```
- **方法三：免 Git 单文件极简运行（适合未安装 Git 的 Windows 用户）**  
  无需克隆整个仓库，直接下载单文件 [`call_api.py`](https://raw.githubusercontent.com/bilibili/Index-Translate/main/inference/llm/call_api.py)，在存放该文件的目录下打开 CMD 运行：
  ```cmd
  python call_api.py --serve
  ```

##### 🍎 macOS / 🐧 Linux 用户

在终端中克隆仓库并运行：

```bash
git clone https://github.com/bilibili/Index-Translate.git
cd Index-Translate

# 启动本地代理网桥（默认监听 127.0.0.1:8080）
python inference/llm/call_api.py --serve
```

终端将显示启动成功信息：

![启动本地代理终端截图](assets/immersive_terminal_proxy.png)

> [!TIP]
> **局域网共享**：若需要让同一局域网内的手机、平板或其他电脑使用此服务，只需添加 `--host 0.0.0.0` 参数（Windows 批处理脚本亦支持传参 `run_proxy_windows.bat --host 0.0.0.0`）：
> ```bash
> python inference/llm/call_api.py --serve --host 0.0.0.0
> ```

#### 选项 B：使用本地 GPU 私有化部署（vLLM）

如果你拥有本地 NVIDIA 显卡，可直接使用 vLLM 部署模型（以 9B 为例）：

```bash
vllm serve IndexTeam/Index-Translate-9B \
    --served-model-name Index-Translate-9B \
    --host 127.0.0.1 \
    --port 8000 \
    --max-model-len 4096
```

---

### 第三步：在沉浸式翻译中配置自定义服务

1. 点击浏览器工具栏的 **沉浸式翻译** 图标，打开 **设置**（或右键扩展图标选择「选项」）。
2. 在左侧菜单点击 **翻译服务**，滚动到页面下方的 **开发者设置**。
3. 找到并开启 **OpenAI**（或选择「添加自定义模型」）。
4. 按照下表填写配置参数：

| 配置项 | 选项 A（公网 35B 代理模式） | 选项 B（本地 vLLM 模式） | 说明 |
|---|---|---|---|
| **翻译服务** | `OpenAI` | `OpenAI` | 选择标准 OpenAI 兼容模式 |
| **自定义接口地址 (API URL)** | `http://127.0.0.1:8080/v1` | `http://127.0.0.1:8000/v1` | 注意以 `/v1` 结尾 |
| **模型名称 (Model)** | `Index-Translate-35B-A3B` | `Index-Translate-9B` | 需与服务端声明的模型名称一致 |
| **API Key (密钥)** | `index` | `none` | 本地服务无鉴权限制，可随意填写 |
| **每秒最大请求数** | `3` ~ `5` | 根据显卡性能设置 (如 `5` ~ `10`) | 防止瞬时并发过高引起排队 |

配置界面实操参考图：

![沉浸式翻译设置界面截图](assets/immersive_config_step.png)

5. 点击右侧或下方的 **「测试服务」** 按钮：
   - 看到返回 `✓ 服务可用` 或类似测试译文（例如 `"Hello World" -> "你好，世界"`），即说明全链路连通成功！

---

### 第四步：畅享高品质网页双语阅读

1. 打开任意外文学术论文、技术文档或新闻资讯页面（如 [arXiv:2609.40181](https://arxiv.org/abs/2609.40181)、GitHub、Hacker News 或 Wikipedia）。
2. 按快捷键 `Alt + A`（Mac 上为 `Option + A`），或点击页面右侧的沉浸式翻译悬浮球。
3. 插件将自动请求 Index-Translate 大模型，并在原文字句下方以优雅的双语对照样式呈现精准译文：

![网页双语对照翻译实测截图](assets/immersive_bilingual_reading.png)

---

## ❓ 常见问题排查 (FAQ)

### 1. 点击「测试服务」提示连接超时、拒绝连接或 504 错误？
- **检查代理服务是否正常运行**：确保 CMD、PowerShell 或终端窗口中的代理未被关闭，窗口中应提示正在监听 `127.0.0.1:8080`。
- **Windows / macOS 网络代理软件劫持（重点避坑）**：
  若开启了 VPN 或科学上网客户端（如 **Clash Verge、v2rayN、Sing-box、Netch** 等），尤其是启用了 **TUN 虚拟网卡模式** 或 **系统代理**，客户端可能会将本机的 `127.0.0.1` 回环请求拦截并转往远端代理服务器，导致连接超时或返回 504 错误。
  - **解决步骤**：在客户端设置中开启「**绕过局域网 / 回环地址 (Bypass LAN / Loopback)**」，或在分流规则中将 `127.0.0.1` 与 `localhost` 设为 `DIRECT`（直连）。
- **端口冲突**：如果 `8080` 端口被其他软件占用，可在启动时指定其他端口（例如 `8088`）：
  ```bash
  python inference/llm/call_api.py --serve 8088
  ```
  同时将沉浸式翻译中的接口地址改为 `http://127.0.0.1:8088/v1`。

### 2. Windows 提示 `'python' 不是内部或外部命令，也不是可运行的程序`？
- 说明系统中尚未安装 Python 3，或安装时未添加到系统环境变量 PATH。
- **解决方法（二选一）**：
  1. 打开 Windows **微软商店 (Microsoft Store)**，搜索并安装 `Python 3.12`，系统会自动配置好 PATH 环境变量。
  2. 若从 [Python 官方网站](https://www.python.org/downloads/) 下载安装包，在安装首页底部务必**勾选 "Add python.exe to PATH"** 后再点击 Install。

### 3. 为什么偶尔会出现思考标签 `<think>`？
- 官方 `call_api.py --serve` 本地代理会在请求体中自动注入 `{"chat_template_kwargs": {"enable_thinking": False}, "temperature": 0.0}`，彻底杜绝思考标签。
- 如果你是通过第三方反向代理或直接对接自建服务，请务必在客户端请求参数中显式关闭思考模式。

### 4. 如何指定术语表或者保持特定译名？
- `Index-Translate` 原生支持 **instTrans** 格式的术语强对照。
- 你可以在沉浸式翻译的 **「自定义系统提示词」** 中增加特定术语映射要求，或者直接使用官方 SDK / `call_api.py` 的 `-g / --glossary` 功能。

---

## 🔗 相关链接

- [Index-Translate GitHub 官方仓库](https://github.com/bilibili/Index-Translate)
- [免费公网 API 调用脚本说明](../inference/llm/README_zh.md#免费公网-api-调用与沉浸式翻译本地代理)
- [内置轻量网页翻译扩展](../extension/README_zh.md)
