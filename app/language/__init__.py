"""Optional multilingual / voice boundary layer (BHASHINI with graceful fallback)."""

from language.base import LanguageProvider, LanguageServiceUnavailable
from language.factory import get_language_provider

__all__ = ["LanguageProvider", "LanguageServiceUnavailable", "get_language_provider"]
