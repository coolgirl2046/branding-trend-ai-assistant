"""Environment-backed settings for Firebase and the AI provider.

Loading is explicit so importing this module never initializes Firebase or
requires credentials to be present.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


class ConfigurationError(RuntimeError):
    """Raised when required environment configuration is unavailable."""


@dataclass(frozen=True)
class FirebaseSettings:
    project_id: str
    service_account_json: str | None = field(default=None, repr=False)
    service_account_path: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class AISettings:
    api_key: str = field(repr=False)
    base_url: str
    model: str
    provider: str = "openai"
    max_output_tokens: int = 800
    token_parameter: str = "max_completion_tokens"


DEFAULT_AI_PROVIDER = "openai"
AI_PROVIDER_VARIABLES = {
    "openai": (
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
    ),
    "gemini": (
        "GEMINI_API_KEY",
        "GEMINI_BASE_URL",
        "GEMINI_MODEL",
    ),
}


def load_firebase_settings(
    env_file: str | Path = DEFAULT_ENV_FILE,
) -> FirebaseSettings:
    """Load Firebase settings without printing or logging secret values."""

    load_dotenv(dotenv_path=env_file, override=False)

    project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
    service_account_json = (
        os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip() or None
    )
    service_account_path = (
        os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip() or None
    )

    missing = []
    if not project_id:
        missing.append("FIREBASE_PROJECT_ID")
    if not service_account_json and not service_account_path:
        missing.append(
            "FIREBASE_SERVICE_ACCOUNT_JSON 또는 FIREBASE_SERVICE_ACCOUNT_PATH"
        )

    if missing:
        names = ", ".join(missing)
        raise ConfigurationError(f"필수 Firebase 환경 변수가 없습니다: {names}")

    return FirebaseSettings(
        project_id=project_id,
        service_account_json=service_account_json,
        service_account_path=service_account_path,
    )


def load_ai_settings(
    env_file: str | Path = DEFAULT_ENV_FILE,
) -> AISettings:
    """Load AI provider settings without exposing the API key."""

    load_dotenv(dotenv_path=env_file, override=False)
    provider = os.getenv("AI_PROVIDER", DEFAULT_AI_PROVIDER).strip().lower()
    if provider not in AI_PROVIDER_VARIABLES:
        raise ConfigurationError(
            "AI_PROVIDER는 openai 또는 gemini여야 합니다."
        )

    api_key_name, base_url_name, model_name = AI_PROVIDER_VARIABLES[provider]
    values = {
        api_key_name: os.getenv(api_key_name, "").strip(),
        base_url_name: os.getenv(base_url_name, "").strip(),
        model_name: os.getenv(model_name, "").strip(),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ConfigurationError(
            "필수 AI 환경 변수가 없습니다: " + ", ".join(missing)
        )

    try:
        max_output_tokens = int(os.getenv("AI_MAX_OUTPUT_TOKENS", "800"))
    except ValueError:
        raise ConfigurationError("AI_MAX_OUTPUT_TOKENS는 1~4096 정수여야 합니다.") from None
    if not 1 <= max_output_tokens <= 4096:
        raise ConfigurationError("AI_MAX_OUTPUT_TOKENS는 1~4096 정수여야 합니다.")
    token_parameter = os.getenv("AI_TOKEN_PARAMETER", "max_completion_tokens").strip()
    if token_parameter not in {"max_completion_tokens", "max_tokens"}:
        raise ConfigurationError("AI_TOKEN_PARAMETER 설정을 확인해 주세요.")

    return AISettings(
        max_output_tokens=max_output_tokens,
        token_parameter=token_parameter,
        provider=provider,
        api_key=values[api_key_name],
        base_url=values[base_url_name],
        model=values[model_name],
    )
