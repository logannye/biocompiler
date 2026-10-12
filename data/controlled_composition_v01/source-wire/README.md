# Controlled-composition source wire originals

These frozen inputs exercise the additive source representation. They do not
establish source admission, reference resolution, compatible realization,
material validity, requirement satisfaction, native capability or empirical
function.

`source-shape.json` is a standalone, literal BuildRequest with the controlled
source profile at both root and program, bounded assurance and one
ControlledActivity. Its semantic bundle retains the legacy semantic vocabulary.
It deliberately retains unresolved artificial references and legacy declarations:
a codec must preserve those inputs, while later native admission must assess
them. A successful round trip is the only positive expectation here.

`negative-mutations.json` contains twenty independent single mutations of that
original. Every case starts from fresh original bytes and expects representation
rejection. Paths are ordered object keys or array indices. `replace` requires an
existing field, `add` an absent field, and `remove` an existing field. These are
wire-shape/profile negatives; they do not stand in for semantic negative cases.

Both files use UTF-8 JSON with sorted keys, compact separators and one terminal
newline. Their exact SHA-256 values are literal expectations in
`tests/test_policy_controlled_composition_source.py`. The tests read these files
directly; they never rebuild the originals from SDK annotations, SDK serializers,
the native table or another fixture. The independent normative authority remains
`protocol/policy-controlled-composition-source-v0.1.schema.json`.

These same literal inputs may be used for the later native decoder ingress
tests. No native decoder has yet accepted them.
