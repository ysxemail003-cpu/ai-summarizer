import json
from fastapi.testclient import TestClient
from aipart.app import app
from aipart.services.stt import get_stt_engine

client = TestClient(app)


def test_health():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_summarize_frequency():
    payload = {"text": "This is a test. This test is simple. Summaries help users.", "max_sentences": 2, "strategy": "frequency"}
    r = client.post("/v1/summarize", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("sentences"), list)
    assert 1 <= len(data["sentences"]) <= 2
    assert isinstance(data.get("summary"), str)


def test_summarize_lead_and_boundary():
    payload = {"text": "A. B. C. D.", "max_sentences": 3, "strategy": "lead"}
    r = client.post("/v1/summarize", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["sentences"] == ["A.", "B.", "C."]


def test_summarize_empty_text_400():
    payload = {"text": "  ", "max_sentences": 2}
    r = client.post("/v1/summarize", json=payload)
    assert r.status_code == 400
    assert "不能为空" in r.json().get("detail", "")


def test_optimize_bullet():
    payload = {"text": "第一句。第二句！第三句？", "style": "bullet"}
    r = client.post("/v1/optimize", json=payload)
    assert r.status_code == 200
    result = r.json()["result"]
    lines = [ln for ln in result.splitlines() if ln.strip()]
    assert all(ln.strip().startswith("-") for ln in lines)
    assert len(lines) >= 3


def test_optimize_formal():
    payload = {"text": "I'm gonna go. It's ok.", "style": "formal"}
    r = client.post("/v1/optimize", json=payload)
    assert r.status_code == 200
    out = r.json()["result"].lower()
    assert "going to" in out and "okay" in out


def test_optimize_concise_en_removes_filler():
    payload = {"text": "It is actually really very good.", "style": "concise"}
    r = client.post("/v1/optimize", json=payload)
    assert r.status_code == 200
    out = r.json()["result"].lower()
    assert "actually" not in out and "really" not in out and "very" not in out


def test_stt_missing_file_422():
    # FastAPI 会对缺少必需的 file 字段返回 422
    r = client.post("/v1/stt", files={})
    assert r.status_code == 422


def test_stt_invalid_audio_returns_400_or_501():
    # 如果引擎可用，上传无效音频应返回 400；如果不可用则 501
    engine = get_stt_engine()
    r = client.post("/v1/stt", files={"file": ("fake.wav", b"not-a-real-wav", "audio/wav")})
    if engine.available:
        assert r.status_code in (200, 400)
        if r.status_code == 400:
            assert "失败" in r.json().get("detail", "")
    else:
        assert r.status_code == 501


def test_ai_json_text_flow():
    payload = {
        "text": "This is a test. This test is simple. Summaries help users.",
        "summarize": True,
        "optimize": True,
        "max_sentences": 2,
        "strategy": "frequency",
        "style": "bullet",
    }
    r = client.post("/v1/ai", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data.get("text")
    assert isinstance(data.get("summary"), str)
    assert isinstance(data.get("optimized"), str)


def test_ai_multipart_audio_flow():
    engine = get_stt_engine()
    r = client.post(
        "/v1/ai",
        files={"file": ("fake.wav", b"fake-bytes", "audio/wav")},
        data={"summarize": "1", "optimize": "0", "max_sentences": "2", "strategy": "lead"},
    )
    if engine.available:
        # 有引擎时，假音频可能 400（解析失败），也可能 200（若底层容错返回空文本）
        assert r.status_code in (200, 400)
        if r.status_code == 400:
            assert "失败" in r.json().get("detail", "")
    else:
        assert r.status_code == 501
