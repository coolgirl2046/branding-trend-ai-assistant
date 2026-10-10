"""Firestore-backed conversation CRUD endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from firebase_admin import firestore

from backend.app.database import get_firestore_client
from backend.app.schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationListItem,
    DeleteConversationResponse,
)


CONVERSATIONS_COLLECTION = "conversations"
router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def get_conversation_client() -> Any:
    """Dependency boundary overridden by unit tests."""
    return get_firestore_client()


def _raise_internal_error() -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="대화 처리 중 서버 오류가 발생했습니다.",
    ) from None


def _timestamp_to_iso(value: Any) -> str:
    if not isinstance(value, datetime):
        raise ValueError("대화 시간 필드가 유효하지 않습니다.")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _message_from_stored(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": message["role"],
        "content": message["content"],
        "created_at": _timestamp_to_iso(message["created_at"]),
    }


def _detail_from_snapshot(snapshot: Any) -> dict[str, Any]:
    stored = snapshot.to_dict()
    return {
        "id": snapshot.id,
        "title": stored["title"],
        "messages": [
            _message_from_stored(message)
            for message in stored.get("messages", [])
        ],
        "created_at": _timestamp_to_iso(stored["created_at"]),
        "updated_at": _timestamp_to_iso(stored["updated_at"]),
    }


@router.post(
    "",
    response_model=ConversationDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: ConversationCreate,
    client: Annotated[Any, Depends(get_conversation_client)],
) -> dict[str, Any]:
    try:
        collection = client.collection(CONVERSATIONS_COLLECTION)
        document = collection.document()
        message_time = datetime.now(timezone.utc)
        messages = [
            {
                "role": message.role,
                "content": message.content,
                "created_at": message_time,
            }
            for message in payload.messages
        ]
        document.set(
            {
                "title": payload.title,
                "messages": messages,
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )
        created_snapshot = document.get()
        if not created_snapshot.exists:
            _raise_internal_error()
        return _detail_from_snapshot(created_snapshot)
    except HTTPException:
        raise
    except Exception:
        _raise_internal_error()


@router.get("", response_model=list[ConversationListItem])
def list_conversations(
    client: Annotated[Any, Depends(get_conversation_client)],
) -> list[dict[str, Any]]:
    try:
        conversations = []
        for snapshot in client.collection(CONVERSATIONS_COLLECTION).stream():
            detail = _detail_from_snapshot(snapshot)
            conversations.append(
                {
                    "id": detail["id"],
                    "title": detail["title"],
                    "message_count": len(detail["messages"]),
                    "created_at": detail["created_at"],
                    "updated_at": detail["updated_at"],
                }
            )
        conversations.sort(key=lambda item: item["updated_at"], reverse=True)
        return conversations
    except Exception:
        _raise_internal_error()


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    client: Annotated[Any, Depends(get_conversation_client)],
) -> dict[str, Any]:
    try:
        snapshot = (
            client.collection(CONVERSATIONS_COLLECTION)
            .document(conversation_id)
            .get()
        )
        if not snapshot.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="대화를 찾을 수 없습니다.",
            )
        return _detail_from_snapshot(snapshot)
    except HTTPException:
        raise
    except Exception:
        _raise_internal_error()


@router.delete(
    "/{conversation_id}",
    response_model=DeleteConversationResponse,
)
def delete_conversation(
    conversation_id: str,
    client: Annotated[Any, Depends(get_conversation_client)],
) -> dict[str, Any]:
    try:
        document = client.collection(CONVERSATIONS_COLLECTION).document(
            conversation_id
        )
        if not document.get().exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="삭제할 대화를 찾을 수 없습니다.",
            )
        document.delete()
        return {"deleted": True, "id": conversation_id}
    except HTTPException:
        raise
    except Exception:
        _raise_internal_error()
