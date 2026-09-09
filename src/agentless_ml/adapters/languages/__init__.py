"""Language-specific repository representations."""

from agentless_ml.adapters.languages.base import LanguageAdapter
from agentless_ml.adapters.languages.go import GoAdapter
from agentless_ml.adapters.languages.javascript import (
    JavaScriptAdapter,
    TypeScriptAdapter,
)
from agentless_ml.adapters.languages.python import PythonAdapter
from agentless_ml.adapters.languages.rust import RustAdapter


def get_language_adapter(language: str) -> LanguageAdapter:
    adapters = {
        "python": PythonAdapter,
        "go": GoAdapter,
        "javascript": JavaScriptAdapter,
        "typescript": TypeScriptAdapter,
        "rust": RustAdapter,
    }
    try:
        return adapters[language.casefold()]()
    except KeyError:
        raise ValueError(f"unsupported workflow language: {language}") from None


__all__ = [
    "GoAdapter",
    "JavaScriptAdapter",
    "LanguageAdapter",
    "PythonAdapter",
    "RustAdapter",
    "TypeScriptAdapter",
    "get_language_adapter",
]
