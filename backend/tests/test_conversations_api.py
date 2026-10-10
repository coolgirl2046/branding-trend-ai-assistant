"""Conversation API tests using an in-memory Firestore-compatible mock."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
from typing import Any

from fastapi.testclient import TestClient
from firebase_admin import firestore

from backend.app.main import app
from backend.app.routers.conversations import get_conversation_client


class FakeSnapshot:
    def __init__(self, document_id: str, stored: dict[str, Any] | None):
        self.id = document_id
        self.exists = stored is not None
        self._stored = stored

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self._stored or {})


class FakeDocument:
    def __init__(self, client: "FakeFirestoreClient", document_id: str):
        self._client = client
        self.id = document_id

    def get(self) -> FakeSnapshot:
        return FakeSnapshot(self.id, self._client.documents.get(self.id))

    def set(self, fields: dict[str, Any]) -> None:
        resolved = self._client.resolve_server_timestamps(fields)
        self._client.documents[self.id] = resolved

    def delete(self) -> None:
        self._client.documents.pop(self.id, None)


class FakeCollection:
    def __init__(self, client: "FakeFirestoreClient"):
        self._client = client

    def document(self, document_id: str | None = None) -> FakeDocument:
        if document_id is None:
            document_id = self._client.next_document_id()
        return FakeDocument(self._client, document_id)

    def stream(self) -> list[FakeSnapshot]:
        return [
            FakeSnapshot(document_id, stored)
            for document_id, stored in self._client.documents.items()
        ]


class FakeFirestoreClient:
    def __init__(self):
        self.documents: dict[str, dict[str, Any]] = {}
        self._id_sequence = 0
        self._time_sequence = 0

    def collection(self, name: str) -> FakeCollection:
        if name != "conversations":
            raise AssertionError(f"Unexpected collection: {name}")
        return FakeCollection(self)

    def next_document_id(self) -> str:
        self._id_sequence += 1
        return f"conversation-{self._id_sequence:03d}"

    def next_timestamp(self) -> datetime:
        value = datetime(2026, 9, 9, tzinfo=timezone.utc) + timedelta(
            seconds=self._time_sequence
        )
        self._time_sequence += 1
        return value

    def resolve_server_timestamps(self, value: Any) -> Any:
        if value is firestore.SERVER_TIMESTAMP:
            return self.next_timestamp()
        if isinstance(value, dict):
            return {
                key: self.resolve_server_timestamps(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self.resolve_server_timestamps(item) for item in value]
        return deepcopy(value)


class FailingFirestoreClient:
    def collection(self, name: str) -> None:
        del name
        raise RuntimeError("private_key=DO_NOT_EXPOSE client_email=secret@example.com")


class ConversationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.firestore = FakeFirestoreClient()
        app.dependency_overrides[get_conversation_client] = lambda: self.firestore
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()

    def _store_conversation(
        self,
        document_id: str,
        title: str,
        updated_at: datetime,
        messages: list[dict[str, Any]] | None = None,
    ) -> None:
        self.firestore.documents[document_id] = {
            "title": title,
            "messages": deepcopy(messages or []),
            "created_at": updated_at - timedelta(hours=1),
            "updated_at": updated_at,
        }

    def test_post_creates_new_conversation(self) -> None:
        response = self.client.post(
            "/api/conversations", json={"title": "새 대화"}
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["id"], "conversation-001")
        self.assertEqual(body["title"], "새 대화")
        self.assertEqual(body["messages"], [])
        stored = self.firestore.documents[body["id"]]
        self.assertIn("created_at", stored)
        self.assertIn("updated_at", stored)

    def test_post_stores_valid_messages_with_created_at(self) -> None:
        response = self.client.post(
            "/api/conversations",
            json={
                "title": "질문 대화",
                "messages": [
                    {"role": "user", "content": "최근 흐름은?"},
                    {"role": "assistant", "content": "데이터를 확인합니다."},
                ],
            },
        )

        self.assertEqual(response.status_code, 201)
        messages = response.json()["messages"]
        self.assertEqual([message["role"] for message in messages], ["user", "assistant"])
        self.assertTrue(all(message["created_at"] for message in messages))

    def test_blank_title_is_rejected(self) -> None:
        response = self.client.post(
            "/api/conversations", json={"title": "   "}
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.firestore.documents, {})

    def test_invalid_message_role_is_rejected(self) -> None:
        response = self.client.post(
            "/api/conversations",
            json={
                "title": "역할 검사",
                "messages": [{"role": "system", "content": "내용"}],
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_blank_message_content_is_rejected(self) -> None:
        response = self.client.post(
            "/api/conversations",
            json={
                "title": "내용 검사",
                "messages": [{"role": "user", "content": "  "}],
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_get_list_is_sorted_by_updated_at_descending(self) -> None:
        base = datetime(2026, 9, 9, tzinfo=timezone.utc)
        self._store_conversation("old", "이전 대화", base)
        self._store_conversation(
            "new",
            "최근 대화",
            base + timedelta(hours=2),
            messages=[
                {"role": "user", "content": "질문", "created_at": base}
            ],
        )

        response = self.client.get("/api/conversations")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([item["id"] for item in body], ["new", "old"])
        self.assertEqual(body[0]["message_count"], 1)
        self.assertNotIn("messages", body[0])

    def test_get_detail_returns_all_messages(self) -> None:
        observed_at = datetime(2026, 9, 9, tzinfo=timezone.utc)
        messages = [
            {"role": "user", "content": "첫 질문", "created_at": observed_at},
            {
                "role": "assistant",
                "content": "첫 답변",
                "created_at": observed_at + timedelta(seconds=1),
            },
        ]
        self._store_conversation("detail", "상세 대화", observed_at, messages)

        response = self.client.get("/api/conversations/detail")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["messages"][0]["content"], "첫 질문")
        self.assertEqual(len(response.json()["messages"]), 2)

    def test_get_missing_conversation_returns_404(self) -> None:
        response = self.client.get("/api/conversations/missing")
        self.assertEqual(response.status_code, 404)

    def test_delete_existing_conversation(self) -> None:
        observed_at = datetime(2026, 9, 9, tzinfo=timezone.utc)
        self._store_conversation("delete-me", "삭제 대화", observed_at)

        response = self.client.delete("/api/conversations/delete-me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"deleted": True, "id": "delete-me"}
        )
        self.assertNotIn("delete-me", self.firestore.documents)

    def test_delete_missing_conversation_returns_404(self) -> None:
        response = self.client.delete("/api/conversations/missing")
        self.assertEqual(response.status_code, 404)

    def test_internal_error_does_not_expose_sensitive_details(self) -> None:
        app.dependency_overrides[get_conversation_client] = (
            lambda: FailingFirestoreClient()
        )

        response = self.client.get("/api/conversations")

        self.assertEqual(response.status_code, 500)
        response_text = response.text.lower()
        self.assertNotIn("private_key", response_text)
        self.assertNotIn("client_email", response_text)
        self.assertNotIn("do_not_expose", response_text)


if __name__ == "__main__":
    unittest.main()
