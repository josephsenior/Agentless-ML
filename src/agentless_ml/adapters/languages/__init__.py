"""Repository representations for each workflow language.

Go, JavaScript, TypeScript and Rust are descriptions (``LanguageSpec``) read by
one generic engine; none has its own adapter implementation. Python keeps a
dedicated implementation because it is held byte-identical to published
Agentless v1.5.0 (see ``docs/python-parity.md``).
"""

from functools import lru_cache

from agentless_ml.adapters.languages.base import LanguageAdapter
from agentless_ml.adapters.languages.go import GO
from agentless_ml.adapters.languages.javascript import JAVASCRIPT, TYPESCRIPT
from agentless_ml.adapters.languages.python import PythonAdapter
from agentless_ml.adapters.languages.rust import RUST
from agentless_ml.structure.engine import TreeSitterLanguage

_DESCRIBED = {spec.language: spec for spec in (GO, JAVASCRIPT, TYPESCRIPT, RUST)}


@lru_cache(maxsize=None)
def get_language_adapter(language: str) -> LanguageAdapter:
    key = language.casefold()
    if key == "python":
        return PythonAdapter()
    if key in _DESCRIBED:
        return TreeSitterLanguage(_DESCRIBED[key])
    raise ValueError(f"unsupported workflow language: {language}")


def source_adapter(path: str) -> LanguageAdapter | None:
    """Resolve a supported source path independently of benchmark metadata."""
    # TypeScript also accepts JavaScript paths. Prefer JavaScript for those files.
    for language in ("python", *_DESCRIBED):
        adapter = get_language_adapter(language)
        if adapter.is_source_path(path):
            return adapter
    return None


__all__ = [
    "LanguageAdapter",
    "PythonAdapter",
    "TreeSitterLanguage",
    "get_language_adapter",
]
