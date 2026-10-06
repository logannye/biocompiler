"""Inert identity predicates for separately authenticated PR and main audits.

The caller must authenticate the expected record and these helper bytes against
an independently reviewed tool revision BEFORE invoking this module. An
expected record derived from the supplied API data is not independent authority.
This helper does not establish artifact, semantic, test or release acceptance.
It neither reads files nor imports repository code nor makes network requests.
"""
from __future__ import annotations

import re
from typing import Any


class IdentityError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise IdentityError(message)


def record(value: Any, label: str) -> dict[str, Any]:
    require(type(value) is dict, label + " must be an object")
    return value


def at(value: Any, *path: str) -> Any:
    for name in path:
        value = record(value, "/".join(path)).get(name)
    return value


def eq(actual: Any, expected: Any, label: str) -> None:
    require(type(actual) is type(expected) and actual == expected,
            label + " does not match independently reviewed authority")


def sha(value: Any, label: str) -> None:
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value) is not None,
            label + " must be a full lowercase Git SHA-1")


def check_main_identity(*, expected: dict[str, Any], run: dict[str, Any],
                        commit: dict[str, Any], main_ref: dict[str, Any],
                        pr: dict[str, Any], suite: dict[str, Any],
                        require_success: bool = True) -> dict[str, Any]:
    """Check push identity separately from normal-merge parent provenance.

    `require_success=False` permits only queued/in_progress/success states for
    acquisition; such a result cannot close a final acceptance gate. PR
    associations on a push run are supplemental data, not identity authority.
    The API commit is `/git/commits/M`, not the higher-level `/commits/M` shape.
    """
    expected = record(expected, "expected")
    keys = {"schema", "repository", "repository_id", "main_branch", "pr_number",
            "pr_head_branch", "accepted_pr_head", "premerge_main", "merge_revision",
            "accepted_tree", "run_id", "run_attempt", "workflow_id", "workflow_path",
            "check_suite_id", "actions_app_id", "actions_app_slug"}
    require(set(expected) == keys, "Unexpected or missing expected identity field")
    eq(expected["schema"], "biocompiler.actual_main_identity.v1", "identity schema")
    for key in ("accepted_pr_head", "premerge_main", "merge_revision", "accepted_tree"):
        sha(expected[key], key)
    for key in ("repository_id", "pr_number", "run_id", "run_attempt", "workflow_id",
                "check_suite_id", "actions_app_id"):
        require(type(expected[key]) is int and expected[key] > 0,
                key + " must be a positive integer")
    for key in ("repository", "main_branch", "pr_head_branch", "workflow_path", "actions_app_slug"):
        require(type(expected[key]) is str and bool(expected[key]), key + " must be nonempty text")
    eq(expected["main_branch"], "main", "reviewed main branch")
    eq(expected["workflow_path"], ".github/workflows/ci.yml", "reviewed workflow path")
    eq(expected["run_attempt"], 1, "reviewed fresh run attempt")
    eq(expected["actions_app_slug"], "github-actions", "reviewed Actions app")
    require(type(require_success) is bool, "require_success must be a Boolean")
    merge = expected["merge_revision"]
    head = expected["accepted_pr_head"]
    parent = expected["premerge_main"]
    require(len({merge, head, parent}) == 3, "Normal merge and its two parents must be distinct")

    for label, value in (("run", run), ("commit", commit), ("main_ref", main_ref),
                         ("pr", pr), ("suite", suite)):
        record(value, label)
    eq(at(run, "event"), "push", "run event")
    eq(at(run, "head_branch"), expected["main_branch"], "run branch")
    eq(at(run, "head_sha"), merge, "run source/tested revision")
    eq(at(run, "head_commit", "id"), merge, "run head commit")
    eq(at(run, "head_commit", "tree_id"), expected["accepted_tree"], "run head tree")
    for actual, key in (("id", "run_id"), ("run_attempt", "run_attempt"),
                        ("workflow_id", "workflow_id"), ("path", "workflow_path"),
                        ("check_suite_id", "check_suite_id")):
        eq(at(run, actual), expected[key], "run " + actual)
    for label, value in (("run repository", at(run, "repository")),
                         ("run head repository", at(run, "head_repository")),
                         ("suite repository", at(suite, "repository")),
                         ("PR base repository", at(pr, "base", "repo")),
                         ("PR head repository", at(pr, "head", "repo"))):
        eq(at(value, "full_name"), expected["repository"], label + " name")
        eq(at(value, "id"), expected["repository_id"], label + " id")

    eq(at(commit, "sha"), merge, "Git commit identity")
    eq(at(commit, "tree", "sha"), expected["accepted_tree"], "merge tree")
    parents = at(commit, "parents")
    require(type(parents) is list and len(parents) == 2, "Normal merge requires exactly two parents")
    eq([at(item, "sha") for item in parents], [parent, head], "ordered merge parents")
    eq(at(main_ref, "ref"), "refs/heads/" + expected["main_branch"], "current main ref")
    eq(at(main_ref, "object", "type"), "commit", "current main object type")
    eq(at(main_ref, "object", "sha"), merge, "current main revision")

    eq(at(pr, "number"), expected["pr_number"], "merged PR number")
    eq(at(pr, "state"), "closed", "merged PR state")
    eq(at(pr, "merged"), True, "merged PR flag")
    eq(at(pr, "merge_commit_sha"), merge, "merged PR revision")
    eq(at(pr, "head", "sha"), head, "accepted PR head")
    eq(at(pr, "head", "ref"), expected["pr_head_branch"], "accepted PR branch")
    eq(at(pr, "base", "ref"), expected["main_branch"], "merged PR base branch")
    # base.sha may move when GitHub refreshes a merged PR. The independently
    # retained premerge ref and actual ordered Git parents are the authority.

    eq(at(suite, "id"), expected["check_suite_id"], "suite identity")
    eq(at(suite, "head_sha"), merge, "suite source revision")
    eq(at(suite, "head_commit", "id"), merge, "suite head commit")
    eq(at(suite, "head_commit", "tree_id"), expected["accepted_tree"], "suite head tree")
    eq(at(suite, "head_branch"), expected["main_branch"], "suite branch")
    eq(at(suite, "before"), parent, "suite pre-push revision")
    eq(at(suite, "after"), merge, "suite post-push revision")
    eq(at(suite, "app", "id"), expected["actions_app_id"], "suite app id")
    eq(at(suite, "app", "slug"), expected["actions_app_slug"], "suite app slug")
    for label, value in (("run", run), ("suite", suite)):
        status, conclusion = at(value, "status"), at(value, "conclusion")
        if require_success:
            eq(status, "completed", label + " status")
            eq(conclusion, "success", label + " conclusion")
        else:
            require((status in ("queued", "in_progress") and conclusion is None)
                    or (status == "completed" and conclusion == "success"),
                    label + " has a failed or inconsistent acquisition state")
    return {
        "schema": "biocompiler.actual_main_identity_result.v1",
        "scope": "merge_and_push_identity_only_not_artifact_or_release_acceptance",
        "source_revision": merge, "tested_revision": merge,
        "ordered_merge_parents": [parent, head], "tree": expected["accepted_tree"],
        "run_id": expected["run_id"], "run_attempt": expected["run_attempt"],
        "requires_success": require_success,
    }


