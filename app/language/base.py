"""Language / voice provider abstraction (BHASHINI or fallback)."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field


class LanguageServiceUnavailable(RuntimeError):
    """The requested language capability is not available from the configured provider."""


class LanguageInfo(BaseModel):
    code: str
    name: str


class LanguageCapabilities(BaseModel):
    provider: str
    configured: bool
    asr: bool = False
    translation: bool = False
    tts: bool = False
    transliteration: bool = False
    detection: Literal["service", "heuristic"] = "heuristic"
    languages: list[LanguageInfo] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DetectResult(BaseModel):
    language: str
    method: Literal["service", "script_heuristic"]
    script: str | None = None
    provider: str


class TranscribeResult(BaseModel):
    text: str
    language: str
    provider: str


class TranslateResult(BaseModel):
    text: str
    original_text: str
    source_language: str
    target_language: str
    provider: str
    translated: bool = True
    protected_terms: list[str] = Field(default_factory=list)
    fallback_reason: str | None = None


class SpeakResult(BaseModel):
    audio_base64: str
    audio_format: str
    language: str
    provider: str


class TransliterateResult(BaseModel):
    text: str
    source_language: str
    target_language: str
    provider: str


class LanguageProvider(Protocol):
    name: str

    def capabilities(self) -> LanguageCapabilities: ...

    def detect_language(self, text: str) -> DetectResult: ...

    def speech_to_text(self, audio: bytes, *, language: str, audio_format: str = "wav") -> TranscribeResult: ...

    def translate(self, text: str, *, source_language: str, target_language: str) -> TranslateResult: ...

    def text_to_speech(self, text: str, *, language: str) -> SpeakResult: ...

    def transliterate(self, text: str, *, source_language: str, target_language: str) -> TransliterateResult: ...


LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "kn": "Kannada",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "or": "Odia",
    "as": "Assamese",
    "ur": "Urdu",
    "sa": "Sanskrit",
    "ne": "Nepali",
    "kok": "Konkani",
    "mai": "Maithili",
    "doi": "Dogri",
    "sd": "Sindhi",
    "ks": "Kashmiri",
    "brx": "Bodo",
    "mni": "Manipuri",
    "sat": "Santali",
}


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)
