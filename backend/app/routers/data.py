"""Firestore-backed data CRUD and summary endpoints."""

from __future__ import annotations

from typing import Annotated, Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from firebase_admin import firestore

from backend.app.database import get_firestore_client
from backend.app.schemas import (
    DataSummaryResponse,
    DeleteDataResponse,
    TrendDataCreate,
    TrendDataResponse,
    TrendDataUpdate,
)
from backend.app.services.data_summary import calculate_firestore_summary
from backend.app.services.summary import ALLOWED_KEYWORDS
from backend.scripts.seed_data import FIRESTORE_COLLECTION, make_document_id


router = APIRouter(prefix="/api/data", tags=["data"])
KEYWORD_ORDER = {
    keyword: index for index, keyword in enumerate(ALLOWED_KEYWORDS)
}


def get_data_client() -> Any:
    """Dependency boundary overridden by unit tests."""
    return get_firestore_client()


def _raise_internal_error() -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="데이터 처리 중 서버 오류가 발생했습니다.",
    ) from None


def _response_from_snapshot(snapshot: Any) -> dict[str, Any]:
    stored = snapshot.to_dict()
    return {
        "id": snapshot.id,
        "date": stored["date"],
        "keyword": stored["keyword"],
        "value": stored["value"],
        "memo": stored.get("memo"),
    }


@router.post(
    "",
    response_model=TrendDataResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_data(
    payload: TrendDataCreate,
    client: Annotated[Any, Depends(get_data_client)],
) -> dict[str, Any]:
    try:
        document_id = make_document_id(payload.date, payload.keyword.value)
        document = client.collection(FIRESTORE_COLLECTION).document(document_id)
        if document.get().exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="같은 날짜와 키워드의 데이터가 이미 존재합니다.",
            )

        stored = payload.model_dump(mode="json")
        stored.update(
            created_at=firestore.SERVER_TIMESTAMP,
            updated_at=firestore.SERVER_TIMESTAMP,
        )
        document.set(stored)
        return {"id": document_id, **payload.model_dump(mode="json")}
    except HTTPException:
        raise
    except Exception:
        _raise_internal_error()


@router.get("", response_model=list[TrendDataResponse])
def list_data(
    client: Annotated[Any, Depends(get_data_client)],
) -> list[dict[str, Any]]:
    try:
        items = [
            _response_from_snapshot(snapshot)
            for snapshot in client.collection(FIRESTORE_COLLECTION).stream()
        ]
        items.sort(
            key=lambda item: (
                item["date"],
                KEYWORD_ORDER.get(item["keyword"], len(KEYWORD_ORDER)),
            )
        )
        return items
    except Exception:
        _raise_internal_error()


@router.get("/summary", response_model=DataSummaryResponse)
def get_data_summary(
    client: Annotated[Any, Depends(get_data_client)],
) -> dict[str, Any]:
    try:
        return calculate_firestore_summary(client)
    except Exception:
        _raise_internal_error()


@router.put("/{document_id}", response_model=TrendDataResponse)
def update_data(
    document_id: str,
    payload: TrendDataUpdate,
    client: Annotated[Any, Depends(get_data_client)],
) -> dict[str, Any]:
    try:
        collection = client.collection(FIRESTORE_COLLECTION)
        current_document = collection.document(document_id)
        current_snapshot = current_document.get()
        if not current_snapshot.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="수정할 데이터를 찾을 수 없습니다.",
            )

        new_document_id = make_document_id(payload.date, payload.keyword.value)
        input_fields = payload.model_dump(mode="json")

        if new_document_id == document_id:
            current_document.update(
                {**input_fields, "updated_at": firestore.SERVER_TIMESTAMP}
            )
        else:
            new_document = collection.document(new_document_id)
            if new_document.get().exists:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="변경할 날짜와 키워드의 데이터가 이미 존재합니다.",
                )

            current_data = current_snapshot.to_dict()
            created_at = current_data.get(
                "created_at", firestore.SERVER_TIMESTAMP
            )
            batch = client.batch()
            batch.set(
                new_document,
                {
                    **input_fields,
                    "created_at": created_at,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                },
            )
            batch.delete(current_document)
            batch.commit()

        return {"id": new_document_id, **input_fields}
    except HTTPException:
        raise
    except Exception:
        _raise_internal_error()


@router.delete("/{document_id}", response_model=DeleteDataResponse)
def delete_data(
    document_id: str,
    client: Annotated[Any, Depends(get_data_client)],
) -> dict[str, Any]:
    try:
        document = client.collection(FIRESTORE_COLLECTION).document(document_id)
        if not document.get().exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="삭제할 데이터를 찾을 수 없습니다.",
            )
        document.delete()
        return {"deleted": True, "id": document_id}
    except HTTPException:
        raise
    except Exception:
        _raise_internal_error()
