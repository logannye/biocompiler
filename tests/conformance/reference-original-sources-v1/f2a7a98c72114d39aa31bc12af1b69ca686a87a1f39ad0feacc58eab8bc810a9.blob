"""Named Python recognition functions with inspectable source correspondence."""

from __future__ import annotations

import functools
import inspect
import math
from typing import Any, Callable

from biocompiler.errors import DefinitionError, ScopeError, TypeMismatchError
from biocompiler.frontend.expressions import Condition
from biocompiler.semantics.types import BOOLEAN


class Signature:
    """A reusable recognition definition evaluated against its supplied scopes.

    The function builds an expression at authoring time. Each call adds a named
    wrapper node retaining the definition identity and the actual bound inputs.
    """

    def __init__(self, function: Callable[..., Condition], *, name: str | None = None):
        if not callable(function):
            raise TypeMismatchError(
                "A signature must wrap a callable returning a Condition"
            )
        self.function = function
        self.name = function.__name__ if name is None else name
        if not isinstance(self.name, str) or not self.name.strip():
            raise DefinitionError("A signature name must be a nonempty string")
        functools.update_wrapper(self, function)
        self._parameters = inspect.signature(function)
        self._definition: dict[str, Any] = {
            "name": self.name,
            "module": function.__module__,
            "qualname": function.__qualname__,
        }

    def __call__(self, *args: Any, **kwargs: Any) -> Condition:
        bound = self._parameters.bind(*args, **kwargs)
        bound.apply_defaults()
        result = self.function(*args, **kwargs)
        if not isinstance(result, Condition):
            raise TypeMismatchError(f"Signature {self.name!r} must return a Condition")
        inputs = [result.node_id]
        graph, role = result._graph, result.role

        def binding(value: Any) -> Any:
            if hasattr(value, "_graph") and hasattr(value, "node_id"):
                if value._graph is not graph:
                    raise ScopeError(
                        "A signature cannot bind objects from different therapies"
                    )
                if value.role is not None and value.role != role:
                    raise ScopeError(
                        "A signature must return an expression bound to its supplied cell role"
                    )
                inputs.append(value.node_id)
                return {"input": len(inputs) - 1}
            if value is None or isinstance(value, (str, bool, int)):
                return {"literal": value}
            if isinstance(value, float) and math.isfinite(value):
                return {"literal": value}
            if isinstance(value, (tuple, list)):
                return [binding(item) for item in value]
            if isinstance(value, dict) and all(isinstance(key, str) for key in value):
                return {key: binding(item) for key, item in value.items()}
            if hasattr(value, "to_dict") and callable(value.to_dict):
                return {"literal": value.to_dict()}
            raise TypeMismatchError(
                "Signature arguments must be symbolic handles or serializable design values"
            )

        bindings = {name: binding(value) for name, value in bound.arguments.items()}
        node = graph.add(
            "signature",
            inputs=tuple(inputs),
            attributes={"definition": self._definition, "bindings": bindings},
            data_type=BOOLEAN,
            role=role,
            intern=True,
        )
        return Condition(graph, node, BOOLEAN, role)


def signature(
    function: Callable[..., Condition] | None = None, *, name: str | None = None
):
    """Decorate a recognition function, optionally supplying its public name."""
    if function is None:
        return lambda wrapped: Signature(wrapped, name=name)
    return Signature(function, name=name)
