"""Fallback language provider — text passthrough; never pretends to transcribe or translate."""

from __future__ import annotations

from language.base import (
    DetectResult,
    LanguageCapabilities,
    LanguageInfo,
    LanguageServiceUnavailable,
    SpeakResult,
    TranscribeResult,
    TranslateResult,
    TransliterateResult,
)

# (start, end, script, default language). Devanagari is shared by several languages → "hi" default.
_SCRIPT_RANGES: tuple[tuple[int, int, str, str], ...] = (
    (0x0900, 0x097F, "Deva", "hi"),
    (0x0980, 0x09FF, "Beng", "bn"),
    (0x0A00, 0x0A7F, "Guru", "pa"),
    (0x0A80, 0x0AFF, "Gujr", "gu"),
    (0x0B00, 0x0B7F, "Orya", "or"),
    (0x0B80, 0x0BFF, "Taml", "ta"),
    (0x0C00, 0x0C7F, "Telu", "te"),
    (0x0C80, 0x0CFF, "Knda", "kn"),
    (0x0D00, 0x0D7F, "Mlym", "ml"),
    (0x0600, 0x06FF, "Arab", "ur"),
)


def detect_script(text: str) -> tuple[str, str]:
    """(script, language) by majority of non-Latin letters; Latin-only text → English."""
    counts: dict[tuple[str, str], int] = {}
    for ch in text or "":
        cp = ord(ch)
        for start, end, script, lang in _SCRIPT_RANGES:
            if start <= cp <= end:
                counts[(script, lang)] = counts.get((script, lang), 0) + 1
                break
    if not counts:
        return "Latn", "en"
    return max(counts.items(), key=lambda kv: kv[1])[0]


class FallbackLanguageProvider:
    name = "fallback"

    def __init__(self, reason: str = "BHASHINI is not configured.") -> None:
        self.reason = reason

    def capabilities(self) -> LanguageCapabilities:
        return LanguageCapabilities(
            provider=self.name,
            configured=False,
            detection="heuristic",
            languages=[LanguageInfo(code="en", name="English")],
            notes=[self.reason, "Text input works in English; voice and translation are unavailable."],
        )

    def detect_language(self, text: str) -> DetectResult:
        script, lang = detect_script(text)
        return DetectResult(language=lang, method="script_heuristic", script=script, provider=self.name)

    def speech_to_text(self, audio: bytes, *, language: str, audio_format: str = "wav") -> TranscribeResult:
        raise LanguageServiceUnavailable(f"Speech recognition unavailable: {self.reason}")

    def translate(self, text: str, *, source_language: str, target_language: str) -> TranslateResult:
        if source_language == target_language:
            return TranslateResult(
                text=text,
                original_text=text,
                source_language=source_language,
                target_language=target_language,
                provider=self.name,
                translated=False,
            )
        raise LanguageServiceUnavailable(f"Translation unavailable: {self.reason}")

    def text_to_speech(self, text: str, *, language: str) -> SpeakResult:
        raise LanguageServiceUnavailable(f"Text-to-speech unavailable: {self.reason}")

    def transliterate(self, text: str, *, source_language: str, target_language: str) -> TransliterateResult:
        raise LanguageServiceUnavailable(f"Transliteration unavailable: {self.reason}")
