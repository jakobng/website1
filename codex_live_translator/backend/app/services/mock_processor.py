from .provider_base import ProcessedSegment, SegmentProcessor
from ..language_support import parse_two_way_target


class MockProcessor(SegmentProcessor):
    async def process(
        self,
        audio_bytes: bytes,
        mime_type: str,
        source_lang: str,
        target_lang: str,
        prior_context: list[str],
        conversation_context: str | None = None,
    ) -> ProcessedSegment:
        size_kb = max(1, len(audio_bytes) // 1024)
        transcript = (
            f"[{source_lang}] audio segment received ({size_kb} KB). "
            "Switch FT_PROVIDER=openai for real transcription."
        )
        translation = await self.translate_text(
            transcript=transcript,
            source_lang=source_lang,
            target_lang=target_lang,
            prior_context=prior_context,
            conversation_context=conversation_context,
        )
        return ProcessedSegment(
            transcript_src=transcript,
            translation_en=translation,
            confidence=0.25,
            is_final=True,
        )

    async def translate_text(
        self,
        transcript: str,
        source_lang: str,
        target_lang: str,
        prior_context: list[str],
        conversation_context: str | None = None,
    ) -> str:
        context_note = ""
        if prior_context:
            context_note = f" Context tail: {prior_context[-1][:120]}"
        if conversation_context:
            context_note += f" Topic hint: {conversation_context[:120]}"
        two_way_target = parse_two_way_target(target_lang)
        if two_way_target:
            return f"AUTO({two_way_target}<->EN) gist: {transcript[:160]}{context_note}"
        return f"{target_lang.upper()} gist: {transcript[:160]}{context_note}"
