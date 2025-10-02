# AI 自动总结与语音转写服务（FastAPI）

这是一个面向 Android 应用的后端服务，提供以下能力并通过 HTTP 接口暴露给 App 调用：
- 语音转文字（Whisper，可选安装 faster-whisper 或 openai-whisper）
- 文本摘要（支持 lead / frequency 两种策略）
- 文本优化（简洁、正式、要点风格）
- 统一一体化接口：文本或音频输入，一次得到转写/摘要/优化结果

本服务不包含可视化界面（UI）。外观由 Android 客户端决定；服务以 REST API 形式对接到 App。

---

## 目录结构

- `aipart/app.py` FastAPI 应用与路由
- `aipart/api/schemas.py` Pydantic 请求/响应模型
- `aipart/services/` 文本处理与 STT 实现
- `run_server.py` 本地启动脚本（uvicorn）
- `scripts/smoke_test.py` 本地冒烟测试脚本
- `tests/` 基础接口测试

---

## 快速开始（Windows / cmd.exe）

前置：建议 Python 3.10+ 且已安装 Git；建议使用虚拟环境。

1) 创建并启用虚拟环境

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -U pip
.venv\Scripts\python -m pip install -r requirements.txt
```

2)（可选）安装语音转写引擎 Whisper（二选一）

- 更快更省资源：faster-whisper（基于 CTranslate2）
```bat
.venv\Scripts\python -m pip install faster-whisper
```
- 官方参考实现：openai-whisper（依赖本机 ffmpeg）
```bat
.venv\Scripts\python -m pip install openai-whisper
```

提示：
- 使用 openai-whisper 时，请确保已安装 FFmpeg 并在 PATH 中（在 cmd 执行 `ffmpeg -version` 可检查）。
- faster-whisper CPU 默认 `int8` 量化；如有 NVIDIA GPU，可通过环境变量切换到 `cuda` 与 `float16`，见下文。

3) 启动服务

```bat
.venv\Scripts\python run_server.py
```

默认监听：`http://127.0.0.1:8080`（对外监听 0.0.0.0）。

4) 健康检查

```bat
curl http://127.0.0.1:8080/healthz
```

---

## Whisper（STT）环境变量（可选）

- faster-whisper
  - `FAST_WHISPER_MODEL`：模型大小（默认 `tiny`，可选 `tiny|base|small|medium|large-v3` 等）
  - `FAST_WHISPER_DEVICE`：设备（默认 `cpu`，可选 `cpu|cuda`）
  - `FAST_WHISPER_COMPUTE`：计算精度（默认 `int8`，常用 `float16|int8_float16|float32`）

- openai-whisper
  - `OPENAI_WHISPER_MODEL`：模型大小（默认 `tiny`）

在 Windows/cmd 中临时设置示例：
```bat
set FAST_WHISPER_MODEL=base
set FAST_WHISPER_DEVICE=cpu
set FAST_WHISPER_COMPUTE=int8
.venv\Scripts\python run_server.py
```

---

### Windows 专项说明（OpenMP 冲突导致 STT 502/崩溃）

- 现象：调用 `/v1/stt` 或 `/v1/ai`（音频流程）时，日志出现 `libiomp5md.dll already initialized`，服务异常退出或客户端看到 502。
- 成因：Windows 上 OpenMP 运行时被多个依赖（如 onnxruntime/ctranslate2 与 MKL）重复加载，产生冲突。
- 解决方案：
  - 方案 A（已内置于代码，默认启用）：`aipart/services/stt.py` 会在 Windows 启动时设置以下环境变量，通常无需额外操作：
    - `KMP_DUPLICATE_LIB_OK=TRUE`
    - `OMP_NUM_THREADS=1`
  - 方案 B（部署层推荐，适合用进程管理器/脚本统一设置）：在启动服务前显式设置环境变量。
    - cmd.exe 示例：
      ```bat
      set KMP_DUPLICATE_LIB_OK=TRUE
      set OMP_NUM_THREADS=1
      .venv\Scripts\python run_server.py
      ```
- 影响：上述设置可避免冲突并提升稳定性；对性能影响通常可忽略。如需更高吞吐，建议采用「多进程 + 负载均衡」方式横向扩展。

---

## API 速览

所有响应均为 JSON；错误统一为：`{"detail": "..."}`。

