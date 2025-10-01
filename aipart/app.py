from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from .api.schemas import (
    SummarizeRequest, SummarizeResponse,
    OptimizeRequest, OptimizeResponse,
    STTResponse, ErrorResponse,
    AiTextRequest, AiResponse
)
from .services.summarizer import summarize as summarize_svc
from .services.optimizer import optimize as optimize_svc
from .services.stt import get_stt_engine
from .services.text_utils import detect_language, apply_corrections
import tempfile
import os


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body_size: int) -> None:
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        try:
            if cl is not None and int(cl) > self.max_body_size:
                mb = max(1, self.max_body_size // (1024 * 1024))
                return JSONResponse(status_code=413, content={"detail": f"请求体过大，限制为 {mb}MB"})
        except Exception:
            pass
        return await call_next(request)


app = FastAPI(title="AI Summarizer Service", version="0.1.0")

# Body size limit (default 25MB)
try:
    _max_mb = int((os.environ.get("MAX_UPLOAD_MB") or "25").strip())
except Exception:
    _max_mb = 25
app.add_middleware(BodySizeLimitMiddleware, max_body_size=_max_mb * 1024 * 1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    # 预热 STT，减少首个请求冷启动
    try:
        engine = get_stt_engine()
        ready = engine.warm_up()
        # 标记就绪状态
        app.state.stt_ready = bool(ready)
    except Exception:
        app.state.stt_ready = False


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/ready")
def readyz():
    engine = get_stt_engine()
    return {"ready": bool(getattr(app.state, "stt_ready", False)), "engine": engine.name, "available": engine.available}


@app.post("/v1/summarize", response_model=SummarizeResponse, responses={400: {"model": ErrorResponse}})
def summarize(req: SummarizeRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="text 不能为空")
    sentences = summarize_svc(req.text, req.max_sentences, req.strategy)
    return SummarizeResponse(summary=" ".join(sentences), sentences=sentences)


@app.post("/v1/optimize", response_model=OptimizeResponse, responses={400: {"model": ErrorResponse}})
def optimize(req: OptimizeRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="text 不能为空")
    result = optimize_svc(req.text, req.style, req.language)
    return OptimizeResponse(result=result)


@app.post("/v1/stt", response_model=STTResponse, responses={400: {"model": ErrorResponse}, 501: {"model": ErrorResponse}})
async def stt(file: UploadFile = File(...), language: str | None = None, initial_prompt: str | None = None):
    if not file:
        raise HTTPException(status_code=400, detail="请上传音频文件")
    engine = get_stt_engine()
    if not engine.available:
        raise HTTPException(status_code=501, detail="STT 引擎不可用，请安装 faster-whisper 或 openai-whisper")
    # Save to temp file and transcribe
    suffix = os.path.splitext(file.filename or "audio")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    try:
        try:
            text, lang = engine.transcribe(tmp_path, language=language, initial_prompt=initial_prompt)
            # 术语纠错（可选，受环境变量控制）
            text = apply_corrections(text, lang or "en")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"音频解析/转写失败: {e}")
        return STTResponse(text=text, language=lang, engine=engine.name)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@app.post("/v1/ai", response_model=AiResponse, responses={400: {"model": ErrorResponse}, 501: {"model": ErrorResponse}})
async def ai_unified(request: Request):
    content_type = request.headers.get("content-type", "").lower()

    def do_pipeline(text: str, summarize: bool, optimize: bool, max_sentences: int, strategy: str, style: str, language: str | None, lang_detected: str | None = None):
        summary = None
        optimized = None
        lang = language or lang_detected
        if summarize:
            sentences = summarize_svc(text, max_sentences, strategy)
            summary = " ".join(sentences)
        if optimize:
            base = summary or text
            optimized = optimize_svc(base, style, language)
        return summary, optimized, lang

    # JSON: 文本流程
    if "application/json" in content_type:
        data = await request.json()
        try:
            req = AiTextRequest(**data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"请求格式错误: {e}")
        if not req.text or not req.text.strip():
            raise HTTPException(status_code=400, detail="text 不能为空")
        lang = detect_language(req.text)
        summary, optimized, lang_out = do_pipeline(
            req.text, req.summarize, req.optimize, req.max_sentences, req.strategy, req.style, req.language, lang
        )
        return AiResponse(text=req.text, summary=summary, optimized=optimized, language=lang_out)

    # multipart: 音频流程
    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        if not file:
            raise HTTPException(status_code=400, detail="请上传音频文件")
        def get_bool(name: str, default: bool) -> bool:
            v = form.get(name, None)
            if v is None:
                return default
            return str(v).strip().lower() in ("1", "true", "yes", "on")
        def get_int(name: str, default: int) -> int:
            v = form.get(name, None)
            try:
                return int(v)
            except Exception:
                return default
        summarize_flag = get_bool("summarize", True)
        optimize_flag = get_bool("optimize", False)
        max_sentences = get_int("max_sentences", 3)
        strategy = (form.get("strategy") or "frequency").strip()
        style = (form.get("style") or "concise").strip()
        language = (form.get("language") or None)
        initial_prompt = (form.get("initial_prompt") or None)

        engine = get_stt_engine()
        if not engine.available:
            raise HTTPException(status_code=501, detail="STT 引擎不可用，请安装 faster-whisper 或 openai-whisper")
        # 保存临时文件并转写
        filename = getattr(file, "filename", "audio.wav")
        suffix = os.path.splitext(filename)[1] or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        try:
            try:
                text, lang = engine.transcribe(tmp_path, language=language, initial_prompt=initial_prompt)
                text = apply_corrections(text, lang or "en")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"音频解析/转写失败: {e}")
            summary, optimized, lang_out = do_pipeline(
                text, summarize_flag, optimize_flag, max_sentences, strategy, style, language, lang
            )
            return AiResponse(text=text, summary=summary, optimized=optimized, language=lang_out, engine=engine.name)
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    # 不支持的 content type
    raise HTTPException(status_code=400, detail="不支持的 Content-Type，请用 application/json 或 multipart/form-data")
