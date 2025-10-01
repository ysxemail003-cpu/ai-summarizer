import math
import wave
import struct
import os

OUT = os.environ.get("OUT", os.path.join(os.getcwd(), "data", "sample_440.wav"))
DURATION = float(os.environ.get("DURATION", "1.0"))  # seconds
SR = int(os.environ.get("SR", "16000"))
FREQ = float(os.environ.get("FREQ", "440.0"))
AMP = 0.5  # amplitude 0..1

dirname = os.path.dirname(OUT)
if dirname:
    os.makedirs(dirname, exist_ok=True)

nframes = int(DURATION * SR)
with wave.open(OUT, "wb") as wf:
    wf.setnchannels(1)  # mono
    wf.setsampwidth(2)  # 16-bit
    wf.setframerate(SR)
    for i in range(nframes):
        t = i / SR
        sample = AMP * math.sin(2 * math.pi * FREQ * t)
        value = int(max(-1.0, min(1.0, sample)) * 32767)
        wf.writeframesraw(struct.pack('<h', value))
    # finalize header
    wf.writeframes(b"")

print(f"Generated WAV: {OUT}")