- 健康检查
  - `GET /healthz` → `{ "status": "ok" }`

- 文本摘要
  - `POST /v1/summarize`（application/json）
  - 请求：`{ text, max_sentences(默认3,1-20), strategy("lead"|"frequency",默认"frequency") }`
  - 响应：`{ summary, sentences[] }`

- 文本优化
  - `POST /v1/optimize`（application/json）
  - 请求：`{ text, style("concise"|"formal"|"bullet",默认"concise"), language? }`
  - 响应：`{ result }`

- 语音转文字（STT）
  - `POST /v1/stt`（multipart/form-data，字段名 `file`）
  - 成功：`200 → { text, language?, engine }`
  - 未安装引擎：`501 → { detail }`
  - 无效/损坏音频：`400 → { detail }`
  - 备注：纯音调音频（例如 440Hz 正弦波）可能得到空文本 `""`，属正常。

- 一体化接口（推荐安卓使用，最简单）
  - `POST /v1/ai`
  - 两种用法：
    1) 文本流程（application/json）
       - 请求：`{ text, summarize(true/false,默认true), optimize(true/false,默认false), max_sentences, strategy, style, language? }`
       - 响应：`{ text, summary?, optimized?, language?, engine? }`
       - 说明：自动语言检测；若 `optimize=true`，基于摘要或原文做优化。
    2) 音频流程（multipart/form-data）
       - 字段：`file`、`summarize`(默认true)、`optimize`(默认false)、`max_sentences`、`strategy`、`style`、`language?`
       - 响应：同上，并包含 `engine`。

### Windows/cmd 示例（换行用 ^）

- 摘要
```bat
curl -X POST http://127.0.0.1:8080/v1/summarize ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"这是第一句。这是第二句。\",\"max_sentences\":1}"
```

- 优化（要点）
```bat
curl -X POST http://127.0.0.1:8080/v1/optimize ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"第一句。第二句！第三句？\",\"style\":\"bullet\"}"
```

- 语音转文字（需已安装 Whisper）
```bat
curl -X POST http://127.0.0.1:8080/v1/stt ^
  -F "file=@data/sample_440.wav"
```

- 一体化（文本）
```bat
curl -X POST http://127.0.0.1:8080/v1/ai ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"This is a test. This test is simple. Summaries help users.\",\"summarize\":true,\"optimize\":true,\"style\":\"bullet\"}"
```

- 一体化（音频）
```bat
curl -X POST http://127.0.0.1:8080/v1/ai ^
  -F "file=@data/sample_440.wav" ^
  -F "summarize=1" ^
  -F "optimize=0" ^
  -F "max_sentences=2" ^
  -F "strategy=lead"
```

---

## 本地自测与单元测试

- 冒烟测试脚本（需服务已启动）
```bat
set BASE=http://127.0.0.1:8080
set SAMPLE_WAV=data\sample_440.wav
.venv\Scripts\python scripts\smoke_test.py
```
- 单元测试
```bat
.venv\Scripts\python -m pytest -q
```
测试已覆盖：健康检查、摘要策略与边界、优化风格、STT 缺失文件/无效音频/未安装引擎，以及一体化接口（JSON 与 multipart）。即便未安装 Whisper，测试会断言返回 501，仍可通过。

---

## Android 端对接指南（最简做法）

强烈建议只对接一个接口：`POST /v1/ai`
- 文本输入 → 发送 application/json
- 语音输入 → 发送 multipart/form-data，字段名 `file`

以下以 Kotlin + Retrofit 为例：

### 1) 数据模型（与后端 `aipart/api/schemas.py` 对应）
```kotlin
// AiTextRequest
data class AiTextRequest(
    val text: String,
    val summarize: Boolean = true,
    val optimize: Boolean = false,
    val max_sentences: Int = 3,
    val strategy: String = "frequency", // "lead" | "frequency"
    val style: String = "concise",      // "concise" | "formal" | "bullet"
    val language: String? = null
)

// AiResponse
data class AiResponse(
    val text: String,
    val summary: String?,
    val optimized: String?,
    val language: String?,
    val engine: String?
)

// 后端错误统一为 {"detail": "..."}
data class ErrorResponse(val detail: String)
```

