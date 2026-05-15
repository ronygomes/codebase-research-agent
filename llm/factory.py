from django.conf import settings

from llm.providers.base import LLMProvider
from llm.providers.gemini import GeminiProvider


def get_llm_provider() -> LLMProvider:
    provider = settings.LLM_PROVIDER
    if provider == "gemini":
        return GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            model_name=settings.LLM_MODEL,
            retry_on_rate_limit=settings.ENABLE_GEMINI_RETRY_BACKOFF,
        )
    raise ValueError(f"Unknown LLM provider: {provider}")
