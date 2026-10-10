# Typed finite-machine research builds

`policy.finite_build` connects the existing public `BuildRequest` source to one
complete supplied finite-machine component-material authority. The immutable
`FiniteMachineBuild` contains that source, a `FiniteMachineAuthority`, and explicit
`PreservationLimits`. It uses the existing native finite-machine wire profiles;
Python class layout does not define a new source language or native schema.

Import preserves the complete original source, implementation models, component
library, composition rule, catalog and input bindings, provider/resource context,
construction authority and budgets. It supplies no missing models, sequences,
bindings or work allowances. Import and `ResearchProject.preflight()` establish
literal structural readiness only. Native admission and biological function have
not been assessed at that point.

The following repository example uses independently retained **artificial software
fixtures**, not a functional therapeutic payload or qualified biological component.
It exercises two different existing finite-machine shapes through the same public
API. Run native operations only in the project's authorized hosted environment.

```python
import hashlib
import json
from pathlib import Path

from biocompiler.policy.finite_build import FiniteMachineBuild
from biocompiler.policy.research_project import ResearchProject, SourceRecord

originals = Path("core/test/data/policy_finite_machine_v01.json")
original_bytes = originals.read_bytes()
fixture = json.loads(original_bytes)
source = SourceRecord(
    id="finite-software-originals",
    locator="urn:biocompiler:policy-finite-machine-v01",
    version="1",
    sha256=hashlib.sha256(original_bytes).hexdigest(),
    role="software_fixture",
    reuse_terms="Artificial compiler regression only; distribution terms assessed separately",
)
output = Path("research-output")
output.mkdir(exist_ok=True)

for case in fixture["cases"][:2]:  # retry_cycle and guarded_branch
    specification = FiniteMachineBuild.from_request(
        case["request"], limits=fixture["limits"],
    )
    project = ResearchProject.from_build(
        project_id=case["id"],
        title=f"Finite-machine software example: {case['id']}",
        build=specification,
        sources=(source,),
        assumptions=("Supplied artificial contracts; empirical function unassessed.",),
    )
    project_path = output / f"{case['id']}.json"
    bundle_path = output / f"{case['id']}.zip"
    project.dump(project_path)

    # Installed Core produces; separately installed Verify freshly checks and
    # exports the complete FASTA/manifest pair before atomic publication.
    built = ResearchProject.load(project_path).compile(output=bundle_path)
    assert built.compiled.executable == "core"
    assert built.verified.executable == "verify"

    reopened = ResearchProject.load(project_path)
    assert reopened.build.to_request() == case["request"]
    independently_verified = reopened.verify_bundle(bundle_path)
    assert independently_verified.artifact == built.verified.artifact
```

The project and bundle serve different purposes. Retain the independently
supplied project as original authority. Reopening a bundle does not import its
saved PASS: `verify_bundle()` rechecks its candidate with Verify under the current
project, then compares the complete exported FASTA and manifest bytes. A changed
source, supplied component, limit or other original invalidates comparison with
the old bundle. Rejected compilation retains its full native diagnostic report in
`ResearchProjectRejected.compiled` and publishes no bundle.

For authoring, use the public source builders to create a `BuildRequest`, then
construct `FiniteMachineBuild(document, authority, limits)`. The authority is
imported explicitly with `FiniteMachineAuthority.from_request(...)`. Limits are
typed `SourceExecutionLimits`, `CandidateExecutionLimits`,
`RequirementMonitorLimits` and `PreservationLimits`; every allowance is explicit.
`PreservationLimits.from_data(...)` losslessly imports existing allowances.
`dataclasses.replace` can express an intentional typed budget change without
modifying the original specification.

`specification.with_document(new_document)` is an explicit source replacement.
It preserves every other original field and **does not repair or repin catalog or
model authority**. Fresh native checking must establish that the edited program
still corresponds to those supplied components. Ordered states and transitions,
subject/encounter scope, observations, effect lifecycle, deployment and requirements
remain full source data; the facade does not reduce them to a Boolean condition.

This addition supports only
`biocompiler.policy_finite_machine_component_mrna.v0.1`. Existing research-project
routes retain their prior behavior. Machine-network and quantitative profiles are
not admitted merely because they share lower-level transport code. Explicit
`CoreClient` values may be passed to the project for authenticated hosted binaries;
the project rejects swapped Core/Verify roles before compilation.

Local tests use inert native peers to exercise immutable originals, routing,
publication and reopening. Actual compiler/checker acceptance and exact fixture
RNA require the separately recorded hosted source and installed SDK campaigns.
Neither kind of software test establishes mechanism function in human cells.
