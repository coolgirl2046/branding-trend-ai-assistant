"""Grounded AI chat endpoint with automatic conversation persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from firebase_admin import firestore

from backend.app.database import get_firestore_client
from backend.app.routers.conversations import CONVERSATIONS_COLLECTION
from backend.app.schemas import ChatRequest, ChatResponse
from backend.app.services.ai import (
    AIProviderError,
    OpenAIChatService,
    build_system_prompt,
    create_ai_chat_service,
)
from backend.app.services.data_summary import calculate_firestore_summary


router = APIRouter(prefix="/api/chat", tags=["chat"])
TITLE_MAX_LENGTH = 50


def get_chat_client() -> Any:
    return get_firestore_client()


def get_ai_chat_service() -> OpenAIChatService:
    try:
        return create_ai_chat_service()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 서비스 설정을 확인할 수 없습니다.",
        ) from None


def _raise_internal_error() -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="채팅 처리 중 서버 오류가 발생했습니다.",
    ) from None


def _make_title(message: str) -> str:
    single_line = " ".join(message.split())
    if len(single_line) <= TITLE_MAX_LENGTH:
        return single_line
    return single_line[: TITLE_MAX_LENGTH - 3].rstrip() + "..."


def _provider_history(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    history = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant"}:
            raise ValueError("저장된 대화 role이 유효하지 않습니다.")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("저장된 대화 content가 유효하지 않습니다.")
        history.append({"role": role, "content": content})
    return history


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    client: Annotated[Any, Depends(get_chat_client)],
    ai_service: Annotated[OpenAIChatService, Depends(get_ai_chat_service)],
) -> dict[str, Any]:
    try:
        collection = client.collection(CONVERSATIONS_COLLECTION)
        created_new = payload.conversation_id is None

        if created_new:
            document = collection.document()
            existing_messages: list[dict[str, Any]] = []
            title = _make_title(payload.message)
        else:
            document = collection.document(payload.conversation_id)
            snapshot = document.get()
            if not snapshot.exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="대화를 찾을 수 없습니다.",
                )
            stored = snapshot.to_dict()
            existing_messages = list(stored.get("messages", []))
            title = stored["title"]

        model_messages = _provider_history(existing_messages)
        model_messages.append({"role": "user", "content": payload.message})
        summary = calculate_firestore_summary(client)
        system_prompt = build_system_prompt(summary)

        try:
            answer = ai_service.generate_answer(
                system_prompt=system_prompt,
                messages=model_messages,
            )
        except AIProviderError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI 응답을 생성하지 못했습니다.",
            ) from None
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI 응답을 생성하지 못했습니다.",
            ) from None

        message_time = datetime.now(timezone.utc)
        updated_messages = [
            *existing_messages,
            {
                "role": "user",
                "content": payload.message,
                "created_at": message_time,
            },
            {
                "role": "assistant",
                "content": answer,
                "created_at": message_time,
            },
        ]

        if created_new:
            document.set(
                {
                    "title": title,
                    "messages": updated_messages,
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                }
            )
        else:
            document.update(
                {
                    "messages": updated_messages,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                }
            )

        return {
            "conversation_id": document.id,
            "answer": answer,
            "created_new_conversation": created_new,
        }
    except HTTPException:
        raise
    except Exception:
        _raise_internal_error()
