"""BHASHINI (ULCA pipeline) language provider.

Service IDs are discovered from the ULCA pipeline-config API for the configured credentials —
never hard-coded. Every call falls back honestly (raises ``LanguageServiceUnavailable``) on failure.
"""

from __future__ import annotations

import base64
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from config import Settings
from language.base import (
    DetectResult,
    LanguageCapabilities,
    LanguageInfo,
    LanguageServiceUnavailable,
    SpeakResult,
    TranscribeResult,
    TranslateResult,
    TransliterateResult,
    language_name,
)
from language.fallback import detect_script
from language.glossary import protect, restore

logger = logging.getLogger(__name__)

TASKS = ("asr", "translation", "tts", "transliteration", "txt-lang-detection")
DISCOVERY_TTL_SECONDS = 3600


@dataclass
class _Discovery:
    callback_url: str
    auth_name: str
    auth_value: str
    services: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    fetched_at: float = field(default_factory=time.monotonic)


class BhashiniLanguageProvider:
    name = "bhashini"

    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport
        self._lock = threading.Lock()
        self._discovery: _Discovery | None = None

    # -- HTTP ---------------------------------------------------------------

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.settings.bhashini_timeout, transport=self._transport)

    def _config_call(self, task: str, language: dict[str, str] | None = None) -> dict[str, Any]:
        cfg = self.settings
        task_body: dict[str, Any] = {"taskType": task}
        if language:
            task_body["config"] = {"language": language}
        body: dict[str, Any] = {"pipelineTasks": [task_body]}
        if cfg.bhashini_pipeline_id:
            body["pipelineRequestConfig"] = {"pipelineId": cfg.bhashini_pipeline_id}
        headers = {
            "userID": cfg.bhashini_user_id or "",
            "ulcaApiKey": cfg.bhashini_api_key or "",
            "Content-Type": "application/json",
        }
        with self._client() as client:
            resp = client.post(cfg.bhashini_base_url, json=body, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def discover(self, *, force: bool = False) -> _Discovery:
        with self._lock:
            d = self._discovery
            if d and not force and time.monotonic() - d.fetched_at < DISCOVERY_TTL_SECONDS:
                return d
            callback: tuple[str, str, str] | None = None
            services: dict[str, list[dict[str, Any]]] = {}
            errors: dict[str, str] = {}
            for task in TASKS:
                try:
                    data = self._config_call(task)
                except Exception as exc:  # noqa: BLE001 - per-task discovery failure is recorded
                    errors[task] = type(exc).__name__
                    continue
                endpoint = data.get("pipelineInferenceAPIEndPoint") or {}
                key = endpoint.get("inferenceApiKey") or {}
                if endpoint.get("callbackUrl") and key.get("value") and callback is None:
                    callback = (endpoint["callbackUrl"], key.get("name") or "Authorization", key["value"])
                for block in data.get("pipelineResponseConfig") or []:
                    if block.get("taskType") == task:
                        services.setdefault(task, []).extend(block.get("config") or [])
            if callback is None:
                raise LanguageServiceUnavailable(
                    "BHASHINI discovery failed: no inference endpoint returned "
                    f"(errors: {', '.join(f'{k}={v}' for k, v in errors.items()) or 'none'})."
                )
            self._discovery = _Discovery(
                callback_url=callback[0],
                auth_name=callback[1],
                auth_value=callback[2],
                services=services,
                errors=errors,
            )
            logger.info(
                "BHASHINI discovery ok tasks=%s",
                {t: len(v) for t, v in services.items()},
            )
            return self._discovery

    def _service_id(self, task: str, source: str, target: str | None = None) -> str:
        override = {
            "asr": self.settings.bhashini_asr_service,
            "translation": self.settings.bhashini_translation_service,
            "tts": self.settings.bhashini_tts_service,
        }.get(task)
        if override:
            return override
        d = self.discover()
        for entry in d.services.get(task, []):
            lang = entry.get("language") or {}
            if lang.get("sourceLanguage") != source:
                continue
            if target is not None and lang.get("targetLanguage") != target:
                continue
            if entry.get("serviceId"):
                return entry["serviceId"]
        pair = f"{source}->{target}" if target else source
        raise LanguageServiceUnavailable(f"BHASHINI has no {task} service for {pair}.")

    def _compute(self, task_config: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
        d = self.discover()
        body = {"pipelineTasks": [task_config], "inputData": input_data}
        try:
            with self._client() as client:
                resp = client.post(
                    d.callback_url,
                    json=body,
                    headers={d.auth_name: d.auth_value, "Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise LanguageServiceUnavailable(f"BHASHINI {task_config['taskType']} failed: {type(exc).__name__}") from exc
        responses = data.get("pipelineResponse") or []
        if not responses:
            raise LanguageServiceUnavailable(f"BHASHINI {task_config['taskType']} returned no output.")
        return responses[0]

    # -- Provider API -------------------------------------------------------

    def capabilities(self) -> LanguageCapabilities:
        try:
            d = self.discover()
        except LanguageServiceUnavailable as exc:
            return LanguageCapabilities(provider=self.name, configured=True, notes=[str(exc)])
        codes: set[str] = {"en"}
        for task in ("asr", "translation"):
            for entry in d.services.get(task, []):
                lang = entry.get("language") or {}
                if lang.get("sourceLanguage"):
                    codes.add(lang["sourceLanguage"])
        return LanguageCapabilities(
            provider=self.name,
            configured=True,
            asr=bool(d.services.get("asr")),
            translation=bool(d.services.get("translation")),
            tts=bool(d.services.get("tts")),
            transliteration=bool(d.services.get("transliteration")),
            detection="service" if d.services.get("txt-lang-detection") else "heuristic",
            languages=[LanguageInfo(code=c, name=language_name(c)) for c in sorted(codes)],
            notes=[f"Discovery unavailable for: {', '.join(d.errors)}"] if d.errors else [],
        )

    def detect_language(self, text: str) -> DetectResult:
        script, heuristic_lang = detect_script(text)
        try:
            d = self.discover()
            entries = d.services.get("txt-lang-detection") or []
            if entries and entries[0].get("serviceId"):
                out = self._compute(
                    {"taskType": "txt-lang-detection", "config": {"serviceId": entries[0]["serviceId"]}},
                    {"input": [{"source": text}]},
                )
                preds = ((out.get("output") or [{}])[0].get("langPrediction")) or []
                if preds and preds[0].get("langCode"):
                    return DetectResult(
                        language=preds[0]["langCode"], method="service", script=script, provider=self.name
                    )
        except LanguageServiceUnavailable:
            logger.info("BHASHINI language detection unavailable; using script heuristic")
        return DetectResult(language=heuristic_lang, method="script_heuristic", script=script, provider=self.name)

    def speech_to_text(self, audio: bytes, *, language: str, audio_format: str = "wav") -> TranscribeResult:
        service = self._service_id("asr", language)
        out = self._compute(
            {
                "taskType": "asr",
                "config": {
                    "language": {"sourceLanguage": language},
                    "serviceId": service,
                    "audioFormat": audio_format,
                    "samplingRate": 16000,
                },
            },
            {"audio": [{"audioContent": base64.b64encode(audio).decode("ascii")}]},
        )
        text = ((out.get("output") or [{}])[0].get("source") or "").strip()
        if not text:
            raise LanguageServiceUnavailable("BHASHINI ASR returned an empty transcript.")
        return TranscribeResult(text=text, language=language, provider=self.name)

    def translate(self, text: str, *, source_language: str, target_language: str) -> TranslateResult:
        if source_language == target_language:
            return TranslateResult(
                text=text, original_text=text, source_language=source_language,
                target_language=target_language, provider=self.name, translated=False,
            )
        masked, mapping = protect(text) if source_language == "en" else (text, {})
        service = self._service_id("translation", source_language, target_language)
        out = self._compute(
            {
                "taskType": "translation",
                "config": {
                    "language": {"sourceLanguage": source_language, "targetLanguage": target_language},
                    "serviceId": service,
                },
            },
            {"input": [{"source": masked}]},
        )
        translated = ((out.get("output") or [{}])[0].get("target") or "").strip()
        if not translated:
            raise LanguageServiceUnavailable("BHASHINI translation returned empty output.")
        restored, lost = restore(translated, mapping)
        if lost:
            # Protected terms were mangled — append them so canonical names are not lost.
            restored = f"{restored} ({', '.join(lost)})"
        return TranslateResult(
            text=restored,
            original_text=text,
            source_language=source_language,
            target_language=target_language,
            provider=self.name,
            protected_terms=list(mapping.values()),
        )

    def text_to_speech(self, text: str, *, language: str) -> SpeakResult:
        service = self._service_id("tts", language)
        out = self._compute(
            {
                "taskType": "tts",
                "config": {
                    "language": {"sourceLanguage": language},
                    "serviceId": service,
                    "gender": "female",
                    "samplingRate": 8000,
                },
            },
            {"input": [{"source": text}]},
        )
        audio = ((out.get("audio") or [{}])[0].get("audioContent")) or ""
        if not audio:
            raise LanguageServiceUnavailable("BHASHINI TTS returned no audio.")
        return SpeakResult(audio_base64=audio, audio_format="wav", language=language, provider=self.name)

    def transliterate(self, text: str, *, source_language: str, target_language: str) -> TransliterateResult:
        d = self.discover()
        entry = next(
            (
                e for e in d.services.get("transliteration", [])
                if (e.get("language") or {}).get("sourceLanguage") == source_language
                and (e.get("language") or {}).get("targetLanguage") == target_language
            ),
            None,
        )
        if entry is None:
            raise LanguageServiceUnavailable(
                f"BHASHINI has no transliteration service for {source_language}->{target_language}."
            )
        out = self._compute(
            {
                "taskType": "transliteration",
                "config": {
                    "language": {"sourceLanguage": source_language, "targetLanguage": target_language},
                    "serviceId": entry["serviceId"],
                },
            },
            {"input": [{"source": text}]},
        )
        target = (out.get("output") or [{}])[0].get("target")
        if isinstance(target, list):
            target = target[0] if target else ""
        return TransliterateResult(
            text=str(target or ""), source_language=source_language,
            target_language=target_language, provider=self.name,
        )
