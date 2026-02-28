import importlib


def test_indigenous_language_hint_falls_back_to_auto_for_transcription():
    language_support = importlib.import_module("app.language_support")
    assert language_support.normalize_source_language_for_transcription("tay") is None


def test_supported_language_hint_is_kept_for_transcription():
    language_support = importlib.import_module("app.language_support")
    assert language_support.normalize_source_language_for_transcription("ja") == "ja"


def test_language_hint_description_uses_friendly_name():
    language_support = importlib.import_module("app.language_support")
    assert language_support.describe_language_hint("tay") == "Atayal (tay)"
