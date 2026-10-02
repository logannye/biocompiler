"""Public errors for intent authoring and compilation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class _SourceLocation(Protocol):
    @property
    def file(self) -> str: ...

    @property
    def line(self) -> int: ...


class BiocompilerError(Exception):
    """Base biocompiler error."""


class DefinitionError(BiocompilerError, ValueError):
    """An invalid or conflicting definition."""


class ScopeError(BiocompilerError, ValueError):
    """Incompatible therapies or cell roles."""


class TypeMismatchError(BiocompilerError, TypeError):
    """Incompatible semantic types or dimensions."""


class SerializationError(BiocompilerError, ValueError):
    """An invalid serialized intent or behavior document."""


class CompilationUnavailableError(BiocompilerError, NotImplementedError):
    """Molecular realization is not implemented."""

    def __init__(self, message: str, *, diagnostics: Iterable[object] = ()) -> None:
        self.diagnostics = tuple(diagnostics)
        super().__init__(message)


class BehaviorError(BiocompilerError, ValueError):
    """An invalid or unresolved abstract behavior specification."""


class LoweringError(BehaviorError):
    """An intent graph cannot be lowered under the selected execution profile."""

    def __init__(self, message: str, *, diagnostics: Iterable[object] = ()) -> None:
        self.diagnostics = tuple(diagnostics)
        super().__init__(message)


class UnsupportedBehaviorError(LoweringError):
    """A source construct needs an execution profile not implemented yet."""

    def __init__(self, message: str, *, node_id: str | None = None,
                 source: _SourceLocation | None = None) -> None:
        self.node_id = node_id
        self.source = source
        location = f" at {source.file}:{source.line}" if source is not None else ""
        identity = f" [{node_id}]" if node_id is not None else ""
        super().__init__(f"{message}{identity}{location}")


class LoweringVerificationError(BehaviorError):
    """The emitted behavior fails exact source-preservation checks."""


class EvaluationError(BehaviorError):
    """Invalid histories or undefined execution in the abstract evaluator."""


class StateConflictError(EvaluationError):
    """Concurrent assignments disagree on the same cell-local state."""


class NonConvergenceError(EvaluationError):
    """Same-time state propagation did not stabilize within the step bound."""
