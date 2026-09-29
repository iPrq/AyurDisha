"""Language / voice router — BHASHINI when configured; honest 503s when a capability is unavailable.

Provider credentials never leave the server.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from config import get_settings
from graph.formulation.telemetry import log_event, timed
from language.base import (
    DetectResult,
    LanguageCapabilities,
    LanguageServiceUnavailable,
    SpeakResult,
    TranscribeResult,
    TranslateResult,
)
from language.factory import get_language_provider

router = APIRouter(prefix="/api/v1/language", tags=["language"])

AUDIO_TYPES = {"audio/wav", "audio/x-wav", "audio/wave", "audio/flac", "audio/mpeg", "application/octet-stream"}


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    source_language: str = Field(min_length=2, max_length=8)
    target_language: str = Field(min_length=2, max_length=8)


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1500)
    language: str = Field(min_length=2, max_length=8)


class TranscribeResponse(TranscribeResult):
    detected: DetectResult | None = None


def _unavailable(exc: LanguageServiceUnavailable) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))


@router.get("/capabilities", response_model=LanguageCapabilities)
def capabilities() -> LanguageCapabilities:
    return get_language_provider().capabilities()


@router.post("/detect", response_model=DetectResult)
def detect(request: TextRequest) -> DetectResult:
    provider = get_language_provider()
    result = provider.detect_language(request.text)
    log_event("language_detect", provider=provider.name, language=result.language, language_method=result.method)
    return result


@router.post("/transcribe", response_model=TranscribeResponse)
def transcribe(
    file: UploadFile = File(...),
    language: str = Form("auto"),
) -> TranscribeResponse:
    settings = get_settings()
    provider = get_language_provider()
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Send WAV, FLAC or MP3 audio.")
    data = file.file.read(settings.audio_max_bytes + 1)
    if len(data) > settings.audio_max_bytes:
        raise HTTPException(status_code=413, detail="Audio clip is too long.")
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio.")
    source = language if language not in ("", "auto") else settings.bhashini_default_source_language
    audio_format = {"audio/flac": "flac", "audio/mpeg": "mp3"}.get(content_type, "wav")
    with timed("language_transcribe", provider=provider.name, language=source) as log:
        try:
            result = provider.speech_to_text(data, language=source, audio_format=audio_format)
        except LanguageServiceUnavailable as exc:
            log["fallback"] = "unavailable"
            raise _unavailable(exc) from exc
        detected = provider.detect_language(result.text)
        log["language_method"] = detected.method
        return TranscribeResponse(**result.model_dump(), detected=detected)


@router.post("/translate", response_model=TranslateResult)
def translate(request: TranslateRequest) -> TranslateResult:
    provider = get_language_provider()
    with timed("language_translate", provider=provider.name, language=request.source_language) as log:
        try:
            return provider.translate(
                request.text, source_language=request.source_language, target_language=request.target_language
            )
        except LanguageServiceUnavailable as exc:
            log["fallback"] = "unavailable"
            raise _unavailable(exc) from exc


@router.post("/speak", response_model=SpeakResult)
def speak(request: SpeakRequest) -> SpeakResult:
    provider = get_language_provider()
    with timed("language_speak", provider=provider.name, language=request.language) as log:
        try:
            return provider.text_to_speech(request.text, language=request.language)
        except LanguageServiceUnavailable as exc:
            log["fallback"] = "unavailable"
            raise _unavailable(exc) from exc
