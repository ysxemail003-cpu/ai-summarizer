import json
import os
import httpx

BASE = os.environ.get("BASE", "http://127.0.0.1:8080")
SAMPLE_WAV = os.environ.get("SAMPLE_WAV")


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
    with httpx.Client(timeout=60) as client:
        # health
        r = client.get(f"{BASE}/healthz")
        pretty("/healthz", r)

        # summarize
        payload = {
            "text": "This is a test. This test is simple. Summaries help users.",
            "max_sentences": 2,
            "strategy": "frequency",
        }
        r = client.post(f"{BASE}/v1/summarize", json=payload)
        pretty("/v1/summarize", r)

        # optimize
        payload2 = {"text": "第一句。第二句！第三句？", "style": "bullet"}
        r = client.post(f"{BASE}/v1/optimize", json=payload2)
        pretty("/v1/optimize", r)

        # stt: only if SAMPLE_WAV provided
        if SAMPLE_WAV and os.path.exists(SAMPLE_WAV):
            with open(SAMPLE_WAV, "rb") as f:
                files = {"file": (os.path.basename(SAMPLE_WAV), f, "audio/wav")}
                r = client.post(f"{BASE}/v1/stt", files=files)
                pretty("/v1/stt", r)
        else:
            print("\n=== /v1/stt (skipped) ===\n没有设置 SAMPLE_WAV，跳过 STT 测试。")


if __name__ == "__main__":
    main()
