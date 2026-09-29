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
    """An invalid intent document."""


class CompilationUnavailableError(CellWeaveError, NotImplementedError):
    """Molecular realization is not implemented."""
