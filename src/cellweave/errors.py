"""Public errors for intent authoring and compilation."""


class CellWeaveError(Exception):
    """Base CellWeave error."""


class DefinitionError(CellWeaveError, ValueError):
    """An invalid or conflicting definition."""


class ScopeError(CellWeaveError, ValueError):
    """Incompatible therapies or cell roles."""


class TypeMismatchError(CellWeaveError, TypeError):
    """Incompatible semantic types or dimensions."""


class SerializationError(CellWeaveError, ValueError):
    """An invalid serialized intent or behavior document."""


class CompilationUnavailableError(CellWeaveError, NotImplementedError):
    """Molecular realization is not implemented."""

    def __init__(self, message, *, diagnostics=()):
        self.diagnostics = tuple(diagnostics)
        super().__init__(message)


class BehaviorError(CellWeaveError, ValueError):
    """An invalid or unresolved abstract behavior specification."""


class LoweringError(BehaviorError):
    """An intent graph cannot be lowered under the selected execution profile."""

    def __init__(self, message, *, diagnostics=()):
        self.diagnostics = tuple(diagnostics)
        super().__init__(message)


class UnsupportedBehaviorError(LoweringError):
    """A source construct needs an execution profile not implemented yet."""

    def __init__(self, message, *, node_id=None, source=None):
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