def check_pr_identity(*, expected: dict[str, Any], run: dict[str, Any],
                      commit: dict[str, Any], head_commit: dict[str, Any],
                      main_ref: dict[str, Any], merge_ref: dict[str, Any],
                      pr: dict[str, Any], suite: dict[str, Any],
                      require_success: bool = True) -> dict[str, Any]:
    """Bind an independently supplied PR head to its exact tested merge tree.

    A saved PR snapshot must belong to this head/base, even if the remote PR has
    advanced since acquisition. API records never supply their own expectations.
    """
    expected = record(expected, "expected")
    keys = {"schema", "repository", "repository_id", "main_branch", "pr_number",
            "pr_head_branch", "head_revision", "base_revision", "tested_revision",
            "tree", "previous_head_revision", "run_id", "run_attempt", "workflow_id",
            "workflow_path", "check_suite_id", "actions_app_id", "actions_app_slug"}
    require(set(expected) == keys, "Unexpected or missing expected PR identity field")
    eq(expected["schema"], "biocompiler.pull_request_identity.v1", "PR identity schema")
    for key in ("head_revision", "base_revision", "tested_revision", "tree", "previous_head_revision"):
        sha(expected[key], key)
    for key in ("repository_id", "pr_number", "run_id", "run_attempt", "workflow_id", "check_suite_id", "actions_app_id"):
        require(type(expected[key]) is int and expected[key] > 0, key + " must be a positive integer")
    for key in ("repository", "main_branch", "pr_head_branch", "workflow_path", "actions_app_slug"):
        require(type(expected[key]) is str and bool(expected[key]), key + " must be nonempty text")
    eq(expected["main_branch"], "main", "reviewed main branch")
    eq(expected["workflow_path"], ".github/workflows/ci.yml", "reviewed workflow path")
    eq(expected["run_attempt"], 1, "reviewed fresh run attempt")
    eq(expected["actions_app_slug"], "github-actions", "reviewed Actions app")
    require(type(require_success) is bool, "require_success must be a Boolean")
    head, base, tested = (expected[k] for k in ("head_revision", "base_revision", "tested_revision"))
    require(len({head, base, tested}) == 3, "PR tested merge and both parents must be distinct")
    for label, value in (("run", run), ("commit", commit), ("head commit", head_commit),
                         ("main ref", main_ref), ("merge ref", merge_ref), ("PR", pr), ("suite", suite)):
        record(value, label)
    eq(at(run, "event"), "pull_request", "run event")
    eq(at(run, "head_branch"), expected["pr_head_branch"], "run branch")
    eq(at(run, "head_sha"), head, "run source revision")
    eq(at(run, "head_commit", "id"), head, "run head commit")
    eq(at(run, "head_commit", "tree_id"), expected["tree"], "run head tree")
    for actual, key in (("id", "run_id"), ("run_attempt", "run_attempt"), ("workflow_id", "workflow_id"),
                        ("path", "workflow_path"), ("check_suite_id", "check_suite_id")):
        eq(at(run, actual), expected[key], "run " + actual)
    for label, value in (("run repository", at(run, "repository")), ("run head repository", at(run, "head_repository")),
                         ("suite repository", at(suite, "repository")), ("PR base repository", at(pr, "base", "repo")),
                         ("PR head repository", at(pr, "head", "repo"))):
        eq(at(value, "full_name"), expected["repository"], label + " name")
        eq(at(value, "id"), expected["repository_id"], label + " id")
    eq(at(commit, "sha"), tested, "tested Git commit")
    eq(at(commit, "tree", "sha"), expected["tree"], "tested tree")
    eq(at(head_commit, "sha"), head, "source Git commit")
    eq(at(head_commit, "tree", "sha"), expected["tree"], "source tree")
    parents = at(commit, "parents")
    require(type(parents) is list and len(parents) == 2, "PR tested merge requires exactly two parents")
    eq([at(item, "sha") for item in parents], [base, head], "ordered tested merge parents")
    for label, ref, name, revision in (("main", main_ref, "refs/heads/" + expected["main_branch"], base),
                                       ("merge", merge_ref, "refs/pull/" + str(expected["pr_number"]) + "/merge", tested)):
        eq(at(ref, "ref"), name, label + " ref")
        eq(at(ref, "object", "type"), "commit", label + " ref object type")
        eq(at(ref, "object", "sha"), revision, label + " ref revision")
    eq(at(pr, "number"), expected["pr_number"], "PR number")
    eq(at(pr, "state"), "open", "PR state")
    eq(at(pr, "merged"), False, "PR merged flag")
    eq(at(pr, "merge_commit_sha"), tested, "PR tested revision")
    eq(at(pr, "head", "sha"), head, "PR head")
    eq(at(pr, "head", "ref"), expected["pr_head_branch"], "PR branch")
    eq(at(pr, "base", "sha"), base, "PR base revision")
    eq(at(pr, "base", "ref"), expected["main_branch"], "PR base branch")
    associations = at(run, "pull_requests")
    require(type(associations) is list and len(associations) == 1, "Run must name exactly the expected PR")
    association = associations[0]
    eq(at(association, "number"), expected["pr_number"], "run associated PR")
    for side, revision, branch in (("head", head, expected["pr_head_branch"]), ("base", base, expected["main_branch"])):
        eq(at(association, side, "sha"), revision, "associated " + side + " revision")
        eq(at(association, side, "ref"), branch, "associated " + side + " ref")
        eq(at(association, side, "repo", "id"), expected["repository_id"], "associated " + side + " repository")
    eq(at(suite, "id"), expected["check_suite_id"], "suite identity")
    eq(at(suite, "head_sha"), head, "suite source revision")
    eq(at(suite, "head_commit", "id"), head, "suite head commit")
    eq(at(suite, "head_commit", "tree_id"), expected["tree"], "suite head tree")
    eq(at(suite, "head_branch"), expected["pr_head_branch"], "suite branch")
    eq(at(suite, "before"), expected["previous_head_revision"], "suite previous source")
    eq(at(suite, "after"), head, "suite current source")
    eq(at(suite, "app", "id"), expected["actions_app_id"], "suite app id")
    eq(at(suite, "app", "slug"), expected["actions_app_slug"], "suite app slug")
    for label, value in (("run", run), ("suite", suite)):
        status, conclusion = at(value, "status"), at(value, "conclusion")
        if require_success:
            eq(status, "completed", label + " status")
            eq(conclusion, "success", label + " conclusion")
        else:
            require((status in ("queued", "in_progress") and conclusion is None)
                    or (status == "completed" and conclusion == "success"), label + " failed acquisition state")
    return {"schema": "biocompiler.pull_request_identity_result.v1",
            "scope": "tested_merge_identity_only_not_artifact_or_release_acceptance",
            "source_revision": head, "tested_revision": tested, "ordered_merge_parents": [base, head],
            "tree": expected["tree"], "run_id": expected["run_id"], "run_attempt": expected["run_attempt"],
            "requires_success": require_success}
