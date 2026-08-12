from yida_ai.config.settings import LLMSettings
from yida_ai.ui.ai_status import AIConnectionState, derive_ai_status


def test_provider_creation_does_not_count_as_verified():
    settings = LLMSettings(
        provider="openai-compatible",
        api_url="https://example.test/v1/chat/completions",
        model="example-model",
    )
    assert derive_ai_status(settings, has_key=False).state is AIConnectionState.UNCONFIGURED
    assert derive_ai_status(settings, has_key=True).state is AIConnectionState.CONFIGURED_UNVERIFIED


def test_verified_status_requires_matching_provider_and_model():
    settings = LLMSettings(
        provider="openai-compatible",
        api_url="https://example.test/v1/chat/completions",
        model="model-a",
        last_verified_at="2026-08-09T00:00:00+00:00",
        last_verified_provider="openai-compatible",
        last_verified_model="model-a",
    )
    assert derive_ai_status(settings, has_key=True).state is AIConnectionState.VERIFIED
    settings.model = "model-b"
    assert derive_ai_status(settings, has_key=True).state is AIConnectionState.CONFIGURED_UNVERIFIED
