import os
import sys

# 仅在 Windows 上可用：使用 SAPI 进行本地 TTS 合成
try:
    import comtypes.client as cc  # type: ignore
    # 先预加载 SAPI 类型库，避免直接导入 SpeechLib 失败
    sapi_typelib = os.path.join(os.environ.get("WINDIR", r"C:\\Windows"), r"System32\Speech\Common\sapi.dll")
    cc.GetModule(sapi_typelib)
    from comtypes.gen import SpeechLib  # type: ignore
except Exception as e:
    print("[ERROR] 需要依赖 comtypes，或系统未安装 SAPI：", e, file=sys.stderr)
    print("请执行: pip install comtypes", file=sys.stderr)
    raise

TEXT = os.environ.get("TEXT", "你好!世界！")
OUT = os.environ.get("OUT", os.path.join(os.getcwd(), "data", "nihao.wav"))
RATE = int(os.environ.get("RATE", "0"))       # -10..10，0为默认语速
VOLUME = int(os.environ.get("VOLUME", "100")) # 0..100
VOICE_HINT = os.environ.get("VOICE_HINT", "")  # 按名称子串选择语音，如 "Huihui"/"Xiaoyi"/"Hanhan"

os.makedirs(os.path.dirname(OUT), exist_ok=True)

# 创建 TTS 引擎和文件流
voice = cc.CreateObject("SAPI.SpVoice")
stream = cc.CreateObject("SAPI.SpFileStream")
fmt = cc.CreateObject("SAPI.SpAudioFormat")

# 16kHz 16-bit Mono，更利于 ASR
fmt.Type = SpeechLib.SAFT16kHz16BitMono
stream.Format = fmt

# 选择输出文件（创建/覆盖）
stream.Open(OUT, SpeechLib.SSFMCreateForWrite)
voice.AudioOutputStream = stream

# 选择语音（如有 VOICE_HINT 则按名称包含匹配）
if VOICE_HINT:
    tokens = voice.GetVoices()
    chosen = None
    for i in range(tokens.Count):
        t = tokens.Item(i)
        name = t.GetDescription()
        if VOICE_HINT.lower() in name.lower():
            chosen = t
            break
    if chosen is not None:
        voice.Voice = chosen

# 设置速率与音量
voice.Rate = RATE
voice.Volume = VOLUME

# 合成
voice.Speak(TEXT)

# 关闭流
stream.Close()
print(f"Generated WAV: {OUT}")
