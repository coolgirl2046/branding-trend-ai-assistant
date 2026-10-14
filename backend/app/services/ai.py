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
from backend.app.services.trend_tools import (
    FUNCTION_TOOL_SCHEMA,
    TrendToolInputError,
)


logger = logging.getLogger(__name__)
MAX_DIAGNOSTIC_FIELD_LENGTH = 64
MAX_TOOL_CALLS = 3


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
        messages: list[dict[str, Any]],
        tool_executor: Any | None = None,
    ) -> str:
        request_messages = [
            {"role": "system", "content": system_prompt},
            *[dict(message) for message in messages],
        ]
        tool_calls_used = 0

        while True:
            request_options: dict[str, Any] = {
                "model": self._model,
                "messages": request_messages,
            }
            if tool_executor is not None and tool_calls_used < MAX_TOOL_CALLS:
                request_options["tools"] = [FUNCTION_TOOL_SCHEMA]
                request_options["tool_choice"] = "auto"
            tools_enabled = "tools" in request_options

            try:
                completion = self._client.chat.completions.create(**request_options)
                response_message = completion.choices[0].message
            except Exception as exc:
                _log_provider_error(exc)
                raise AIProviderError("AI 응답 생성에 실패했습니다.") from None

            calls = _get_field(response_message, "tool_calls") or []
            tool_names = [
                name
                for call in calls
                if isinstance(
                    (name := _get_field(_get_field(call, "function"), "name")), str
                )
            ]
            logger.info(
                "function_calling_response tool_call_count=%d tool_names=%s",
                len(calls),
                ",".join(tool_names) if tool_names else "none",
            )
            if not calls:
                content = _get_field(response_message, "content")
                if not isinstance(content, str) or not content.strip():
                    raise AIProviderError("AI 응답이 비어 있습니다.")
                return content.strip()

            if tool_executor is None:
                raise AIProviderError("AI 제공자가 지원하지 않는 도구 호출을 반환했습니다.")
            if not tools_enabled:
                raise AIProviderError("도구 호출 한도를 초과했습니다.")

            request_messages.append(_assistant_tool_message(response_message, calls))
            for call in calls:
                call_id = _get_field(call, "id")
                function = _get_field(call, "function")
                name = _get_field(function, "name")
                raw_arguments = _get_field(function, "arguments")
                tool_calls_used += 1

                if not isinstance(call_id, str) or not call_id:
                    raise AIProviderError("AI 도구 호출 형식이 올바르지 않습니다.")

                if tool_calls_used > MAX_TOOL_CALLS:
                    tool_result: object = {
                        "error": f"한 번의 답변에서 도구는 최대 {MAX_TOOL_CALLS}회까지 호출할 수 있습니다."
                    }
                else:
                    try:
                        parsed_arguments = json.loads(raw_arguments)
                        tool_result = tool_executor(name, parsed_arguments)
                    except (json.JSONDecodeError, TypeError):
                        tool_result = {"error": "도구 인자가 유효한 JSON 객체가 아닙니다."}
                    except TrendToolInputError as exc:
                        tool_result = {"error": str(exc)}
                    except Exception:
                        tool_result = {"error": "요청한 Firestore 데이터를 조회하지 못했습니다."}

                request_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(
                            tool_result, ensure_ascii=False, separators=(",", ":")
                        ),
                    }
                )

            # After the call budget is used, the next request has no tools and
            # must provide a final answer from the results already returned.


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
        "- 특정 키워드와 날짜 구간의 주간 원본 데이터가 필요하면 제공된 읽기 전용 도구를 사용한다.\n"
        "- 사용자가 이해하기 쉬운 한국어로 지나치게 장황하지 않게 답한다.\n"
        "아래 JSON은 현재 Firestore 데이터에서 계산한 요약이다.\n"
        f"{summary_json}"
    )


def _get_field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _assistant_tool_message(message: Any, calls: list[Any]) -> dict[str, Any]:
    normalized_calls = []
    for call in calls:
        function = _get_field(call, "function")
        normalized_calls.append(
            {
                "id": _get_field(call, "id"),
                "type": "function",
                "function": {
                    "name": _get_field(function, "name"),
                    "arguments": _get_field(function, "arguments"),
                },
            }
        )
    return {
        "role": "assistant",
        "content": _get_field(message, "content"),
        "tool_calls": normalized_calls,
    }
