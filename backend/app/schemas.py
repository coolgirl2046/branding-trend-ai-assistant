"""Pydantic request and response models for the Mission 2 API."""

from __future__ import annotations

import math
from datetime import date as date_type
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Keyword(str, Enum):
    PERSONAL_BRANDING = "퍼스널브랜딩"
    IMAGE_MAKING = "이미지메이킹"
    SPEECH = "스피치"


class TrendDataFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    keyword: Keyword
    value: float
    memo: str | None = Field(default=None, max_length=1000)

    @field_validator("date", mode="before")
    @classmethod
    def validate_iso_date(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("date는 YYYY-MM-DD 문자열이어야 합니다.")
        try:
            parsed = date_type.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date는 유효한 YYYY-MM-DD 날짜여야 합니다.") from exc
        if parsed.isoformat() != value:
            raise ValueError("date는 YYYY-MM-DD 형식이어야 합니다.")
        return value

    @field_validator("value", mode="before")
    @classmethod
    def validate_finite_value(cls, value: object) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("value는 숫자여야 합니다.")
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            raise ValueError("value는 유한한 숫자여야 합니다.")
        if not 0 <= numeric_value <= 100:
            raise ValueError("value는 상대 관심도 범위인 0~100이어야 합니다.")
        return numeric_value


class TrendDataCreate(TrendDataFields):
    pass


class TrendDataUpdate(TrendDataFields):
    pass


class TrendDataResponse(TrendDataFields):
    id: str


class DeleteDataResponse(BaseModel):
    deleted: bool
    id: str


class KeywordSummary(BaseModel):
    count: int
    average: float | None
    minimum: float | None
    maximum: float | None
    latest_date: str | None
    latest_value: float | None
    recent_4week_average: float | None
    previous_4week_average: float | None
    difference: float | None
    trend: Literal["상승", "하락", "유지", "데이터 부족"]


class RankingItem(BaseModel):
    rank: int
    keyword: Keyword
    recent_4week_average: float


class TrendRule(BaseModel):
    stability_threshold: float
    stable_when: str


class DataSummaryResponse(BaseModel):
    start_date: str | None
    end_date: str | None
    total_count: int
    metric_note: str
    trend_rule: TrendRule
    keywords: dict[Keyword, KeywordSummary]
    ranking: list[RankingItem]


class ConversationMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(max_length=10000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("content는 빈 문자열일 수 없습니다.")
        return stripped


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(max_length=200)
    messages: list[ConversationMessageCreate] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title은 빈 문자열일 수 없습니다.")
        return stripped


class ConversationMessageResponse(ConversationMessageCreate):
    created_at: str


class ConversationListItem(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: str
    updated_at: str


class ConversationDetail(BaseModel):
    id: str
    title: str
    messages: list[ConversationMessageResponse]
    created_at: str
    updated_at: str


class DeleteConversationResponse(BaseModel):
    deleted: bool
    id: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(max_length=10000)
    conversation_id: str | None = Field(default=None, max_length=200)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message는 빈 문자열일 수 없습니다.")
        return stripped

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("conversation_id는 빈 문자열일 수 없습니다.")
        return stripped


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    created_new_conversation: bool