### 2) Retrofit 接口
```kotlin
interface ApiService {
    @POST("/v1/ai")
    suspend fun aiText(@Body body: AiTextRequest): Response<AiResponse>

    @Multipart
    @POST("/v1/ai")
    suspend fun aiAudio(
        @Part file: MultipartBody.Part,
        @Part("summarize") summarize: RequestBody,
        @Part("optimize") optimize: RequestBody,
        @Part("max_sentences") maxSentences: RequestBody,
        @Part("strategy") strategy: RequestBody,
        @Part("style") style: RequestBody,
        @Part("language") language: RequestBody?
    ): Response<AiResponse>
}
```

### 3) 构造请求示例
```kotlin
// 文本流程
val req = AiTextRequest(
    text = "This is a test. This test is simple.",
    summarize = true,
    optimize = true,
    max_sentences = 2,
    strategy = "frequency",
    style = "bullet"
)
val resp = api.aiText(req)
if (resp.isSuccessful) {
    val data = resp.body()!!
    // data.text / data.summary / data.optimized / data.language
} else {
    // 从 resp.errorBody() 解析 {detail}
}

// 音频流程（audioFile 为本地录音文件）
val mediaType = "audio/wav".toMediaType()
val requestFile = audioFile.asRequestBody(mediaType)
val filePart = MultipartBody.Part.createFormData("file", audioFile.name, requestFile)

fun s(v: String) = v.toRequestBody("text/plain".toMediaType())
val summarize = s("1")
val optimize = s("0")
val maxSentences = s("2")
val strategy = s("lead")
val style = s("concise")
val language: RequestBody? = null

val r2 = api.aiAudio(filePart, summarize, optimize, maxSentences, strategy, style, language)
if (r2.isSuccessful) {
    val data = r2.body()!!
    // data.text / data.summary ...
} else {
    // 501 表示服务端未安装 STT 引擎；400 表示音频无效
}
```

### 4) 处理状态码与错误
- 200：正常渲染结果
- 400：输入不合法或音频解析失败 → 提示用户检查/重试
- 422：缺少必填字段（例如未上传 `file`）
- 501：服务端未安装 STT 引擎 → 提示后端安装 faster-whisper 或 openai-whisper

### 5) 其他接入建议
- Base URL：开发与生产环境分开配置；内网联调用 `http://<后端机 IP>:8080`
- 超时：初次加载 Whisper 模型可能较慢，建议将网络超时设为 30~60s
- 上传大小：建议在 App 端限制录音时长（如 <= 60 秒）；服务端可通过反向代理限制体积
- 编解码：优先使用 WAV/PCM 或 AAC/M4A 容器；如使用 openai-whisper，确保 FFmpeg 可解码
- CORS：服务端当前放开（`*`）；如需 WebView/H5 直接调用可复用；生产可按域名收紧

---

## 开发与测试

- 在线 API 文档：服务启动后访问 `http://127.0.0.1:8080/docs` 或 `/redoc`
- 代码风格与类型：本项目以简洁为主，若引入新依赖请在 `requirements.txt` 维护

---

## 部署建议（生产）

- 使用 Uvicorn 多进程或搭配进程管理器（如 Supervisor）与反向代理（如 Nginx）
- 示例（仅供参考）：
```bat
.venv\Scripts\uvicorn aipart.app:app --host 0.0.0.0 --port 8080 --workers 2
```
- 资源选择：
  - 仅 CPU：`FAST_WHISPER_DEVICE=cpu`，`FAST_WHISPER_COMPUTE=int8`
  - 有 GPU：`FAST_WHISPER_DEVICE=cuda`，`FAST_WHISPER_COMPUTE=float16`
- 安全：生产环境请收紧 CORS、限制上传大小、记录审计日志

---

## 常见问题（FAQ）

- Q: 调用 `/v1/stt` 返回 501？
  - A: 说明服务端未安装 Whisper 引擎。安装 `faster-whisper` 或 `openai-whisper` 其一即可。

- Q: 返回 400，提示音频解析/转写失败？
  - A: 检查文件是否为有效音频，确保采样率/编码正确；若用 openai-whisper，请确认本机 FFmpeg 可用。

- Q: 纯音调/无语音内容的音频怎么办？
  - A: 可能返回 200 且 `text` 为空字符串，这是正常表现。

