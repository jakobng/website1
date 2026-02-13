from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class ProcessedSegment:
    transcript_src: str
    translation_en: str
    confidence: float
    is_final: bool = True


class SegmentProcessor(ABC):
    @abstractmethod
    async def process(
        self,
        audio_bytes: bytes,
        mime_type: str,
        source_lang: str,
        target_lang: str,
        prior_context: list[str],
        conversation_context: str | None = None,
    ) -> ProcessedSegment:
        raise NotImplementedError
