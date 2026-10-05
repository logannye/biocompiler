"""Symbolic operators. None of these evaluates therapeutic behavior."""
from typing import Literal
from .model import EVENT, INTEGER, TEXT, TRUTH, DefinitionRef, Expr, Quantity, Ref, TypeSpec
from .values import compatible


def literal(value: str | int | bool | Quantity) -> Expr:
    if isinstance(value, Quantity):
        return Expr("literal", TypeSpec("quantity", value.unit), value=value)
    if type(value) is bool:
        return Expr("literal", TRUTH, value=value)
    if type(value) is int:
        return Expr("literal", INTEGER, value=value)
    if type(value) is str:
        return Expr("literal", TEXT, value=value)
    raise TypeError("Expected an exact, typed policy literal")


UNKNOWN = Expr("literal", TRUTH, value="unknown")
TRUE = literal(True)
FALSE = literal(False)


def _truth(conditions: tuple[Expr, ...], minimum: int = 1) -> None:
    if len(conditions) < minimum or any(not isinstance(x, Expr) or x.value_type != TRUTH for x in conditions):
        raise TypeError("Expected symbolic truth conditions; events are separate")


def all_of(*conditions: Expr) -> Expr:
    _truth(conditions)
    return Expr("all", TRUTH, conditions)


def any_of(*conditions: Expr) -> Expr:
    _truth(conditions)
    return Expr("any", TRUTH, conditions)


def not_(condition: Expr) -> Expr:
    _truth((condition,))
    return Expr("not", TRUTH, (condition,))


def compare(left: Expr, op: Literal["eq", "ne", "lt", "le", "gt", "ge"], right: Expr | Quantity | int | str | bool) -> Expr:
    rhs = right if isinstance(right, Expr) else literal(right)
    if not compatible(left.value_type, rhs.value_type):
        raise TypeError("Comparison requires matching value types, quantity kinds and reference scopes")
    return Expr(op, TRUTH, (left, rhs))


def arithmetic(left: Expr, op: Literal["add", "subtract", "multiply", "divide"], right: Expr, *, result: TypeSpec | None = None) -> Expr:
    if left.value_type.kind not in ("integer", "quantity") or right.value_type.kind not in ("integer", "quantity"):
        raise TypeError("Arithmetic requires numeric expressions")
    if op in ("add", "subtract"):
        if not compatible(left.value_type, right.value_type):
            raise TypeError("Addition and subtraction require compatible quantities")
        result = left.value_type
    elif result is None:
        raise TypeError("Multiplication/division require an explicit resulting quantity type")
    return Expr(op, result, (left, right))


def exists(domain: Ref, predicate: Expr, *, binding: Ref) -> Expr:
    _truth((predicate,))
    return Expr("exists", TRUTH, (predicate,), scope=domain, binding=binding)


def forall(domain: Ref, predicate: Expr, *, binding: Ref) -> Expr:
    _truth((predicate,))
    return Expr("forall", TRUTH, (predicate,), scope=domain, binding=binding)


def count(domain: Ref, predicate: Expr, *, binding: Ref) -> Expr:
    _truth((predicate,))
    return Expr("count", INTEGER, (predicate,), scope=domain, binding=binding)


def entity(subject: Ref, *, entity_kind: str = "cell") -> Expr:
    return Expr("literal", TypeSpec("entity", entity_kind=entity_kind), ref=subject, scope=subject)


def distinct(*subjects: Expr) -> Expr:
    if len(subjects) < 2 or any(x.value_type.kind != "entity" for x in subjects):
        raise TypeError("distinct requires at least two entity expressions")
    return Expr("distinct", TRUTH, subjects)


def call(contract: DefinitionRef, *arguments: Expr, result: TypeSpec) -> Expr:
    return Expr("call", result, arguments, contract=contract)


def rising(condition: Expr) -> Expr:
    _truth((condition,))
    return Expr("rising", EVENT, (condition,))
