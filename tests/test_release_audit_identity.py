"""Literal API identity fixtures; never real release acceptance evidence."""
import copy
import unittest
from tools.release_audit_identity import IdentityError, check_main_identity, check_pr_identity


def main_controls():
    if not __debug__:
        raise RuntimeError('Literal audit controls require enabled assertions')
    EXPECTED = {
        "schema": "biocompiler.actual_main_identity.v1", "repository": "example/project",
        "repository_id": 17, "main_branch": "main", "pr_number": 85,
        "pr_head_branch": "codex/integration", "accepted_pr_head": "a" * 40,
        "premerge_main": "b" * 40, "merge_revision": "c" * 40,
        "accepted_tree": "d" * 40, "run_id": 37, "run_attempt": 1,
        "workflow_id": 42, "workflow_path": ".github/workflows/ci.yml",
        "check_suite_id": 53, "actions_app_id": 64, "actions_app_slug": "github-actions",
    }
    # Independent literal input records, not values assembled from EXPECTED or from
    # the checker. These are deliberately fictional IDs and cannot be real receipts.
    INPUTS = {
        "run": {"event": "push", "head_branch": "main", "head_sha": "c" * 40,
                "head_commit": {"id": "c" * 40, "tree_id": "d" * 40}, "id": 37, "run_attempt": 1,
                "workflow_id": 42, "path": ".github/workflows/ci.yml", "check_suite_id": 53,
                "repository": {"full_name": "example/project", "id": 17},
                "head_repository": {"full_name": "example/project", "id": 17},
                "status": "completed", "conclusion": "success", "pull_requests": []},
        "commit": {"sha": "c" * 40, "tree": {"sha": "d" * 40},
                   "parents": [{"sha": "b" * 40}, {"sha": "a" * 40}]},
        "main_ref": {"ref": "refs/heads/main", "object": {"type": "commit", "sha": "c" * 40}},
        "pr": {"number": 85, "state": "closed", "merged": True, "merge_commit_sha": "c" * 40,
               "head": {"sha": "a" * 40, "ref": "codex/integration",
                        "repo": {"full_name": "example/project", "id": 17}},
               "base": {"ref": "main", "sha": "c" * 40,
                        "repo": {"full_name": "example/project", "id": 17}}},
        "suite": {"id": 53, "head_sha": "c" * 40, "head_branch": "main",
                  "before": "b" * 40, "after": "c" * 40, "head_commit": {"id": "c" * 40, "tree_id": "d" * 40},
                  "repository": {"full_name": "example/project", "id": 17},
                  "app": {"id": 64, "slug": "github-actions"},
                  "status": "completed", "conclusion": "success", "pull_requests": []},
    }


    def replace(record, path, value):
        for name in path[:-1]:
            record = record[name]
        record[path[-1]] = value


    positive = []
    baseline = check_main_identity(expected=EXPECTED, **INPUTS)
    assert baseline["source_revision"] == "c" * 40 == baseline["tested_revision"]
    assert baseline["ordered_merge_parents"] == ["b" * 40, "a" * 40]
    positive.append("independent literal normal-merge push identity")
    supplement = copy.deepcopy(INPUTS)
    supplement["run"]["pull_requests"] = [{"number": 999}]
    supplement["suite"]["pull_requests"] = [{"number": 999}, {"number": 85}]
    assert check_main_identity(expected=EXPECTED, **supplement) == baseline
    positive.append("supplemental push PR associations do not supply identity")
    pending = copy.deepcopy(INPUTS)
    for name in ("run", "suite"):
        pending[name].update(status="in_progress", conclusion=None)
    pending_result = check_main_identity(expected=EXPECTED, require_success=False, **pending)
    assert pending_result["requires_success"] is False
    positive.append("acquisition-only active run is explicitly not final")
    queued = copy.deepcopy(INPUTS)
    for name in ("run", "suite"):
        queued[name].update(status="queued", conclusion=None)
    assert check_main_identity(expected=EXPECTED, require_success=False, **queued)["requires_success"] is False
    positive.append("acquisition-only queued run is explicitly not final")

    cases = [
        ("PR event", ("run", "event"), "pull_request"),
        ("manual event", ("run", "event"), "workflow_dispatch"),
        ("non-main branch", ("run", "head_branch"), "codex/integration"),
        ("old PR source", ("run", "head_sha"), "a" * 40),
        ("different head commit", ("run", "head_commit", "id"), "a" * 40),
        ("contradictory run head tree", ("run", "head_commit", "tree_id"), "e" * 40),
        ("old run", ("run", "id"), 36), ("rerun attempt", ("run", "run_attempt"), 2),
        ("bool attempt", ("run", "run_attempt"), True),
        ("wrong workflow", ("run", "workflow_id"), 41),
        ("wrong workflow path", ("run", "path"), ".github/workflows/other.yml"),
        ("wrong suite", ("run", "check_suite_id"), 52),
        ("wrong repo", ("run", "repository", "full_name"), "example/other"),
        ("wrong repo id", ("run", "repository", "id"), 18),
        ("fork source", ("run", "head_repository", "id"), 18),
        ("wrong Git commit", ("commit", "sha"), "a" * 40),
        ("changed merge tree", ("commit", "tree", "sha"), "e" * 40),
        ("swapped parents", ("commit", "parents"), [{"sha": "a" * 40}, {"sha": "b" * 40}]),
        ("self-parent", ("commit", "parents"), [{"sha": "b" * 40}, {"sha": "c" * 40}]),
        ("squash", ("commit", "parents"), [{"sha": "b" * 40}]),
        ("extra parent", ("commit", "parents"), [{"sha": "b" * 40}, {"sha": "a" * 40}, {"sha": "e" * 40}]),
        ("moved main", ("main_ref", "object", "sha"), "e" * 40),
        ("different ref", ("main_ref", "ref"), "refs/heads/other"),
        ("noncommit ref", ("main_ref", "object", "type"), "tag"),
        ("different PR", ("pr", "number"), 95), ("PR open", ("pr", "state"), "open"),
        ("PR unmerged", ("pr", "merged"), False), ("integer merged flag", ("pr", "merged"), 1),
        ("different merge", ("pr", "merge_commit_sha"), "e" * 40),
        ("changed accepted head", ("pr", "head", "sha"), "e" * 40),
        ("changed head branch", ("pr", "head", "ref"), "codex/other"),
        ("PR head fork", ("pr", "head", "repo", "id"), 18),
        ("wrong base branch", ("pr", "base", "ref"), "release"),
        ("wrong base repo", ("pr", "base", "repo", "full_name"), "example/other"),
        ("suite id", ("suite", "id"), 54), ("suite source", ("suite", "head_sha"), "a" * 40),
        ("suite head commit", ("suite", "head_commit", "id"), "a" * 40),
        ("contradictory suite head tree", ("suite", "head_commit", "tree_id"), "e" * 40),
        ("suite branch", ("suite", "head_branch"), "release"),
        ("suite before", ("suite", "before"), "e" * 40),
        ("suite after", ("suite", "after"), "e" * 40),
        ("suite repository", ("suite", "repository", "id"), 18),
        ("suite app id", ("suite", "app", "id"), 65),
        ("suite app slug", ("suite", "app", "slug"), "third-party"),
        ("run not complete", ("run", "status"), "in_progress"),
        ("run failed", ("run", "conclusion"), "failure"),
        ("suite skipped", ("suite", "conclusion"), "skipped"),
        ("suite not complete", ("suite", "status"), "queued"),
    ]
    cases.extend([
        ("floating run id alias", ("run", "id"), 37.0),
        ("floating repository id alias", ("run", "repository", "id"), 17.0),
        ("floating workflow id alias", ("run", "workflow_id"), 42.0),
        ("floating PR number alias", ("pr", "number"), 85.0),
        ("floating suite id alias", ("suite", "id"), 53.0),
        ("floating app id alias", ("suite", "app", "id"), 64.0),
        ("malformed run head commit", ("run", "head_commit"), []),
        ("malformed suite repository", ("suite", "repository"), None),
        ("malformed parent record", ("commit", "parents"), ["b" * 40, {"sha": "a" * 40}]),
        ("malformed PR head", ("pr", "head"), []),
    ])
    negative = []
    for name, path, value in cases:
        changed = copy.deepcopy(INPUTS)
        replace(changed, path, value)
        try:
            check_main_identity(expected=EXPECTED, **changed)
        except IdentityError as error:
            negative.append({"name": name, "diagnostic": str(error)})
        else:
            raise AssertionError("Mutation was accepted: " + name)
    try:
        check_main_identity(expected=EXPECTED, **pending)
    except IdentityError as error:
        negative.append({"name": "acquisition state cannot close final identity gate", "diagnostic": str(error)})
    else:
        raise AssertionError("Pending run accepted as final")

    # Acquisition cannot normalize a failure or an inconsistent status/conclusion
    # into permission to consume success-shaped artifacts.
    for surface in ("run", "suite"):
        for status, conclusion in (("completed", "failure"), ("completed", None),
                                   ("queued", "success"), ("in_progress", "failure")):
            changed = copy.deepcopy(pending)
            changed[surface].update(status=status, conclusion=conclusion)
            try:
                check_main_identity(expected=EXPECTED, require_success=False, **changed)
            except IdentityError as error:
                negative.append({"name": f"acquisition {surface} {status}/{conclusion}", "diagnostic": str(error)})
            else:
                raise AssertionError("Unhealthy acquisition state accepted")

    for surface, field in (("run", "head_sha"), ("commit", "tree"), ("suite", "before"),
                           ("pr", "merged"), ("main_ref", "object")):
        changed = copy.deepcopy(INPUTS)
        del changed[surface][field]
        try:
            check_main_identity(expected=EXPECTED, **changed)
        except IdentityError as error:
            negative.append({"name": f"missing API {surface}/{field}", "diagnostic": str(error)})
        else:
            raise AssertionError("Missing API authority accepted")

    for invalid_flag in (0, 1, "false", None):
        try:
            check_main_identity(expected=EXPECTED, require_success=invalid_flag, **INPUTS)
        except IdentityError as error:
            negative.append({"name": "non-Boolean require_success " + repr(invalid_flag), "diagnostic": str(error)})
        else:
            raise AssertionError("Non-Boolean acceptance flag accepted")

    for name, expected in (
        ("unknown expected field", {**EXPECTED, "ignored": True}),
        ("missing expected field", {key: value for key, value in EXPECTED.items() if key != "accepted_tree"}),
        ("nonobject expected authority", []),
        ("floating expected id alias", {**EXPECTED, "repository_id": 17.0}),
        ("short source hash", {**EXPECTED, "accepted_pr_head": "a"}),
        ("Boolean expected id", {**EXPECTED, "run_id": True}),
        ("self-parenting expected authority", {**EXPECTED, "accepted_pr_head": "c" * 40}),
    ):
        try:
            check_main_identity(expected=expected, **INPUTS)
        except IdentityError as error:
            negative.append({"name": name, "diagnostic": str(error)})
        else:
            raise AssertionError("Invalid expected authority accepted: " + name)

    return positive, negative


