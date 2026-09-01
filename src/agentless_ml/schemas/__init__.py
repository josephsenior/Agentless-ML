"""Public, provider- and benchmark-independent schema surface."""

from agentless_ml.schemas.prediction import (
    FinalPrediction,
    PatchCandidate,
    ValidationResult,
    ValidationStatus,
)
from agentless_ml.schemas.run import RunRecord
from agentless_ml.schemas.structure import FileNode, SymbolNode
from agentless_ml.schemas.task import Benchmark, TaskSpec

__all__ = [
    "Benchmark",
    "FileNode",
    "FinalPrediction",
    "PatchCandidate",
    "RunRecord",
    "SymbolNode",
    "TaskSpec",
    "ValidationResult",
    "ValidationStatus",
]
