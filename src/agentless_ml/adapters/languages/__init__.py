"""Repository representations for each workflow language.

Go, JavaScript, TypeScript and Rust are descriptions (``LanguageSpec``) read by
one generic engine; none has its own adapter implementation. Python keeps a
dedicated implementation because it is held byte-identical to published
Agentless v1.5.0 (see ``docs/python-parity.md``).
"""

from agentless_ml.adapters.languages.base import LanguageAdapter
from agentless_ml.adapters.languages.go import GO
from agentless_ml.adapters.languages.javascript import JAVASCRIPT, TYPESCRIPT
from agentless_ml.adapters.languages.python import PythonAdapter
from agentless_ml.adapters.languages.rust import RUST
from agentless_ml.structure.engine import TreeSitterLanguage

_DESCRIBED = {spec.language: spec for spec in (GO, JAVASCRIPT, TYPESCRIPT, RUST)}


def get_language_adapter(language: str) -> LanguageAdapter:
    key = language.casefold()
    if key == "python":
        return PythonAdapter()
    if key in _DESCRIBED:
        return TreeSitterLanguage(_DESCRIBED[key])
    raise ValueError(f"unsupported workflow language: {language}")


__all__ = [
    "LanguageAdapter",
    "PythonAdapter",
    "TreeSitterLanguage",
    "get_language_adapter",
]
