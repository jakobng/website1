from .provider_base import ProcessedSegment, SegmentProcessor


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

        context_note = ""
        if prior_context:
            context_note = f" Context tail: {prior_context[-1][:120]}"
        if conversation_context:
            context_note += f" Topic hint: {conversation_context[:120]}"

        translation = (
            f"EN gist: captured audio ({size_kb} KB).{context_note}"
        )
        return ProcessedSegment(
            transcript_src=transcript,
            translation_en=translation,
            confidence=0.25,
            is_final=True,
        )
