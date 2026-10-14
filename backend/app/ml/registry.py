from app.core.exceptions import AppError
from .mock_provider import MockSpeechAnalysisProvider
from .custom_provider import CustomSpeechAnalysisProvider

PROVIDERS = {
    "mock": MockSpeechAnalysisProvider,
    "evaluator": CustomSpeechAnalysisProvider,
    "custom": CustomSpeechAnalysisProvider,
}


def register(name, factory):
    PROVIDERS[name] = factory


def get_provider(settings):
    name = settings.analysis_provider
    if name == "mock" and not settings.enable_demo_mode:
        raise AppError(
            "PROVIDER_UNAVAILABLE",
            "Demo mode is disabled. Configure a real analysis provider.",
            503,
        )
    factory = PROVIDERS.get(name)
    if factory is None:
        raise AppError(
            "PROVIDER_UNAVAILABLE",
            f"Configured provider {name!r} is not registered.",
            503,
        )
    provider = factory(settings)
    health = provider.health_check()
    if not health.ready:
        raise AppError(
            "PROVIDER_UNAVAILABLE",
            health.message,
            503,
        )
    return provider
