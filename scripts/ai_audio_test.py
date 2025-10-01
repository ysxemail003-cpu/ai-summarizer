import os
import json
import httpx

BASE = os.environ.get("BASE", "http://127.0.0.1:8080")
WAV = os.environ.get("WAV", os.path.join(os.getcwd(), "data", "nihao.wav"))
LANGUAGE = os.environ.get("LANGUAGE")  # 可选，强制识别语言，如 zh/en
INITIAL_PROMPT = os.environ.get("INITIAL_PROMPT")  # 可选，初始提示以偏置识别

def pretty(title: str, resp: httpx.Response):
    print(f"\n=== {title} ===")
    print(f"Status: {resp.status_code}")
    ctype = resp.headers.get("content-type", "")
    if "application/json" in ctype:
        try:
            print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
        except Exception:
            print(resp.text)
    else:
        print(resp.text)


def main():
    if not os.path.exists(WAV):
        raise SystemExit(f"WAV 文件不存在: {WAV}")
    with httpx.Client(timeout=120) as client:
        with open(WAV, "rb") as f:
            files = {"file": (os.path.basename(WAV), f, "audio/wav")}
            data = {
                "summarize": "1",
                "optimize": "1",
                "max_sentences": "3",
                "strategy": "frequency",
                "style": "concise",
            }
            if LANGUAGE:
                data["language"] = LANGUAGE
            if INITIAL_PROMPT:
                data["initial_prompt"] = INITIAL_PROMPT
            r = client.post(f"{BASE}/v1/ai", files=files, data=data)
            pretty("/v1/ai (audio)", r)

if __name__ == "__main__":
    main()
