"""Exact inert source correspondence for the private owned-encoding extension.

The original whole-module AST is independently pinned from historical bytes.
Only the closed, separately pinned additions below may be removed. This proves
source correspondence, not cache correctness, execution or release acceptance.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

PATH = "src/biocompiler/core_client.py"
PATHS = frozenset({PATH})
HISTORICAL_SHA256 = "c8d65a42c1f92cbd75cb5edd176a9463657e03509be8ed487496d78b17be00fc"
HISTORICAL_AST_SHA256 = "22a7419ee9b1d2af88631b34c38f28c07bf884a1f4c562e849a48509166411d2"
CURRENT_SHA256 = "02cb76470d2170890937865a761d7c6a79b718f17a6ec30b94e0358234b69433"
MAX_SOURCE_BYTES = 131_072
MAX_AST_NODES = 25_000
ADDITIONS = (
    ('_OWNED_COPY_MAX_VISITS', '0944ae55400d1258326c4ded7779cfe24c0e1c5bc9781aa32ad318f7d170fff6'),
    ('_OWNED_COPY_MAX_CONTAINERS', 'efe5b79815c6164f7877c443593a58664570ccf929aad7da71f46d5bd09106b5'),
    ('_OWNED_COPY_MAX_DEPTH', 'e7fddfb43cb63d9dc3b85587084ca8468199009320934d0f66ea77c5667cf180'),
    ('_OWNED_ENCODING_MAX_ENROLLED', 'b1a7eda25c12f5cdf13ee56233d7cf0fce165525e2c9f83ea8ac8a941fa81e28'),
    ('_OWNED_ENCODING_MAX_VISITS', 'a4432f1585a060cab90da830a697358584a8da6a25f2e6513031ca103c6cc631'),
    ('_OWNED_ENCODING_MAX_ENTRIES', '4a36cd2e8a2c7bc080fef6a0c07188568b69e8912bbc6a560d7b02136446dc19'),
    ('_OWNED_ENCODING_MAX_BYTES', '401511c8f05c73a4e5c0b1e1ab91df2f42c0231694626ff3aed77ef7d6dbef0e'),
    ('_OwnedJson', '2c8f3cc0bd9d0dc660ad54864bcf684ce2eb137ecba81006a05a70b33ba8332a'),
    ('_owned_response_eligible', '290041040c981a82dc3052e535267ed34cb63164e62e890b3a3146a71a8a8f4c'),
    ('_CopyFrame', 'f8f35e652b52071dd27a1de7d0b9b5c957be0b38924dcddc7e552a79aed4de97'),
    ('_try_owned_json_copy', '3df37a8f1cd08854c82220af70371cedc9e5c444e3bb34f4476f1124f609881f'),
    ('_OwnedEncodingEntry', 'd1b418f69ff62564767948fbbd0a079cad8f90035136130961e8bb5219ef824b'),
    ('_OwnedEncoding', '5da6cc51ebf8db0d1fd5357ab9f7d7b687e61deb16dadfdf1eb86e4ad18f433e'),
    ('_OWNED_ENCODING', '0a85fd36d3b622e82eab7b77afabf6d376d88c39abe6d2e782630e347a42780a'),
    ('_owned_encoding_scope', '4a49d784f1cf8a1e8bb771ce4bbdd9b906270072629dfdc9e98aa7b10b8a8d1a'),
)
ENCODER_ADDITIONS = (
    (1, '62f09b0bad6639f6d6dc8f95a6b11de14239a302d43479c8a4d4853739be719b'),
    (2, 'b77594ea7680ebcf87e23dba77e4c57bb5a85e206ad2de803c0ea3f60a9b59e5'),
    (3, 'bc9c88cce5fc4201b6ac7e29d499608a267312b9535d5fadf25624c1a426b7b2'),
    (7, 'aa268e9c8670287e602b653d31fc7907f7ba5a7fb395ef579369b8d46c6c9a59'),
    (8, 'b49f755e44ec4fb60cacdfe4a4a10425f99c661017c2f25c23b1bd979effdd60'),
    (9, 'b6d26ee84ac017cadc813b8e7247517520d7d2b59334be7791dd5fddbd113433'),
)


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def structure(node):
    """Preserve every AST field across 3.11/3.14, except absent empty type_params."""
    if isinstance(node, ast.AST):
        return [type(node).__name__, [[name, structure(value)] for name, value in ast.iter_fields(node)
                if not (name == "type_params" and value == [])]]
    if isinstance(node, list):
        return [structure(value) for value in node]
    if isinstance(node, bytes):
        return {"bytes_hex": node.hex()}
    if node is Ellipsis:
        return {"singleton": "Ellipsis"}
    return node


def fingerprint(node):
    return sha(json.dumps(structure(node), ensure_ascii=True, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode())


def parsed(raw):
    require(type(raw) is bytes and len(raw) <= MAX_SOURCE_BYTES, "Encoding source type/size differs")
    try:
        result = ast.parse(raw.decode("utf-8"), filename=PATH, type_comments=True)
    except (SyntaxError, UnicodeError, RecursionError) as error:
        raise ValueError("Invalid encoding source AST") from error
    require(sum(1 for _ in ast.walk(result)) <= MAX_AST_NODES, "Encoding source AST exceeds bound")
    return result


def one_function(module, name):
    nodes = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(nodes) == 1, "Encoding source function census differs: " + name)
    return nodes[0]


def statement(source):
    return ast.parse(source, type_comments=True).body[0]


def strip_imports(module):
    added = tuple(statement(text) for text in (
        "from collections import deque", "from contextlib import contextmanager",
        "from contextvars import ContextVar"))
    require([structure(node) for node in module.body[2:5]] == [structure(node) for node in added],
            "Encoding imports or their placement differ")
    del module.body[2:5]
    imports = [node for node in module.body if isinstance(node, ast.ImportFrom) and node.module == "threading"]
    require(len(imports) == 1 and structure(imports[0]) == structure(statement("from threading import get_ident")),
            "Encoding threading import differs")
    index = module.body.index(imports[0])
    require(index > 0 and index + 1 < len(module.body)
            and structure(module.body[index - 1]) == structure(statement("import subprocess"))
            and structure(module.body[index + 1]) == structure(statement("import time")),
            "Encoding threading import placement differs")
    module.body.pop(index)
    for name, before, after in (
        ("dataclasses", "from dataclasses import dataclass", "from dataclasses import dataclass, field"),
        ("typing", "from typing import BinaryIO, Callable, Literal, TypeAlias, cast",
         "from typing import BinaryIO, Callable, Iterator, Literal, TypeAlias, cast"),
    ):
        imports = [node for node in module.body if isinstance(node, ast.ImportFrom) and node.module == name]
        require(len(imports) == 1 and structure(imports[0]) == structure(statement(after)),
                "Encoding extended import differs: " + name)
        module.body[module.body.index(imports[0])] = statement(before)


def verify_current(current, historical_sha256):
    """Verify exact additions, then restore and compare the complete original AST."""
    require(type(current) is bytes and len(current) <= MAX_SOURCE_BYTES, "Encoding source type/size differs")
    require(historical_sha256 == HISTORICAL_SHA256, "Encoding historical byte identity differs")
    require(sha(current) == CURRENT_SHA256, "Encoding current byte identity differs")
    module = parsed(current)
    strip_imports(module)
    validate = one_function(module, "validate_json")
    encoder = one_function(module, "encode_json")
    first, last = module.body.index(validate) + 1, module.body.index(encoder)
    additions = module.body[first:last]
    require(len(additions) == len(ADDITIONS), "Encoding addition census or placement differs")
    for node, (name, expected) in zip(additions, ADDITIONS):
        actual_name = getattr(node, "name", None)
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            actual_name = node.targets[0].id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            actual_name = node.target.id
        require(actual_name == name and fingerprint(node) == expected,
                "Encoding reviewed addition differs: " + name)
    del module.body[first:last]
    require(len(encoder.body) == 10, "Encoding cache statement census differs")
    for position, expected in ENCODER_ADDITIONS:
        require(fingerprint(encoder.body[position]) == expected,
                "Encoding reviewed cache statement differs")
    encoder.body = [encoder.body[0], *encoder.body[4:7], statement("return bytes(data)")]
    restored = fingerprint(module)
    require(restored == HISTORICAL_AST_SHA256, "Entire historical transport/encoder AST differs")
    return {"path": PATH, "historical_sha256": HISTORICAL_SHA256,
            "current_sha256": sha(current), "kind": "reviewed_private_owned_encoding_extension",
            "historical_ast_sha256": restored,
            "scope": "exact_source_correspondence_only_no_execution_or_acceptance"}


def verify_source(root: Path, name, historical_sha256):
    require(name == PATH, "Unknown encoding source route")
    path = Path(root) / name
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_SOURCE_BYTES,
            "Encoding source missing, redirected or oversized")
    with path.open("rb") as stream:
        raw = stream.read(MAX_SOURCE_BYTES + 1)
    return verify_current(raw, historical_sha256)
