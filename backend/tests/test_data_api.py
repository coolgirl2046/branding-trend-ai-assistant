"""Data API tests using an in-memory Firestore-compatible mock."""

from __future__ import annotations

from datetime import date, timedelta
import unittest
from typing import Any

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers.data import get_data_client
from backend.app.services.summary import METRIC_NOTE
from backend.scripts.seed_data import KEYWORDS, make_document_id


class FakeSnapshot:
    def __init__(self, document_id: str, stored: dict[str, Any] | None):
        self.id = document_id
        self.exists = stored is not None
        self._stored = stored

    def to_dict(self) -> dict[str, Any]:
        return dict(self._stored or {})


class FakeDocument:
    def __init__(self, client: "FakeFirestoreClient", document_id: str):
        self._client = client
        self.id = document_id

    def get(self) -> FakeSnapshot:
        stored = self._client.documents.get(self.id)
        return FakeSnapshot(self.id, stored)

    def set(self, fields: dict[str, Any]) -> None:
        self._client.documents[self.id] = dict(fields)

    def update(self, fields: dict[str, Any]) -> None:
        self._client.documents[self.id].update(fields)

    def delete(self) -> None:
        self._client.documents.pop(self.id, None)


class FakeCollection:
    def __init__(self, client: "FakeFirestoreClient"):
        self._client = client

    def document(self, document_id: str) -> FakeDocument:
        return FakeDocument(self._client, document_id)

    def stream(self) -> list[FakeSnapshot]:
        return [
            FakeSnapshot(document_id, stored)
            for document_id, stored in self._client.documents.items()
        ]


class FakeBatch:
    def __init__(self):
        self.operations: list[tuple[str, FakeDocument, dict[str, Any] | None]] = []

    def set(self, document: FakeDocument, fields: dict[str, Any]) -> None:
        self.operations.append(("set", document, dict(fields)))

    def delete(self, document: FakeDocument) -> None:
        self.operations.append(("delete", document, None))

    def commit(self) -> None:
        for operation, document, fields in self.operations:
            if operation == "set":
                document.set(fields or {})
            else:
                document.delete()


class FakeFirestoreClient:
    def __init__(self):
        self.documents: dict[str, dict[str, Any]] = {}

    def collection(self, name: str) -> FakeCollection:
        if name != "data":
            raise AssertionError(f"Unexpected collection: {name}")
        return FakeCollection(self)

    def batch(self) -> FakeBatch:
        return FakeBatch()


class DataApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.firestore = FakeFirestoreClient()
        app.dependency_overrides[get_data_client] = lambda: self.firestore
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()

    def _store(
        self,
        observed_date: str,
        keyword: str,
        value: float,
        memo: str | None = None,
    ) -> str:
        document_id = make_document_id(observed_date, keyword)
        self.firestore.documents[document_id] = {
            "date": observed_date,
            "keyword": keyword,
            "value": float(value),
            "memo": memo,
            "created_at": "original-created-at",
            "updated_at": "original-updated-at",
        }
        return document_id

    def test_post_creates_data(self) -> None:
        response = self.client.post(
            "/api/data",
            json={
                "date": "2026-07-27",
                "keyword": "스피치",
                "value": 72.5,
                "memo": "테스트",
            },
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["id"], "2026-07-27_speech")
        self.assertIn(body["id"], self.firestore.documents)
        self.assertIn("created_at", self.firestore.documents[body["id"]])
        self.assertIn("updated_at", self.firestore.documents[body["id"]])

    def test_post_duplicate_returns_409(self) -> None:
        self._store("2026-07-20", "스피치", 70.0)
        response = self.client.post(
            "/api/data",
            json={"date": "2026-07-20", "keyword": "스피치", "value": 80},
        )
        self.assertEqual(response.status_code, 409)

    def test_get_returns_date_and_keyword_sorted_list(self) -> None:
        self._store("2026-07-20", "스피치", 70)
        self._store("2026-07-13", "이미지메이킹", 10)
        self._store("2026-07-13", "퍼스널브랜딩", 20)

        response = self.client.get("/api/data")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["keyword"] for item in response.json()],
            ["퍼스널브랜딩", "이미지메이킹", "스피치"],
        )

    def test_put_updates_document_without_id_change(self) -> None:
        document_id = self._store("2026-07-20", "스피치", 70)
        response = self.client.put(
            f"/api/data/{document_id}",
            json={
                "date": "2026-07-20",
                "keyword": "스피치",
                "value": 75,
                "memo": "수정",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], document_id)
        self.assertEqual(self.firestore.documents[document_id]["value"], 75.0)
        self.assertEqual(
            self.firestore.documents[document_id]["created_at"],
            "original-created-at",
        )

    def test_put_moves_document_when_id_changes(self) -> None:
        old_id = self._store("2026-07-20", "스피치", 70)
        response = self.client.put(
            f"/api/data/{old_id}",
            json={
                "date": "2026-07-27",
                "keyword": "퍼스널브랜딩",
                "value": 30,
                "memo": None,
            },
        )

        new_id = "2026-07-27_personal-branding"
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], new_id)
        self.assertNotIn(old_id, self.firestore.documents)
        self.assertIn(new_id, self.firestore.documents)
        self.assertEqual(
            self.firestore.documents[new_id]["created_at"],
            "original-created-at",
        )

    def test_put_id_collision_returns_409(self) -> None:
        old_id = self._store("2026-07-20", "스피치", 70)
        target_id = self._store("2026-07-27", "퍼스널브랜딩", 30)
        response = self.client.put(
            f"/api/data/{old_id}",
            json={
                "date": "2026-07-27",
                "keyword": "퍼스널브랜딩",
                "value": 40,
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn(old_id, self.firestore.documents)
        self.assertIn(target_id, self.firestore.documents)

    def test_delete_removes_existing_document(self) -> None:
        document_id = self._store("2026-07-20", "스피치", 70)
        response = self.client.delete(f"/api/data/{document_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted": True, "id": document_id})
        self.assertNotIn(document_id, self.firestore.documents)

    def test_delete_missing_document_returns_404(self) -> None:
        response = self.client.delete("/api/data/2026-07-20_speech")
        self.assertEqual(response.status_code, 404)

    def test_summary_reuses_validated_summary_logic(self) -> None:
        first_date = date(2026, 6, 1)
        bases = {"퍼스널브랜딩": 10, "이미지메이킹": 5, "스피치": 50}
        for keyword in KEYWORDS:
            for offset in range(8):
                observed_date = (first_date + timedelta(weeks=offset)).isoformat()
                self._store(observed_date, keyword, bases[keyword] + offset)

        response = self.client.get("/api/data/summary")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total_count"], 24)
        self.assertEqual(body["start_date"], "2026-06-01")
        self.assertEqual(body["end_date"], "2026-07-20")
        self.assertEqual(body["metric_note"], METRIC_NOTE)
        self.assertEqual(body["trend_rule"]["stability_threshold"], 0.5)
        self.assertEqual(body["keywords"]["스피치"]["trend"], "상승")
        self.assertEqual(body["ranking"][0]["keyword"], "스피치")

    def test_invalid_keyword_is_rejected(self) -> None:
        response = self.client.post(
            "/api/data",
            json={"date": "2026-07-27", "keyword": "브랜드", "value": 10},
        )
        self.assertEqual(response.status_code, 422)

    def test_invalid_date_is_rejected(self) -> None:
        response = self.client.post(
            "/api/data",
            json={"date": "2026-02-30", "keyword": "스피치", "value": 10},
        )
        self.assertEqual(response.status_code, 422)

    def test_non_finite_value_is_rejected(self) -> None:
        response = self.client.post(
            "/api/data",
            content=(
                '{"date":"2026-07-27","keyword":"스피치",'
                '"value":1e999}'
            ),
            headers={"content-type": "application/json"},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
