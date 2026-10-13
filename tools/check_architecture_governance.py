"""Offline integrity checks for the maintained architecture guidance.

Checks the inline Markdown links and principle references used in these files;
this is not a general Markdown parser, a capability registry, or a semantic
verifier. No compiler imports, subprocesses, network access or writes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CHARTER = "docs/architecture-charter.md"
ROADMAP = "docs/architecture-refactoring-roadmap.md"
MATRIX = "docs/capability-matrix.md"
REVIEW = "docs/architecture-review.md"
ADR = "docs/decisions/0009-architecture-charter-and-incremental-refactoring.md"
DOCUMENTS = (CHARTER, ROADMAP, MATRIX, REVIEW, ADR)
PRINCIPLES = frozenset(f"AC-{number:02d}" for number in range(1, 10))
CATALOG = "protocol/policy-target-capabilities-v0.1.json"
ENTRYPOINTS = {
    "AGENTS.md": (CHARTER, ROADMAP, MATRIX, REVIEW),
    "README.md": (CHARTER, ROADMAP, MATRIX, REVIEW),
    "docs/development-validation.md": (CHARTER, ROADMAP, MATRIX, REVIEW),
    "docs/architecture.md": (CHARTER, ROADMAP, MATRIX),
    "docs/semantic-architecture.md": (CHARTER, ROADMAP, MATRIX),
    "docs/product-vision-and-integration-roadmap.md": (CHARTER, ROADMAP, MATRIX),
    ".github/pull_request_template.md": (CHARTER, MATRIX, REVIEW),
}
WORKFLOWS = (".github/workflows/ci.yml", ".github/workflows/policy-development.yml")
CLAIM = (
    "Documentation integrity only; not semantic compliance, executed capability, "
    "compiler correctness, biological evidence or release acceptance."
)


class GovernanceError(ValueError):
    """An actionable missing or inconsistent architecture reference."""


def prose(text: str) -> str:
    """Ignore fenced examples and HTML comments when checking navigation."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return re.sub(r"^(`{3,}|~{3,})[^\n]*\n.*?^\1\s*$", "", text, flags=re.M | re.S)


def heading_anchors(text: str) -> set[str]:
    """GitHub-style anchors for the plain ATX headings used by these documents."""
    anchors = set()
    for heading in re.findall(r"^#{1,6} (.+?)\s*$", prose(text), re.M):
        slug = re.sub(r"[^\w -]", "", heading.rstrip("# ").lower()).replace(" ", "-")
        candidate, suffix = slug, 0
        while candidate in anchors:
            suffix += 1
            candidate = f"{slug}-{suffix}"
        anchors.add(candidate)
    return anchors


def local_links(root: Path, relative: str, text: str) -> list[Path]:
    result = []
    for target in re.findall(r"\[[^\]\n]*\]\(([^()\s]+)\)", prose(text)):
        link = urlsplit(target)
        if link.scheme or link.netloc:
            # The PR template needs absolute URLs that also work in a PR body.
            prefix = "https://github.com/logannye/biocompiler/blob/main/"
            if target.startswith(prefix):
                path = root / unquote(link.path.split("/blob/main/", 1)[1])
            else:
                continue  # Remote availability is deliberately outside this gate.
        else:
            path = (root / relative).parent / unquote(link.path) if link.path else root / relative
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise GovernanceError(f"{relative}: link escapes repository: {target}")
        if not resolved.exists():
            raise GovernanceError(f"{relative}: missing link target: {target}")
        if link.fragment and resolved.suffix == ".md":
            anchors = heading_anchors(resolved.read_text(encoding="utf-8"))
            if unquote(link.fragment) not in anchors:
                raise GovernanceError(f"{relative}: missing heading anchor: {target}")
        result.append(resolved)
    return result


def check(root: Path = ROOT) -> dict[str, object]:
    root = root.resolve()
    texts = {}
    for relative in dict.fromkeys((*DOCUMENTS, *ENTRYPOINTS, *WORKFLOWS)):
        try:
            texts[relative] = (root / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise GovernanceError(f"{relative}: cannot read required file: {error}") from error

    headings = re.findall(r"^### (AC-\d{2})\b", prose(texts[CHARTER]), re.M)
    if Counter(headings) != Counter(PRINCIPLES):
        raise GovernanceError(f"{CHARTER}: define AC-01 through AC-09 exactly once")
    link_count = 0
    for relative in DOCUMENTS:
        text = prose(texts[relative])
        unknown = set(re.findall(r"\bAC-\d{2}\b", text)) - PRINCIPLES
        if unknown:
            raise GovernanceError(f"{relative}: undefined charter IDs: {sorted(unknown)}")
        link_count += len(local_links(root, relative, text))
    for relative in (REVIEW, ROADMAP):
        mentioned = set(re.findall(r"\bAC-\d{2}\b", prose(texts[relative])))
        if missing := PRINCIPLES - mentioned:
            raise GovernanceError(f"{relative}: missing principle coverage: {sorted(missing)}")
    capabilities = re.findall(r"^#{2,3} (CAP-\d{2})\b", prose(texts[MATRIX]), re.M)
    if not capabilities or len(capabilities) != len(set(capabilities)):
        raise GovernanceError(f"{MATRIX}: capability headings must have unique CAP-nn IDs")
    if (root / CATALOG) not in local_links(root, MATRIX, texts[MATRIX]):
        raise GovernanceError(f"{MATRIX}: link the existing runtime catalog {CATALOG}")

    for relative, required in ENTRYPOINTS.items():
        # Only required navigation is checked in older documents. Their historical
        # links and evidence are not silently brought into this maintenance scope.
        links = local_links(root, relative, texts[relative]) if relative == ".github/pull_request_template.md" else []
        if not links:
            for target in re.findall(r"\[[^\]\n]*\]\(([^()\s]+)\)", prose(texts[relative])):
                if Path(unquote(urlsplit(target).path)).name in {Path(name).name for name in required}:
                    links.extend(local_links(root, relative, f"[reference]({target})"))
        missing = [name for name in required if root / name not in links]
        if missing:
            raise GovernanceError(f"{relative}: missing architecture navigation: {missing}")

    command = "python -B tools/check_architecture_governance.py"
    tests = "python -B -m unittest tests.test_architecture_governance"
    for relative in WORKFLOWS:
        for required in (command, tests):
            if not re.search(r"^ +" + re.escape(required) + r"\s*$", texts[relative], re.M):
                raise GovernanceError(f"{relative}: missing active preflight command: {required}")
    return {
        "status": "documentation_integrity_checked",
        "principles": len(headings),
        "capability_rows": len(capabilities),
        "documents": len(DOCUMENTS),
        "local_links": link_count,
        "claim_scope": CLAIM,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        result = check(args.root)
    except GovernanceError as error:
        print(f"Architecture guidance check failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