- Q: 缺少 `file` 字段时会怎样？
  - A: FastAPI 会返回 422（参数校验错误）。

- Q: 语言选择如何确定？
  - A: 文本流程会自动检测语言；音频流程由 Whisper 推断；也可通过 `language` 指定优化输出语言。

- Q: Windows 上出现 `libiomp5md.dll already initialized` 或客户端收到 502？
  - A: 这是 OpenMP 冲突。可直接依赖项目内置的修复（已默认启用），或按上文“Windows 专项说明”在启动前设置 `KMP_DUPLICATE_LIB_OK=TRUE` 与 `OMP_NUM_THREADS=1`。

---

## 版本与许可

- 服务版本：`0.1.0`（见 `aipart/app.py` 中 FastAPI 初始化）
- 许可：按你们仓库策略（未显式提供）

如需更多示例或 Android 端 Demo 工程模板，可在集成阶段提出，我方可追加提供。

---

## GitHub API 使用指南（一步一步）

本项目内置了一个轻量的 GitHub API 客户端（`aipart/services/github_api.py`），支持：
- 列出当前用户仓库（list repos）
- 创建 Issue（create issue）
- 触发 GitHub Actions 工作流（workflow_dispatch）

已写好的单元测试保证：未设置令牌时不会发起任何网络请求，且直接抛错提示（见 `tests/test_github_api.py`）。

### 1) 准备 GitHub Token（PAT）

推荐使用 Fine-grained personal access token（新式令牌）或 Classic PAT：
- 必要权限（按需取用）：
  - 列表仓库：最小只需 read 权限
  - 创建 Issue：`issues: write`
  - 触发工作流：`workflow: write`
  - 访问私有仓库：`repo`（经典令牌）或在 fine-grained 里勾选具体仓库的读/写权限

生成路径：
- GitHub 右上角头像 → Settings → Developer settings → Personal access tokens
- 创建后请复制保存；不要提交到仓库。

### 2) 在 Windows/cmd 设置环境变量 GITHUB_TOKEN

临时（仅当前终端会话有效）：
```bat
set GITHUB_TOKEN=ghp_xxx_your_token_here
```
永久（写入用户环境变量，生效于新开的终端）：
```bat
setx GITHUB_TOKEN "ghp_xxx_your_token_here"
```
提示：`setx` 执行后需重新打开终端或 IDE 才会生效。

也可在命令行调用时通过 `--token` 明确传入（更灵活，避免污染环境）。

### 3) 用命令行脚本直接调用（零代码）

项目已新增 CLI：`scripts/github_cli.py`

- 列出仓库（默认每页 5 个）：
```bat
python scripts\github_cli.py list-repos --per-page 10
```
JSON 输出：
```bat
python scripts\github_cli.py list-repos --per-page 10 --json
```

- 在指定仓库创建 Issue：
```bat
python scripts\github_cli.py create-issue <owner> <repo> "标题" --body "内容" --labels "bug,help wanted"
```
示例：
```bat
python scripts\github_cli.py create-issue yourname demo-repo "测试 Issue" --body "由 CLI 创建" --labels "bug"
```

- 触发 Actions 工作流（workflow_dispatch）：
```bat
python scripts\github_cli.py dispatch-workflow <owner> <repo> ci.yml --ref main --inputs "{\"name\":\"value\"}"
```
说明：`ci.yml` 为 `.github/workflows/ci.yml` 文件名；`--inputs` 是传给 workflow 的 inputs JSON。

如未设置环境变量，可在命令尾部带上 `--token`：
```bat
python scripts\github_cli.py list-repos --per-page 5 --token ghp_xxx
```

### 4) 在你的 Python 代码中调用

你可以在任何地方复用同一个客户端类：
```python
from aipart.services.github_api import GitHubAPI, get_github_client

# 优先读取环境变量 GITHUB_TOKEN
client = get_github_client()
if not client.available:
    raise RuntimeError("请先设置 GITHUB_TOKEN 或手动传入 token")

# 列出仓库
repos = client.list_repos(per_page=5)

# 创建 Issue
issue = client.create_issue("owner", "repo", "标题", body="可选内容", labels=["bug"]) 

# 触发 workflow_dispatch
ok = client.dispatch_workflow("owner", "repo", "ci.yml", ref="main", inputs={"foo": "bar"})
```
如果你想对接 GitHub Enterprise，可传入自定义 `base_url`：
```python
client = GitHubAPI(token="<your-token>", base_url="https://ghe.your-org.com/api/v3")
```

