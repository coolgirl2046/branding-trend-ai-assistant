"""OpenAI-compatible chat provider isolated for dependency mocking."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
)

from backend.app.config import AISettings, load_ai_settings


logger = logging.getLogger(__name__)
MAX_DIAGNOSTIC_FIELD_LENGTH = 64


class AIProviderError(RuntimeError):
    """Raised with a safe message when the external AI provider fails."""


def _safe_diagnostic_field(value: object) -> str | None:
    """Return only a short, printable string suitable for diagnostic logs."""
    if not isinstance(value, str):
        return None

    normalized = value.strip()
    if not normalized or len(normalized) > MAX_DIAGNOSTIC_FIELD_LENGTH:
        return None
    if not normalized.isprintable():
        return None
    return normalized


def _log_provider_error(exc: Exception) -> None:
    """Log only non-sensitive provider diagnostics."""
    if isinstance(exc, AuthenticationError):
        label = "authentication_error"
    elif isinstance(exc, BadRequestError):
        label = "bad_request"
    elif isinstance(exc, APIConnectionError):
        label = "connection_error"
    elif isinstance(exc, APIStatusError):
        label = "response_error"
    else:
        label = "unknown_error"

    body_type = None
    body_code = None
    body_param = None
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        body_type = _safe_diagnostic_field(body.get("type"))
        body_code = _safe_diagnostic_field(body.get("code"))
        body_param = _safe_diagnostic_field(body.get("param"))

    status_code = getattr(exc, "status_code", None)
    code = _safe_diagnostic_field(getattr(exc, "code", None)) or body_code
    param = _safe_diagnostic_field(getattr(exc, "param", None)) or body_param
    logger.error(
        (
            "AI provider failure label=%s exception_class=%s "
            "status_code=%s type=%s code=%s param=%s"
        ),
        label,
        type(exc).__name__,
        status_code if isinstance(status_code, int) else "none",
        body_type,
        code,
        param,
    )


class OpenAIChatService:
    def __init__(self, settings: AISettings, client: Any | None = None):
        self._model = settings.model
        self._client = client or OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            max_retries=0,
        )

    def generate_answer(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> str:
        request_messages = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=request_messages,
            )
            content = completion.choices[0].message.content
        except Exception as exc:
            _log_provider_error(exc)
            raise AIProviderError("AI 응답 생성에 실패했습니다.") from None

        if not isinstance(content, str) or not content.strip():
            raise AIProviderError("AI 응답이 비어 있습니다.")
        return content.strip()


def create_ai_chat_service() -> OpenAIChatService:
    """Create one OpenAI-compatible client for the selected provider."""
    return OpenAIChatService(load_ai_settings())


def build_system_prompt(summary: dict[str, Any]) -> str:
    summary_json = json.dumps(summary, ensure_ascii=False, separators=(",", ":"))
    return (
        "당신은 브랜딩 트렌드 데이터에 근거해 답하는 AI 비서입니다.\n"
        "- 이 데이터는 네이버 데이터랩의 상대 검색 관심도 지수이며 절대 검색량이 아니다.\n"
        "- 제공된 숫자를 임의로 만들거나 변경하지 않는다.\n"
        "- 데이터에서 직접 확인되는 내용은 관찰/사실로 구분한다.\n"
        "- 전략적 해석이나 추천은 해석/제안으로 구분한다.\n"
        "- 데이터만으로 원인을 알 수 없으면 원인을 단정하지 않는다.\n"
        "- 질문과 관련된 데이터 기간과 최근 기준일을 필요할 때 명확히 언급한다.\n"
        "- 사용자가 이해하기 쉬운 한국어로 지나치게 장황하지 않게 답한다.\n"
        "아래 JSON은 현재 Firestore 데이터에서 계산한 요약이다.\n"
        f"{summary_json}"
    )
