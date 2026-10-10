"""Lazy and repeat-safe Firebase Admin and Firestore initialization."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.client import Client

from backend.app.config import FirebaseSettings, load_firebase_settings


_INITIALIZATION_LOCK = Lock()


class FirebaseInitializationError(RuntimeError):
    """Raised when Firebase credentials or initialization are invalid."""


def _parse_service_account_json(raw_json: str) -> dict[str, Any]:
    try:
        credential_data = json.loads(raw_json)
    except json.JSONDecodeError:
        raise FirebaseInitializationError(
            "FIREBASE_SERVICE_ACCOUNT_JSON이 유효한 JSON 형식이 아닙니다."
        ) from None

    if not isinstance(credential_data, dict):
        raise FirebaseInitializationError(
            "FIREBASE_SERVICE_ACCOUNT_JSON은 JSON 객체여야 합니다."
        )

    required_fields = ("type", "project_id", "private_key", "client_email")
    missing_fields = [
        field for field in required_fields if not credential_data.get(field)
    ]
    if missing_fields:
        names = ", ".join(missing_fields)
        raise FirebaseInitializationError(
            f"Firebase 서비스 계정 JSON에 필수 필드가 없습니다: {names}"
        )

    if credential_data.get("type") != "service_account":
        raise FirebaseInitializationError(
            "Firebase 자격증명 type은 service_account여야 합니다."
        )

    return credential_data


def _validate_project_id(
    credential_data: dict[str, Any],
    expected_project_id: str,
) -> None:
    if credential_data["project_id"] != expected_project_id:
        raise FirebaseInitializationError(
            "FIREBASE_PROJECT_ID와 서비스 계정의 project_id가 일치하지 않습니다."
        )


def _create_firebase_credential(settings: FirebaseSettings) -> Any:
    # JSON body is checked first so Render configuration takes precedence.
    if settings.service_account_json:
        credential_data = _parse_service_account_json(
            settings.service_account_json
        )
        _validate_project_id(credential_data, settings.project_id)
        try:
            return credentials.Certificate(credential_data)
        except (OSError, TypeError, ValueError):
            raise FirebaseInitializationError(
                "Firebase 서비스 계정 JSON 자격증명을 읽을 수 없습니다."
            ) from None

    if settings.service_account_path:
        credential_path = Path(settings.service_account_path).expanduser()
        try:
            is_file = credential_path.is_file()
        except OSError:
            is_file = False
        if not is_file:
            raise FirebaseInitializationError(
                "FIREBASE_SERVICE_ACCOUNT_PATH가 유효한 파일을 가리키지 않습니다."
            )

        try:
            certificate = credentials.Certificate(str(credential_path))
        except (OSError, TypeError, ValueError):
            raise FirebaseInitializationError(
                "FIREBASE_SERVICE_ACCOUNT_PATH의 자격증명 파일을 읽을 수 없습니다."
            ) from None

        if certificate.project_id != settings.project_id:
            raise FirebaseInitializationError(
                "FIREBASE_PROJECT_ID와 서비스 계정의 project_id가 일치하지 않습니다."
            )
        return certificate

    raise FirebaseInitializationError(
        "Firebase 서비스 계정 JSON 본문 또는 파일 경로 설정이 필요합니다."
    )


def initialize_firebase_app(
    settings: FirebaseSettings | None = None,
) -> firebase_admin.App:
    """Return the default Firebase app, initializing it at most once."""

    resolved_settings = settings or load_firebase_settings()

    with _INITIALIZATION_LOCK:
        try:
            existing_app = firebase_admin.get_app()
        except ValueError:
            existing_app = None

        if existing_app is not None:
            if (
                existing_app.project_id
                and existing_app.project_id != resolved_settings.project_id
            ):
                raise FirebaseInitializationError(
                    "이미 초기화된 Firebase 앱의 프로젝트가 설정과 다릅니다."
                )
            return existing_app

        certificate = _create_firebase_credential(resolved_settings)

        try:
            return firebase_admin.initialize_app(
                certificate,
                {"projectId": resolved_settings.project_id},
            )
        except (TypeError, ValueError):
            raise FirebaseInitializationError(
                "Firebase 서비스 계정 자격증명을 초기화할 수 없습니다."
            ) from None


def get_firestore_client(
    settings: FirebaseSettings | None = None,
) -> Client:
    """Create a Firestore client without performing document operations."""

    app = initialize_firebase_app(settings)
    try:
        return firestore.client(app=app)
    except Exception:
        raise FirebaseInitializationError(
            "Firestore client를 생성할 수 없습니다. Firebase 설정을 확인하세요."
        ) from None
