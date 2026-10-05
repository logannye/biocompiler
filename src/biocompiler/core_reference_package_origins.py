"""Public identities of the fixed native reference-input constructor.

This is a representation recipe for ``load_reference_inputs``. Native input
preparation owns parsing, pins, adaptation and request construction. The paths
below describe the actual original constructor's object reuse; equal contents
never select an origin and these Python views confer no acceptance.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar, cast

from biocompiler.core_client import JsonValue
from biocompiler.core_pipeline_provider_views import ViewPath, allocate, require
from biocompiler.core_reference_provider_views import reference_shape
from biocompiler.core_reference_views import ReferenceViews
from biocompiler.ir.composition import CompositionInstance
from biocompiler.ir.construct import ConstructRequest
from biocompiler.registry import reference_builds
from biocompiler.registry.components import ComponentRegistry
from biocompiler.registry.references import ReferenceManifest

T = TypeVar('T')

_MANIFEST = reference_builds.MANIFEST_PIN
_REFERENCES = dict(reference_builds.REFERENCE_PINS)
_LIFETIME = vars(CompositionInstance)['lifetime']
_POLICY = vars(ConstructRequest)['evidence_policy']

# ComponentRegistry.lock retains each actual ComponentRecord identity and then
# sorts by (kind, id, version). This fixed reviewed adapter has one review pin,
# the manifest, three records and three source pins. Indexes describe that
# constructor provenance, not a search for equal values in arbitrary input.
_REGISTRY_IDENTITIES = ('registry', 'components', 0, 'identities')
_LOCK = ('request', 'composition', 'registry_lock')
_LOCK_ORIGINS: tuple[ViewPath, ...] = (
    ('registry', 'components', 0, 'evidence', 0),
    *((*_REGISTRY_IDENTITIES, index) for index in (3, 4, 5, 6, 0, 1, 2)),
)


class _InputFactory:
    def __init__(self, alphabet: str):
        require(reference_builds.MANIFEST_PIN is _MANIFEST
                and reference_builds.REFERENCE_PINS.get(alphabet) is _REFERENCES[alphabet]
                and vars(CompositionInstance)['lifetime'] is _LIFETIME
                and vars(ConstructRequest)['evidence_policy'] is _POLICY,
                'Reference input constructor defaults changed')
        self.origins: dict[ViewPath, object] = {}
        self.used: set[ViewPath] = set()
        self.fixed: dict[ViewPath, object] = {
            (*_REGISTRY_IDENTITIES, 3): _MANIFEST,
            ('request', 'references', 0, 'selection', 'manifest'): _MANIFEST,
            ('request', 'references', 0, 'selection', 'reference'): _REFERENCES[alphabet],
            ('request', 'placements', 0, 'reference'): _REFERENCES[alphabet],
            ('request', 'composition', 'instances', 0, 'lifetime'): _LIFETIME,
            ('request', 'evidence_policy'): _POLICY,
        }
        self.aliases: dict[ViewPath, ViewPath] = {
            (*_LOCK, 'identities', index): origin
            for index, origin in enumerate(_LOCK_ORIGINS)
        }
        self.aliases.update({
            ('request', 'composition', 'instances', 0, 'component'): (*_LOCK, 'components', 0),
            ('request', 'placements', 0, 'component'): (*_LOCK, 'components', 0),
        })

    def __call__(self, kind: type[T], path: ViewPath, document: JsonValue,
                 values: Mapping[str, object], /) -> T:
        require(path not in self.origins, 'Reference input origin path was reused')
        candidate: T = allocate(kind, values)
        if path in self.fixed or path in self.aliases:
            if path in self.fixed:
                origin = self.fixed[path]
            else:
                source = self.aliases[path]
                require(source in self.origins, 'Reference input origin precedes its construction')
                origin = self.origins[source]
            require(type(origin) is kind and reference_shape(origin) == reference_shape(candidate),
                    'Reference input value differs from its constructor origin')
            self.used.add(path)
            candidate = cast(T, origin)
        self.origins[path] = candidate
        return candidate

    def complete(self) -> None:
        require(self.used == self.fixed.keys() | self.aliases.keys(),
                'Reference input constructor origin census differs')


def input_roots(alphabet: str, request_document: JsonValue,
                reference_document: JsonValue, registry_document: JsonValue
                ) -> tuple[ConstructRequest, ReferenceManifest, ComponentRegistry]:
    """Hydrate one native default-loader result, with its original identities.

    Call only for the actual default input constructor's native result. Replaced
    loaders return their own actual objects; this function must not normalize
    them or import them as native preparation capabilities. Each invocation
    allocates fresh roots. Only actual original module/class defaults are shared
    between invocations.
    """
    require(type(alphabet) is str and alphabet in _REFERENCES,
            'Reference input view requires a reviewed DNA or RNA alphabet')
    factory = _InputFactory(alphabet)
    views = ReferenceViews(factory)
    # The original constructor creates the registry before its lock/request.
    # Decode in the same dependency order so every reused identity already has
    # one definite physical origin.
    reference = views.reference_manifest(reference_document, ('reference',))
    registry = views.registry(registry_document, ('registry',))
    request = views.construct_request(request_document, ('request',))
    require(len(registry.components) == len(request.references)
            == len(request.molecules) == len(request.placements)
            == len(request.composition.instances)
            == len(request.composition.registry_lock.components) == 1,
            'Reference input view differs from the fixed single-CDS constructor')
    component = registry.components[0]
    require(len(component.identities) == 7 and len(component.evidence) == 1
            and len(request.composition.registry_lock.identities) == 8,
            'Reference input identity inventory differs from its constructor')
    factory.complete()
    return request, reference, registry
