from typing import Optional, Tuple
import os

# 解决 Windows 上 OpenMP 运行时重复加载导致的崩溃（libiomp5md.dll already initialized）
# 在导入/初始化 STT 引擎之前设置环境变量，避免 502/进程退出
if os.name == "nt":
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    os.environ.setdefault("OMP_NUM_THREADS", "1")

class STTEngine:
    def __init__(self) -> None:
        self._engine = None
        self._name: Optional[str] = None
        self._model = None  # cache actual model instance for faster-whisper
        self._fw_opts = None  # decode options for faster-whisper
        # Try faster-whisper first, then openai-whisper
        try:
            from faster_whisper import WhisperModel  # type: ignore
            self._name = "faster-whisper"
            self._engine = "lazy"  # real model will be loaded on first use
        except Exception:
            try:
                import whisper  # type: ignore
                self._name = "openai-whisper"
                self._engine = whisper
            except Exception:
                self._engine = None
                self._name = None

    @property
    def available(self) -> bool:
        return self._engine is not None

    @property
    def name(self) -> Optional[str]:
        return self._name

    def _read_bool(self, env: str, default: bool) -> bool:
        v = os.environ.get(env)
        if v is None:
            return default
        return str(v).strip().lower() in ("1", "true", "yes", "on")

    def _ensure_fw_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # type: ignore
            # 默认提升到 base，兼顾准确率
            model_size = (os.environ.get("FAST_WHISPER_MODEL", "base") or "base").strip()
            compute_type = (os.environ.get("FAST_WHISPER_COMPUTE", "int8") or "int8").strip()
            device = (os.environ.get("FAST_WHISPER_DEVICE", "cpu") or "cpu").strip()
            self._model = WhisperModel(model_size, device=device, compute_type=compute_type)
            # 推理选项（解码阶段）
            self._fw_opts = {
                "beam_size": int(os.environ.get("FAST_WHISPER_BEAM_SIZE", "5") or 5),
                "best_of": int(os.environ.get("FAST_WHISPER_BEST_OF", "5") or 5),
                "vad_filter": self._read_bool("FAST_WHISPER_VAD_FILTER", True),
                "temperature": float(os.environ.get("FAST_WHISPER_TEMPERATURE", "0.0") or 0.0),
                "no_speech_threshold": float(os.environ.get("FAST_WHISPER_NO_SPEECH_THRESHOLD", "0.6") or 0.6),
                "compression_ratio_threshold": float(os.environ.get("FAST_WHISPER_COMPRESSION_RATIO_THRESHOLD", "2.4") or 2.4),
                "condition_on_previous_text": self._read_bool("FAST_WHISPER_CONDITION_ON_PREV", True),
                "fixed_language": (os.environ.get("FAST_WHISPER_LANGUAGE") or None),
                "task": (os.environ.get("FAST_WHISPER_TASK", "transcribe") or "transcribe").strip(),
                # 初始提示（偏置提示）
                "initial_prompt": (os.environ.get("FAST_WHISPER_INITIAL_PROMPT") or None),
            }
            # 打印一次关键配置便于诊断（避免噪音，不频繁打印）
            try:
                print(
                    f"[STT] faster-whisper model={model_size}, device={device}, compute={compute_type}, "
                    f"opts={{beam={self._fw_opts['beam_size']}, best_of={self._fw_opts['best_of']}, vad={self._fw_opts['vad_filter']}, "
                    f"temp={self._fw_opts['temperature']}, lang={self._fw_opts['fixed_language']}, task={self._fw_opts['task']}, prompt={'yes' if self._fw_opts['initial_prompt'] else 'no'}}}"
                )
            except Exception:
                pass
        return self._model

    def transcribe(self, file_path: str, language: Optional[str] = None, initial_prompt: Optional[str] = None) -> Tuple[str, Optional[str]]:
        if not self.available:
            raise RuntimeError("No STT engine available. Please install faster-whisper or openai-whisper.")
        # faster-whisper path
        if self._name == "faster-whisper":
            model = self._ensure_fw_model()
            opts = self._fw_opts or {}
            lang = language or opts.get("fixed_language")
            prompt = initial_prompt or opts.get("initial_prompt")
            segments, info = model.transcribe(
                file_path,
                language=lang,
                task=opts.get("task", "transcribe"),
                beam_size=opts.get("beam_size", 5),
                best_of=opts.get("best_of", 5),
                vad_filter=opts.get("vad_filter", True),
                temperature=opts.get("temperature", 0.0),
                no_speech_threshold=opts.get("no_speech_threshold", 0.6),
                compression_ratio_threshold=opts.get("compression_ratio_threshold", 2.4),
                condition_on_previous_text=opts.get("condition_on_previous_text", True),
                initial_prompt=prompt,
            )
            text = "".join(seg.text for seg in segments)
            detected = getattr(info, "language", None)
            return text.strip(), (lang or detected)
        # openai-whisper path
        else:
            import whisper  # type: ignore
            model_size = (os.environ.get("OPENAI_WHISPER_MODEL", "base") or "base").strip()
            model = whisper.load_model(model_size)
            # openai-whisper 使用 prompt 参数名
            result = model.transcribe(file_path, language=language, prompt=initial_prompt)
            return (result.get("text", "").strip(), result.get("language"))

    def warm_up(self) -> bool:
        """预热模型：
        - faster-whisper：加载模型到内存；
        - openai-whisper：保持惰性（避免启动即下载/加载大型模型），返回可用状态。
        返回是否就绪。
        """
        if not self.available:
            return False
        try:
            if self._name == "faster-whisper":
                self._ensure_fw_model()
                return True
            # openai-whisper：不做强加载，交由首次调用时加载
            return True
        except Exception:
            return False


_engine_singleton: Optional[STTEngine] = None

def get_stt_engine() -> STTEngine:
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = STTEngine()
    return _engine_singleton
