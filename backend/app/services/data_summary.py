"""Shared Firestore-to-summary adapter for data and chat endpoints."""

from __future__ import annotations

from typing import Any

from backend.app.services.summary import calculate_summary
from backend.scripts.seed_data import FIRESTORE_COLLECTION


def calculate_firestore_summary(client: Any) -> dict[str, Any]:
    records = []
    for snapshot in client.collection(FIRESTORE_COLLECTION).stream():
        stored = snapshot.to_dict()
        records.append(
            {
                "date": stored["date"],
                "keyword": stored["keyword"],
                "value": stored["value"],
            }
        )
    return calculate_summary(records)