### 5) 安全建议
- 绝不要把 Token 写进仓库或日志；避免硬编码。
- 本地/CI 可用环境变量传入；在 GitHub Actions 中使用加密的 `secrets.GITHUB_TOKEN` 或自建 PAT。
- 权限最小化：仅勾选需要的仓库与作用域。

### 6) 常见问题与排查
- 报错 “GITHUB_TOKEN is not set”
  - 未设置环境变量，或当前终端未重启；可用 `--token` 明确传入测试是否正常。
- 403/404 权限错误
  - 检查令牌是否拥有对应仓库与 scope；对于私有仓库需要 `repo`/对应细粒度授权。
- 触发 workflow 无反应
  - 确保 workflow 文件名正确且工作流内已配置 `on: workflow_dispatch:`，并检查 Actions 权限。
- 速率限制
  - 未带 Token 时匿名配额低（约 60/h）；带 Token 提高至 ~5000/h。

---

提示：我们在本地运行了全部测试，当前为 13 通过、0 失败（含若干第三方 Deprecation 警告，不影响功能）。GitHub 客户端在无令牌时不会发生任何真实网络请求，满足安全要求。

---

## 发布到 GitHub（一键脚本 + 手动方式）

本项目已内置自动化脚本，帮助你在 GitHub 上创建新仓库并把当前项目推送上去。

前置条件：
- 已安装 Git 并在 PATH 中可用（cmd 执行 `git --version` 可检查）
- 已安装 Python 并在 PATH 中可用（cmd 执行 `python --version` 可检查）
- 已准备 GitHub 个人访问令牌（PAT），并设置到环境变量 `GITHUB_TOKEN`
  - 临时设置：`set GITHUB_TOKEN=ghp_xxx_your_token`
  - 永久设置（新窗口生效）：`setx GITHUB_TOKEN "ghp_xxx_your_token"`

一键方式（推荐）：
1) 在项目根目录打开 cmd（或在 IDE 内打开系统终端）
2) 运行脚本：
   - 使用默认仓库名（当前文件夹名），私有可见性：
     scripts\publish_to_github.cmd
   - 或自定义参数：
     scripts\publish_to_github.cmd --name my-repo --public --description "My AI service"
     可选参数：
     - `--name <仓库名>`：默认使用当前目录名
     - `--org <组织名>`：在组织下创建
     - `--private`/`--public`：仓库可见性（默认私有）
     - `--description <文本>`：仓库描述
     - `--auto-init`：在 GitHub 端自动生成 README（注意：如果远程有初始提交，本地首次 push 需处理分支合并或强推）
     - `--remote-name <名称>`：默认 origin

脚本行为说明：
- 使用 `GITHUB_TOKEN` 调用 GitHub API 创建仓库；若已存在，则复用
- 本地执行 `git init`（如未初始化）并确保分支为 `main`，提交当前文件
- 把远程 `origin` 配置为不含 token 的 HTTPS URL，并用临时带 token 的 URL 完成首次 push（避免泄露 token 到 .git 配置）
- 成功后输出远程仓库地址

手动方式（可选）：
1) 在 GitHub Web 端创建空仓库（不要初始化 README/License），记下 HTTPS 地址，如：`https://github.com/<你>/<仓库>.git`
2) 在项目根目录执行：
   git init
   git checkout -B main
   git add -A
   git commit -m "Initial commit"
   git remote add origin https://github.com/<你>/<仓库>.git
   git push -u origin main

遇到问题？
- 报错缺少 Git：请安装 Git 并确保在 PATH 中
- 报错缺少 Python：请安装 Python 并确保在 PATH 中
- 报错未设置 GITHUB_TOKEN：请设置环境变量或改为手动方式
- 首次 push 提示需要先拉取：说明你在 GitHub 端勾选了 `Initialize with README`，请先 `git pull --rebase origin main` 再 push，或在脚本中去掉 `--auto-init` 并删除远程 README

---

如需把自动化流程整合到 CI/CD（例如 GitHub Actions）或添加版本发布工作流，我可以继续为你补充配置文件（.github/workflows/*）与脚本。
