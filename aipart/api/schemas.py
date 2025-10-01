from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class SummarizeRequest(BaseModel):
    text: str = Field(..., description="需要被总结的文本")
    max_sentences: int = Field(3, ge=1, le=20, description="摘要句子数上限")
    strategy: Literal["lead", "frequency"] = Field("frequency", description="摘要策略：首句优先或频率打分")


class SummarizeResponse(BaseModel):
    summary: str
    sentences: List[str]


class OptimizeRequest(BaseModel):
    text: str
    style: Literal["concise", "formal", "bullet"] = Field(
        "concise", description="优化风格：简洁/正式/要点"
    )
    language: Optional[str] = Field(None, description="期望语言，不填会自动沿用原文语言")


class OptimizeResponse(BaseModel):
    result: str


class STTResponse(BaseModel):
    text: str
    language: Optional[str] = None
    engine: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str


# 简化对接的一体化接口：/v1/ai
class AiTextRequest(BaseModel):
    text: str
    summarize: bool = True
    optimize: bool = False
    max_sentences: int = Field(3, ge=1, le=20)
    strategy: Literal["lead", "frequency"] = "frequency"
    style: Literal["concise", "formal", "bullet"] = "concise"
    language: Optional[str] = None


class AiResponse(BaseModel):
    text: str
    summary: Optional[str] = None
    optimized: Optional[str] = None
    language: Optional[str] = None
    engine: Optional[str] = None
