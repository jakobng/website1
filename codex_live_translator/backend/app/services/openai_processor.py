import asyncio
import json

import httpx

from .provider_base import ProcessedSegment, SegmentProcessor


class OpenAIProcessor(SegmentProcessor):
    def __init__(
        self,
        api_key: str,
        transcribe_model: str,
        translate_model: str,
        timeout_seconds: int,
    ) -> None:
        self.api_key = api_key
        self.transcribe_model = transcribe_model
        self.translate_model = translate_model
        self.timeout_seconds = timeout_seconds

    async def process(
        self,
        audio_bytes: bytes,
        mime_type: str,
        source_lang: str,
        target_lang: str,
        prior_context: list[str],
        conversation_context: str | None = None,
    ) -> ProcessedSegment:
        transcript = await self._transcribe(audio_bytes, mime_type, source_lang)
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
            confidence=0.7,
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
        return await self._translate(
            transcript=transcript,
            source_lang=source_lang,
            target_lang=target_lang,
            prior_context=prior_context,
            conversation_context=conversation_context,
        )

    async def _transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str,
        source_lang: str,
    ) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {"model": self.transcribe_model}
        if source_lang and source_lang != "auto":
            data["language"] = source_lang

        files = {
            "file": (
                "segment.webm",
                audio_bytes,
                mime_type or "audio/webm",
            )
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await self._post_with_retry(
                client=client,
                url="https://api.openai.com/v1/audio/transcriptions",
                headers=headers,
                data=data,
                files=files,
            )

        payload = response.json()
        text = payload.get("text", "").strip()
        if not text:
            raise RuntimeError("Empty transcription returned from OpenAI")
        return text

    async def _translate(
        self,
        transcript: str,
        source_lang: str,
        target_lang: str,
        prior_context: list[str],
        conversation_context: str | None = None,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        context_block = "\n".join(prior_context[-4:])
        system_prompt = (
            "You are a real-time interpreter for a documentary filmmaker. "
            "Return concise, natural translation in the requested target language while preserving important facts, names, and intent."
        )

        user_prompt = (
            f"Source language hint: {source_lang}.\n"
            f"Target language: {target_lang}.\n"
            "Expected conversation context:\n"
            f"{conversation_context.strip() if conversation_context else '(none)'}\n\n"
            "Recent context (oldest to newest):\n"
            f"{context_block if context_block else '(none)'}\n\n"
            "Current transcript:\n"
            f"{transcript}\n\n"
            "Return only the translated line."
        )

        payload = {
            "model": self.translate_model,
            "temperature": 0.2,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await self._post_with_retry(
                client=client,
                url="https://api.openai.com/v1/responses",
                headers=headers,
                content=json.dumps(payload),
            )

        body = response.json()

        output_text = body.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        fragments: list[str] = []
        for item in body.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    fragments.append(text.strip())

        if fragments:
            return " ".join(fragments)

        return transcript

    async def _post_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        **kwargs: object,
    ) -> httpx.Response:
        max_attempts = 3
        retry_statuses = {429, 500, 502, 503, 504}

        for attempt in range(1, max_attempts + 1):
            response = await client.post(url, **kwargs)
            if response.status_code < 400:
                return response

            message = self._extract_error_message(response)
            if response.status_code in retry_statuses and attempt < max_attempts:
                await asyncio.sleep(attempt * 1.5)
                continue

            raise RuntimeError(
                f"OpenAI request failed ({response.status_code}): {message}"
            )

        raise RuntimeError("OpenAI request failed after retries")

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text.strip()[:300] or response.reason_phrase

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                err_type = error.get("type")
                code = error.get("code")
                details = [part for part in [str(err_type) if err_type else "", str(code) if code else "", str(message) if message else ""] if part]
                if details:
                    return " | ".join(details)

        return str(payload)[:300]
