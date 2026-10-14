"""Chat API tests with fake Firestore and a mocked AI provider."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
from types import SimpleNamespace
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from firebase_admin import firestore
from httpx import Request, Response
from openai import AuthenticationError, BadRequestError

from backend.app.config import AISettings
from backend.app.main import app
from backend.app.routers.chat import get_ai_chat_service, get_chat_client
from backend.app.services.ai import (
    AIProviderError,
    MAX_TOOL_CALLS,
    OpenAIChatService,
    create_ai_chat_service,
)
from backend.app.services.trend_tools import (
    FUNCTION_TOOL_SCHEMA,
    TOOL_NAME,
    execute_trend_tool,
)


class FakeSnapshot:
    def __init__(self, document_id: str, stored: dict[str, Any] | None):
        self.id = document_id
        self.exists = stored is not None
        self._stored = stored

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self._stored or {})


class FakeDocument:
    def __init__(
        self,
        client: "FakeFirestoreClient",
        collection_name: str,
        document_id: str,
    ):
        self._client = client
        self._collection_name = collection_name
        self.id = document_id

    @property
    def _documents(self) -> dict[str, dict[str, Any]]:
        return self._client.collections[self._collection_name]

    def get(self) -> FakeSnapshot:
        return FakeSnapshot(self.id, self._documents.get(self.id))

    def set(self, fields: dict[str, Any]) -> None:
        self._documents[self.id] = self._client.resolve_timestamps(fields)
        self._client.write_count += 1

    def update(self, fields: dict[str, Any]) -> None:
        self._documents[self.id].update(self._client.resolve_timestamps(fields))
        self._client.write_count += 1


class FakeCollection:
    def __init__(self, client: "FakeFirestoreClient", name: str):
        self._client = client
        self._name = name

    def document(self, document_id: str | None = None) -> FakeDocument:
        if document_id is None:
            document_id = self._client.next_conversation_id()
        return FakeDocument(self._client, self._name, document_id)

    def stream(self) -> list[FakeSnapshot]:
        return [
            FakeSnapshot(document_id, stored)
            for document_id, stored in self._client.collections[self._name].items()
        ]


class FakeFirestoreClient:
    def __init__(self):
        self.collections: dict[str, dict[str, dict[str, Any]]] = {
            "data": {},
            "conversations": {},
        }
        self.write_count = 0
        self._conversation_sequence = 0
        self._timestamp_sequence = 0
        self._seed_summary_data()

    def collection(self, name: str) -> FakeCollection:
        if name not in self.collections:
            raise AssertionError(f"Unexpected collection: {name}")
        return FakeCollection(self, name)

    def next_conversation_id(self) -> str:
        self._conversation_sequence += 1
        return f"chat-{self._conversation_sequence:03d}"

    def resolve_timestamps(self, value: Any) -> Any:
        if value is firestore.SERVER_TIMESTAMP:
            timestamp = datetime(2026, 9, 10, tzinfo=timezone.utc) + timedelta(
                seconds=self._timestamp_sequence
            )
            self._timestamp_sequence += 1
            return timestamp
        if isinstance(value, dict):
            return {
                key: self.resolve_timestamps(item) for key, item in value.items()
            }
        if isinstance(value, list):
            return [self.resolve_timestamps(item) for item in value]
        return deepcopy(value)

    def _seed_summary_data(self) -> None:
        start = date(2026, 6, 1)
        bases = {"퍼스널브랜딩": 10, "이미지메이킹": 5, "스피치": 50}
        for keyword, base in bases.items():
            for offset in range(8):
                observed_date = (start + timedelta(weeks=offset)).isoformat()
                document_id = f"{observed_date}_{keyword}_{offset}"
                self.collections["data"][document_id] = {
                    "date": observed_date,
                    "keyword": keyword,
                    "value": float(base + offset),
                }


class FakeAIService:
    def __init__(self, answer: str = "스피치를 우선 검토하세요."):
        self.answer = answer
        self.calls: list[dict[str, Any]] = []

    def generate_answer(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        tool_executor: Any | None = None,
    ) -> str:
        del tool_executor
        self.calls.append(
            {"system_prompt": system_prompt, "messages": deepcopy(messages)}
        )
        return self.answer


class FailingAIService(FakeAIService):
    def generate_answer(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        tool_executor: Any | None = None,
    ) -> str:
        del system_prompt, messages, tool_executor
        raise RuntimeError("api_key=DO_NOT_EXPOSE provider internal failure")


class ChatApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.firestore = FakeFirestoreClient()
        self.ai_service = FakeAIService()
        app.dependency_overrides[get_chat_client] = lambda: self.firestore
        app.dependency_overrides[get_ai_chat_service] = lambda: self.ai_service
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()

    def _store_existing_conversation(self) -> str:
        conversation_id = "existing-chat"
        observed_at = datetime(2026, 9, 9, tzinfo=timezone.utc)
        self.firestore.collections["conversations"][conversation_id] = {
            "title": "기존 대화",
            "messages": [
                {"role": "user", "content": "이전 질문", "created_at": observed_at},
                {
                    "role": "assistant",
                    "content": "이전 답변",
                    "created_at": observed_at,
                },
            ],
            "created_at": observed_at,
            "updated_at": observed_at,
        }
        return conversation_id

    def test_new_conversation_chat_saves_user_and_assistant_messages(self) -> None:
        response = self.client.post(
            "/api/chat",
            json={"message": "어떤 주제를 우선할까?", "conversation_id": None},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["created_new_conversation"])
        self.assertEqual(body["answer"], self.ai_service.answer)
        stored = self.firestore.collections["conversations"][
            body["conversation_id"]
        ]
        self.assertEqual([item["role"] for item in stored["messages"]], ["user", "assistant"])
        self.assertEqual(stored["messages"][0]["content"], "어떤 주제를 우선할까?")
        self.assertEqual(stored["messages"][1]["content"], self.ai_service.answer)

    def test_existing_conversation_chat_preserves_and_appends_messages(self) -> None:
        conversation_id = self._store_existing_conversation()
        response = self.client.post(
            "/api/chat",
            json={"message": "이어서 비교해줘", "conversation_id": conversation_id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["created_new_conversation"])
        stored = self.firestore.collections["conversations"][conversation_id]
        self.assertEqual(len(stored["messages"]), 4)
        self.assertEqual(stored["messages"][0]["content"], "이전 질문")
        self.assertEqual(stored["messages"][-2]["content"], "이어서 비교해줘")
        self.assertEqual(
            [message["content"] for message in self.ai_service.calls[0]["messages"]],
            ["이전 질문", "이전 답변", "이어서 비교해줘"],
        )

    def test_missing_conversation_returns_404_without_provider_call(self) -> None:
        response = self.client.post(
            "/api/chat",
            json={"message": "질문", "conversation_id": "missing"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.ai_service.calls, [])
        self.assertEqual(self.firestore.write_count, 0)

    def test_blank_message_returns_422(self) -> None:
        response = self.client.post(
            "/api/chat", json={"message": "   ", "conversation_id": None}
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.ai_service.calls, [])
        self.assertEqual(self.firestore.write_count, 0)

    def test_provider_failure_returns_safe_error_and_saves_nothing(self) -> None:
        app.dependency_overrides[get_ai_chat_service] = lambda: FailingAIService()
        response = self.client.post(
            "/api/chat", json={"message": "실패 테스트", "conversation_id": None}
        )

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("api_key", response.text.lower())
        self.assertNotIn("do_not_expose", response.text.lower())
        self.assertEqual(self.firestore.collections["conversations"], {})
        self.assertEqual(self.firestore.write_count, 0)

    def test_provider_receives_calculated_summary_in_system_context(self) -> None:
        response = self.client.post(
            "/api/chat", json={"message": "요약해줘", "conversation_id": None}
        )

        self.assertEqual(response.status_code, 200)
        prompt = self.ai_service.calls[0]["system_prompt"]
        self.assertIn('"total_count":24', prompt)
        self.assertIn('"start_date":"2026-06-01"', prompt)
        self.assertIn('"end_date":"2026-07-20"', prompt)
        self.assertIn('"recent_4week_average"', prompt)
        self.assertIn('"ranking"', prompt)
        self.assertIn("퍼스널브랜딩", prompt)
        self.assertIn("이미지메이킹", prompt)
        self.assertIn("스피치", prompt)

    def test_system_context_states_relative_not_absolute_search_interest(self) -> None:
        response = self.client.post(
            "/api/chat", json={"message": "설명해줘", "conversation_id": None}
        )

        self.assertEqual(response.status_code, 200)
        prompt = self.ai_service.calls[0]["system_prompt"]
        self.assertIn("상대 검색 관심도 지수", prompt)
        self.assertIn("절대 검색량이 아니다", prompt)
        self.assertIn("관찰/사실", prompt)
        self.assertIn("해석/제안", prompt)

    def test_chat_tool_executor_is_read_only_and_final_answer_is_persisted(self) -> None:
        class ToolUsingAIService(FakeAIService):
            def generate_answer(
                service_self,
                *,
                system_prompt: str,
                messages: list[dict[str, str]],
                tool_executor: Any | None = None,
            ) -> str:
                del system_prompt, messages
                result = tool_executor(
                    TOOL_NAME,
                    {
                        "keyword": "스피치",
                        "start_date": "2026-06-01",
                        "end_date": "2026-06-08",
                    },
                )
                service_self.result = result
                return "주간 지수는 50과 51입니다."

        initial_data = deepcopy(self.firestore.collections["data"])
        tool_service = ToolUsingAIService()
        app.dependency_overrides[get_ai_chat_service] = lambda: tool_service
        response = self.client.post(
            "/api/chat", json={"message": "기간 데이터를 확인해줘"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [record["value"] for record in tool_service.result["records"]],
            [50.0, 51.0],
        )
        self.assertEqual(self.firestore.collections["data"], initial_data)
        conversation = self.firestore.collections["conversations"][
            response.json()["conversation_id"]
        ]
        self.assertEqual(conversation["messages"][-1]["content"], "주간 지수는 50과 51입니다.")

    def test_openai_service_uses_model_and_system_message_without_network(self) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="  테스트 답변  "))
            ]
        )
        service = OpenAIChatService(
            AISettings(
                api_key="test-key",
                base_url="https://example.invalid/v1",
                model="test-model",
            ),
            client=mock_client,
        )

        answer = service.generate_answer(
            system_prompt="시스템 규칙",
            messages=[{"role": "user", "content": "질문"}],
        )

        self.assertEqual(answer, "테스트 답변")
        call = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(call["model"], "test-model")
        self.assertEqual(call["messages"][0], {"role": "system", "content": "시스템 규칙"})
        self.assertEqual(call["messages"][1], {"role": "user", "content": "질문"})

    def test_openai_client_is_created_with_retries_disabled(self) -> None:
        settings = AISettings(
            api_key="test-key",
            base_url="https://example.invalid/v1",
            model="test-model",
        )

        with patch("backend.app.services.ai.OpenAI") as mock_openai:
            OpenAIChatService(settings)

        mock_openai.assert_called_once_with(
            api_key="test-key",
            base_url="https://example.invalid/v1",
            max_retries=0,
        )

    def test_factory_creates_one_client_for_selected_provider(self) -> None:
        for provider in ("openai", "gemini"):
            with self.subTest(provider=provider):
                settings = AISettings(
                    provider=provider,
                    api_key=f"{provider}-test-key",
                    base_url=f"https://{provider}.example/v1",
                    model=f"{provider}-test-model",
                )

                with (
                    patch(
                        "backend.app.services.ai.load_ai_settings",
                        return_value=settings,
                    ) as load_settings,
                    patch("backend.app.services.ai.OpenAI") as mock_openai,
                ):
                    service = create_ai_chat_service()

                self.assertIsInstance(service, OpenAIChatService)
                load_settings.assert_called_once_with()
                mock_openai.assert_called_once_with(
                    api_key=f"{provider}-test-key",
                    base_url=f"https://{provider}.example/v1",
                    max_retries=0,
                )

    def test_authentication_error_logs_only_safe_diagnostics(self) -> None:
        secret = "DO_NOT_LOG_API_KEY"
        request = Request("POST", "https://example.invalid/v1/chat/completions")
        response = Response(401, request=request, text="provider secret response")
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = AuthenticationError(
            "authentication failed " + secret,
            response=response,
            body={"secret": secret},
        )
        service = OpenAIChatService(
            AISettings(
                api_key=secret,
                base_url="https://example.invalid/v1",
                model="test-model",
            ),
            client=mock_client,
        )

        with self.assertLogs("backend.app.services.ai", level="ERROR") as captured:
            with self.assertRaisesRegex(RuntimeError, "AI"):
                service.generate_answer(
                    system_prompt="system",
                    messages=[{"role": "user", "content": "private question"}],
                )

        log_text = "\n".join(captured.output)
        self.assertIn("label=authentication_error", log_text)
        self.assertIn("exception_class=AuthenticationError", log_text)
        self.assertIn("status_code=401", log_text)
        self.assertNotIn(secret, log_text)
        self.assertNotIn("provider secret response", log_text)
        self.assertNotIn("private question", log_text)

    def test_bad_request_logs_only_safe_diagnostics(self) -> None:
        secret = "DO_NOT_LOG_PROVIDER_BODY"
        request = Request("POST", "https://example.invalid/v1/chat/completions")
        response = Response(400, request=request, text=secret)
        mock_client = MagicMock()
        provider_error = BadRequestError(
            "bad request " + secret,
            response=response,
            body={
                "type": "invalid_request_error",
                "code": "invalid_request",
                "param": "messages[0].role",
                "message": secret,
            },
        )
        provider_error.code = None
        provider_error.param = None
        mock_client.chat.completions.create.side_effect = provider_error
        service = OpenAIChatService(
            AISettings(
                api_key="test-key",
                base_url="https://example.invalid/v1",
                model="test-model",
            ),
            client=mock_client,
        )

        with self.assertLogs("backend.app.services.ai", level="ERROR") as captured:
            with self.assertRaisesRegex(RuntimeError, "AI"):
                service.generate_answer(
                    system_prompt="system",
                    messages=[{"role": "user", "content": "question"}],
                )

        log_text = "\n".join(captured.output)
        self.assertIn("label=bad_request", log_text)
        self.assertIn("exception_class=BadRequestError", log_text)
        self.assertIn("status_code=400", log_text)
        self.assertIn("type=invalid_request_error", log_text)
        self.assertIn("code=invalid_request", log_text)
        self.assertIn("param=messages[0].role", log_text)
        self.assertNotIn(secret, log_text)

    def test_unsafe_code_and_param_are_not_logged(self) -> None:
        secret = "DO_NOT_LOG_STRUCTURED_SECRET"
        request = Request("POST", "https://example.invalid/v1/chat/completions")
        response = Response(400, request=request, text=secret)
        mock_client = MagicMock()
        provider_error = BadRequestError(
            "bad request " + secret,
            response=response,
            body={
                "type": [secret],
                "code": secret * 4,
                "param": {"secret": secret},
                "message": secret,
            },
        )
        mock_client.chat.completions.create.side_effect = provider_error
        service = OpenAIChatService(
            AISettings(
                api_key="test-key",
                base_url="https://example.invalid/v1",
                model="test-model",
            ),
            client=mock_client,
        )

        with self.assertLogs("backend.app.services.ai", level="ERROR") as captured:
            with self.assertRaisesRegex(RuntimeError, "AI"):
                service.generate_answer(
                    system_prompt="system",
                    messages=[{"role": "user", "content": "question"}],
                )

        log_text = "\n".join(captured.output)
        self.assertIn("type=None", log_text)
        self.assertIn("code=None", log_text)
        self.assertIn("param=None", log_text)
        self.assertNotIn(secret, log_text)


class FunctionCallingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.firestore = FakeFirestoreClient()
        self.mock_client = MagicMock()
        self.service = OpenAIChatService(
            AISettings(
                api_key="test-key",
                base_url="https://example.invalid/v1",
                model="test-model",
            ),
            client=self.mock_client,
        )
        self.args = {
            "keyword": "스피치",
            "start_date": "2026-06-01",
            "end_date": "2026-06-08",
        }

    @staticmethod
    def _tool_completion(arguments: str, call_id: str = "call-1") -> Any:
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                id=call_id,
                                function=SimpleNamespace(
                                    name=TOOL_NAME,
                                    arguments=arguments,
                                ),
                            )
                        ],
                    )
                )
            ]
        )

    @staticmethod
    def _answer_completion(content: str = "도구 결과를 요약했습니다.") -> Any:
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=None))]
        )

    def test_tool_schema_and_successful_round_trip(self) -> None:
        self.mock_client.chat.completions.create.side_effect = [
            self._tool_completion(json.dumps(self.args, ensure_ascii=False)),
            self._answer_completion(),
        ]

        answer = self.service.generate_answer(
            system_prompt="system",
            messages=[{"role": "user", "content": "주간 데이터를 비교해줘"}],
            tool_executor=lambda name, arguments: execute_trend_tool(
                self.firestore, name, arguments
            ),
        )

        self.assertEqual(answer, "도구 결과를 요약했습니다.")
        first_call = self.mock_client.chat.completions.create.call_args_list[0].kwargs
        self.assertEqual(first_call["tools"], [FUNCTION_TOOL_SCHEMA])
        self.assertEqual(first_call["tool_choice"], "auto")
        second_messages = self.mock_client.chat.completions.create.call_args_list[1].kwargs[
            "messages"
        ]
        self.assertEqual(second_messages[-2]["role"], "assistant")
        self.assertEqual(second_messages[-1]["role"], "tool")
        self.assertEqual(second_messages[-1]["tool_call_id"], "call-1")
        self.assertIn("상대 검색 관심도 지수", second_messages[-1]["content"])

    def test_function_calling_diagnostic_logs_only_count_and_tool_names(self) -> None:
        self.mock_client.chat.completions.create.side_effect = [
            self._tool_completion(json.dumps(self.args, ensure_ascii=False)),
            self._answer_completion(),
        ]
        private_question = "PRIVATE_USER_QUESTION"

        with self.assertLogs("backend.app.services.ai", level="INFO") as captured:
            self.service.generate_answer(
                system_prompt="system",
                messages=[{"role": "user", "content": private_question}],
                tool_executor=MagicMock(return_value={"records": []}),
            )

        log_text = "\n".join(captured.output)
        self.assertIn("function_calling_response tool_call_count=1", log_text)
        self.assertIn(f"tool_names={TOOL_NAME}", log_text)
        self.assertIn("tool_call_count=0 tool_names=none", log_text)
        self.assertNotIn(private_question, log_text)
        self.assertNotIn("start_date", log_text)
        self.assertNotIn("test-key", log_text)

    def test_invalid_tool_arguments_return_safe_tool_error_to_model(self) -> None:
        invalid_args = {**self.args, "keyword": "지원하지 않는 키워드"}
        self.mock_client.chat.completions.create.side_effect = [
            self._tool_completion(json.dumps(invalid_args, ensure_ascii=False)),
            self._answer_completion(),
        ]

        answer = self.service.generate_answer(
            system_prompt="system",
            messages=[{"role": "user", "content": "데이터"}],
            tool_executor=lambda name, arguments: execute_trend_tool(
                self.firestore, name, arguments
            ),
        )

        self.assertEqual(answer, "도구 결과를 요약했습니다.")
        tool_message = self.mock_client.chat.completions.create.call_args_list[1].kwargs[
            "messages"
        ][-1]
        self.assertIn("지원하지 않는 키워드", tool_message["content"])
        self.assertEqual(self.firestore.write_count, 0)

    def test_tool_execution_error_is_sanitized(self) -> None:
        secret_error = "service-account-private-key"
        self.mock_client.chat.completions.create.side_effect = [
            self._tool_completion(json.dumps(self.args, ensure_ascii=False)),
            self._answer_completion(),
        ]

        answer = self.service.generate_answer(
            system_prompt="system",
            messages=[{"role": "user", "content": "데이터"}],
            tool_executor=MagicMock(side_effect=RuntimeError(secret_error)),
        )

        second_request = self.mock_client.chat.completions.create.call_args_list[1].kwargs
        tool_content = second_request["messages"][-1]["content"]
        self.assertEqual(answer, "도구 결과를 요약했습니다.")
        self.assertIn("Firestore 데이터를 조회하지 못했습니다", tool_content)
        self.assertNotIn(secret_error, tool_content)

    def test_tool_call_limit_is_enforced_and_follow_up_has_no_tools(self) -> None:
        self.mock_client.chat.completions.create.side_effect = [
            *[
                self._tool_completion(json.dumps(self.args, ensure_ascii=False), f"call-{index}")
                for index in range(MAX_TOOL_CALLS)
            ],
            self._answer_completion(),
        ]
        executor = MagicMock(return_value={"records": []})

        answer = self.service.generate_answer(
            system_prompt="system",
            messages=[{"role": "user", "content": "데이터"}],
            tool_executor=executor,
        )

        self.assertEqual(answer, "도구 결과를 요약했습니다.")
        self.assertEqual(executor.call_count, MAX_TOOL_CALLS)
        final_request = self.mock_client.chat.completions.create.call_args_list[-1].kwargs
        self.assertNotIn("tools", final_request)

    def test_provider_tool_call_after_limit_fails_without_another_execution(self) -> None:
        self.mock_client.chat.completions.create.side_effect = [
            *[
                self._tool_completion(json.dumps(self.args, ensure_ascii=False), f"call-{index}")
                for index in range(MAX_TOOL_CALLS)
            ],
            self._tool_completion(json.dumps(self.args, ensure_ascii=False), "extra-call"),
        ]
        executor = MagicMock(return_value={"records": []})

        with self.assertRaisesRegex(AIProviderError, "호출 한도"):
            self.service.generate_answer(
                system_prompt="system",
                messages=[{"role": "user", "content": "데이터"}],
                tool_executor=executor,
            )

        self.assertEqual(executor.call_count, MAX_TOOL_CALLS)
        self.assertEqual(self.mock_client.chat.completions.create.call_count, MAX_TOOL_CALLS + 1)

    def test_malformed_json_arguments_become_safe_error(self) -> None:
        self.mock_client.chat.completions.create.side_effect = [
            self._tool_completion("not-json"),
            self._answer_completion(),
        ]

        answer = self.service.generate_answer(
            system_prompt="system",
            messages=[{"role": "user", "content": "데이터"}],
            tool_executor=MagicMock(),
        )

        self.assertEqual(answer, "도구 결과를 요약했습니다.")
        tool_content = self.mock_client.chat.completions.create.call_args_list[1].kwargs[
            "messages"
        ][-1]["content"]
        self.assertIn("유효한 JSON", tool_content)


if __name__ == "__main__":
    unittest.main()