class ReleaseAuditIdentityTests(unittest.TestCase):
    def test_original_main_identity_controls_are_retained(self):
        positive, negative = main_controls()
        self.assertEqual(len(positive), 4)
        self.assertEqual(len(negative), 83)

    def test_literal_pr_identity_and_every_required_leaf(self):
        expected = {
            'schema': 'biocompiler.pull_request_identity.v1', 'repository': 'example/project',
            'repository_id': 17, 'main_branch': 'main', 'pr_number': 85,
            'pr_head_branch': 'codex/integration', 'head_revision': 'a' * 40,
            'base_revision': 'b' * 40, 'tested_revision': 'c' * 40, 'tree': 'd' * 40,
            'previous_head_revision': 'e' * 40, 'run_id': 37, 'run_attempt': 1,
            'workflow_id': 42, 'workflow_path': '.github/workflows/ci.yml',
            'check_suite_id': 53, 'actions_app_id': 64, 'actions_app_slug': 'github-actions',
        }
        # Literal inputs are not assembled from expected or from checker output.
        inputs = {
            'run': {'id': 37, 'run_attempt': 1, 'event': 'pull_request',
                    'head_branch': 'codex/integration', 'head_sha': 'a' * 40,
                    'head_commit': {'id': 'a' * 40, 'tree_id': 'd' * 40},
                    'workflow_id': 42, 'path': '.github/workflows/ci.yml', 'check_suite_id': 53,
                    'repository': {'id': 17, 'full_name': 'example/project'},
                    'head_repository': {'id': 17, 'full_name': 'example/project'},
                    'status': 'completed', 'conclusion': 'success',
                    'pull_requests': [{'number': 85,
                        'head': {'sha': 'a' * 40, 'ref': 'codex/integration', 'repo': {'id': 17}},
                        'base': {'sha': 'b' * 40, 'ref': 'main', 'repo': {'id': 17}}}]},
            'commit': {'sha': 'c' * 40, 'tree': {'sha': 'd' * 40},
                       'parents': [{'sha': 'b' * 40}, {'sha': 'a' * 40}]},
            'head_commit': {'sha': 'a' * 40, 'tree': {'sha': 'd' * 40}},
            'main_ref': {'ref': 'refs/heads/main', 'object': {'type': 'commit', 'sha': 'b' * 40}},
            'merge_ref': {'ref': 'refs/pull/85/merge', 'object': {'type': 'commit', 'sha': 'c' * 40}},
            'pr': {'number': 85, 'state': 'open', 'merged': False, 'merge_commit_sha': 'c' * 40,
                   'head': {'sha': 'a' * 40, 'ref': 'codex/integration',
                            'repo': {'id': 17, 'full_name': 'example/project'}},
                   'base': {'sha': 'b' * 40, 'ref': 'main',
                            'repo': {'id': 17, 'full_name': 'example/project'}}},
            'suite': {'id': 53, 'head_sha': 'a' * 40,
                      'head_commit': {'id': 'a' * 40, 'tree_id': 'd' * 40},
                      'head_branch': 'codex/integration', 'before': 'e' * 40, 'after': 'a' * 40,
                      'repository': {'id': 17, 'full_name': 'example/project'},
                      'app': {'id': 64, 'slug': 'github-actions'},
                      'status': 'completed', 'conclusion': 'success'},
        }
        result = check_pr_identity(expected=expected, **inputs)
        self.assertEqual(result['source_revision'], 'a' * 40)
        self.assertEqual(result['tested_revision'], 'c' * 40)
        self.assertEqual(result['ordered_merge_parents'], ['b' * 40, 'a' * 40])
        self.assertEqual(result['tree'], 'd' * 40)
        self.assertEqual(result['scope'], 'tested_merge_identity_only_not_artifact_or_release_acceptance')
        for status in ('queued', 'in_progress'):
            altered = copy.deepcopy(inputs)
            for name in ('run', 'suite'):
                altered[name].update(status=status, conclusion=None)
            self.assertFalse(check_pr_identity(expected=expected, require_success=False, **altered)['requires_success'])
            with self.assertRaises(IdentityError):
                check_pr_identity(expected=expected, **altered)

        def leaves(value, path=()):
            if type(value) is dict:
                for key, child in value.items():
                    yield from leaves(child, (*path, key))
            elif type(value) is list:
                for index, child in enumerate(value):
                    yield from leaves(child, (*path, index))
            else:
                yield path, value

        paths = list(leaves(inputs))
        self.assertGreater(len(paths), 50)
        for path, original in paths:
            for operation in ('omit', 'wrong-value', 'wrong-type'):
                changed = copy.deepcopy(inputs)
                parent = changed
                for part in path[:-1]:
                    parent = parent[part]
                if operation == 'omit':
                    del parent[path[-1]]
                elif operation == 'wrong-type':
                    parent[path[-1]] = [original]
                elif type(original) is str:
                    parent[path[-1]] = 'f' * 40 if len(original) == 40 else 'wrong'
                elif type(original) is bool:
                    parent[path[-1]] = not original
                else:
                    parent[path[-1]] = original + 1
                with self.subTest(path=path, operation=operation), self.assertRaises(IdentityError):
                    check_pr_identity(expected=expected, **changed)
        for path in (('commit', 'parents'), ('run', 'pull_requests')):
            for value in ([], None, [*inputs[path[0]][path[1]], inputs[path[0]][path[1]][0]]):
                changed = copy.deepcopy(inputs); changed[path[0]][path[1]] = value
                with self.subTest(path=path, value=value), self.assertRaises(IdentityError):
                    check_pr_identity(expected=expected, **changed)
        swapped = copy.deepcopy(inputs); swapped['commit']['parents'].reverse()
        with self.assertRaises(IdentityError):
            check_pr_identity(expected=expected, **swapped)
        for key in expected:
            changed = {k: v for k, v in expected.items() if k != key}
            with self.subTest(missing_expected=key), self.assertRaises(IdentityError):
                check_pr_identity(expected=changed, **inputs)
        for invalid in (0, 1, 'false', None):
            with self.subTest(require_success=invalid), self.assertRaises(IdentityError):
                check_pr_identity(expected=expected, require_success=invalid, **inputs)
