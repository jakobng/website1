TRANSCRIPTION_LANGUAGE_CODES = {
    "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo", "br", "bs", "ca", "cs", "cy",
    "da", "de", "el", "en", "es", "et", "eu", "fa", "fi", "fo", "fr", "gl", "gu", "ha", "haw",
    "he", "hi", "hr", "ht", "hu", "hy", "id", "is", "it", "ja", "jw", "ka", "kk", "km", "kn",
    "ko", "la", "lb", "ln", "lo", "lt", "lv", "mg", "mi", "mk", "ml", "mn", "mr", "ms", "mt",
    "my", "ne", "nl", "nn", "no", "oc", "pa", "pl", "ps", "pt", "ro", "ru", "sa", "sd", "si",
    "sk", "sl", "sn", "so", "sq", "sr", "su", "sv", "sw", "ta", "te", "tg", "th", "tk", "tl",
    "tr", "tt", "uk", "ur", "uz", "vi", "yi", "yo", "zh",
}

LANGUAGE_HINT_NAMES = {
    "nan": "Taiwanese Hokkien",
    "hak": "Taiwanese Hakka",
    "ami": "Amis",
    "tay": "Atayal",
    "pwn": "Paiwan",
}


def normalize_source_language_for_transcription(source_lang: str) -> str | None:
    normalized = (source_lang or "").strip().lower()
    if not normalized or normalized == "auto":
        return None
    if normalized in TRANSCRIPTION_LANGUAGE_CODES:
        return normalized
    return None


def describe_language_hint(language_code: str) -> str:
    normalized = (language_code or "").strip().lower()
    if not normalized:
        return "auto"
    if normalized == "auto":
        return "auto detect"
    name = LANGUAGE_HINT_NAMES.get(normalized)
    if name:
        return f"{name} ({normalized})"
    return normalized
