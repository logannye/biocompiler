"""Freeze CPython numeric results for the bounded OCaml execution primitives.

No native process runs here. Literal witnesses supplement deterministic oracle
cases; numeric compatibility alone establishes no program or biological claim.
"""

from __future__ import annotations

import argparse
import json
import math
import operator
from pathlib import Path
import random
import struct

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/runtime-numbers-v1.json"
SCHEMA = "biocompiler.runtime_numbers_conformance.v1"
OPERATIONS = {"add": operator.add, "sub": operator.sub, "mul": operator.mul,
              "div": operator.truediv, "neg": operator.neg, "min": min, "max": max,
              "compare": lambda a, b: (a > b) - (a < b)}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def oracle(operation, operands):
    if not all(finite(value) for value in operands):
        return {"code": "evaluation_nonfinite"}
    try:
        if operation == "advance":
            result = operands[0] + operands[1]
        elif operation == "fsum":
            result = math.fsum(operands)
        else:
            result = OPERATIONS[operation](*operands)
    except ZeroDivisionError:
        return {"code": "evaluation_division_by_zero"}
    except OverflowError:
        return {"code": "evaluation_overflow"}
    if not finite(result):
        return {"code": "evaluation_overflow"}
    if operation == "advance" and (operands[1] <= 0 or result <= operands[0]):
        return {"code": "evaluation_nonadvancing_time"}
    return {"result": result, "canonical_json": canonical(result)}


def build():
    cases = []

    def add(identity, operation, operands, literal=None):
        expected = oracle(operation, operands)
        if literal is not None and canonical(expected) != canonical(literal):
            raise AssertionError(f"Independent numeric witness changed: {identity}: {expected}")
        cases.append(dict(id=identity, operation=operation, operands=operands,
                          authority="literal_and_cpython" if literal is not None else "cpython",
                          **expected))

    def result(value):
        return {"result": value, "canonical_json": canonical(value)}

    add("mixed_integer_above_binary64_exact_range", "compare", [2**53 + 1, float(2**53)], result(1))
    add("mixed_integer_below_negative_float", "compare", [-2**53 - 1, -float(2**53)], result(-1))
    add("int_true_division_retains_low_bit", "div", [2**53 + 1, 3], result(3002399751580331.0))
    add("zero_divided_by_negative_integer", "div", [0, -3], result(-0.0))
    add("float_zero_divided_by_negative_integer", "div", [0.0, -3], result(-0.0))
    add("negative_zero_times_integer", "mul", [-0.0, 3], result(-0.0))
    add("negative_zero_negation", "neg", [-0.0], result(0.0))
    add("equal_min_preserves_first_integer", "min", [0, -0.0], result(0))
    add("equal_max_preserves_first_float", "max", [-0.0, 0], result(-0.0))
    add("integer_arithmetic_stays_integer", "add", [2**53, 1], result(2**53 + 1))
    add("floating_arithmetic_rounds_to_even", "add", [float(2**53), 1], result(float(2**53)))
    add("timer_must_advance", "advance", [float(2**53), 1], {"code": "evaluation_nonadvancing_time"})
    add("integer_timer_advances", "advance", [2**53, 1], result(2**53 + 1))
    add("timer_duration_positive", "advance", [1, 0], {"code": "evaluation_nonadvancing_time"})
    add("integer_result_must_remain_finite", "add", [2**1023, 2**1023], {"code": "evaluation_overflow"})
    add("input_must_remain_finite", "compare", [2**1024, 1], {"code": "evaluation_nonfinite"})
    add("division_by_integer_zero", "div", [1, 0], {"code": "evaluation_division_by_zero"})
    add("division_by_negative_float_zero", "div", [1, -0.0], {"code": "evaluation_division_by_zero"})
    add("fsum_exact_cancellation", "fsum", [1e16, 1, -1e16], result(1.0))
    add("fsum_two_low_bits", "fsum", [2**53, 1, 1], result(9007199254740994.0))
    add("fsum_negative_zero", "fsum", [-0.0], result(0.0))
    add("fsum_empty", "fsum", [], result(0.0))
    maximum = float.fromhex("0x1.fffffffffffffp+1023")
    add("fsum_intermediate_overflow", "fsum", [maximum, maximum, -maximum], {"code": "evaluation_overflow"})
    add("fsum_cancellation_before_large_addition", "fsum", [maximum, -maximum, maximum], result(maximum))
    add("fsum_subnormal", "fsum", [5e-324, 5e-324, -5e-324], result(5e-324))
    add("fsum_tie_even", "fsum", [1.0, 2**-53], result(1.0))
    add("fsum_above_tie", "fsum", [1.0, 2**-53, 5e-324], result(1.0000000000000002))
    add("fsum_negative_above_tie", "fsum", [-1.0, -(2**-53), -5e-324], result(-1.0000000000000002))
    rng = random.Random(20261001)
    values = [0, -0.0, 1, -1, 2**53 - 1, 2**53 + 1, -(2**53 + 1),
              2**1023, -(2**1023), 5e-324, -5e-324, maximum, -maximum]
    while len(values) < 96:
        value = struct.unpack(">d", rng.getrandbits(64).to_bytes(8, "big"))[0]
        if math.isfinite(value):
            values.append(value)
    for index in range(240):
        operands = [rng.choice(values), rng.choice(values)]
        for operation in ("add", "sub", "mul", "div", "compare", "min", "max"):
            add(f"mixed_{index:03d}_{operation}", operation, operands)
    for index in range(120):
        left = rng.getrandbits(rng.randrange(1, 1024)) * rng.choice([-1, 1])
        right = (rng.getrandbits(rng.randrange(1, 1024)) or 1) * rng.choice([-1, 1])
        add(f"integer_ratio_{index:03d}", "div", [left, right])
    for index in range(120):
        operands = [rng.choice(values) for _ in range(rng.randrange(0, 24))]
        add(f"sum_{index:03d}", "fsum", operands)
    return dict(schema_version=SCHEMA,
                claim_scope="Finite scalar reference-execution arithmetic only; no semantic or empirical acceptance.",
                cases=cases)


def encoded(data):
    return (json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = encoded(build())
    if args.check:
        if CORPUS.read_bytes() != content:
            parser.error("Frozen runtime numeric corpus differs from current Python results")
    else:
        CORPUS.write_bytes(content)
    print(f"runtime numeric corpus: {len(build()['cases'])} cases")


if __name__ == "__main__":
    main()
