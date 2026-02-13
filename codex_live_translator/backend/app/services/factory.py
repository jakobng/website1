import logging

from ..config import Settings
from .mock_processor import MockProcessor
from .openai_processor import OpenAIProcessor
from .provider_base import SegmentProcessor

logger = logging.getLogger(__name__)


def build_processor(settings: Settings) -> SegmentProcessor:
    provider = settings.provider.strip().lower()

    if provider == "openai":
        if not settings.openai_api_key:
            logger.warning("FT_PROVIDER=openai but FT_OPENAI_API_KEY is missing, falling back to mock provider")
            return MockProcessor()
        return OpenAIProcessor(
            api_key=settings.openai_api_key,
            transcribe_model=settings.openai_transcribe_model,
            translate_model=settings.openai_translate_model,
            timeout_seconds=settings.segment_timeout_seconds,
        )

    if provider != "mock":
        logger.warning("Unknown provider '%s', using mock provider", provider)

    return MockProcessor()