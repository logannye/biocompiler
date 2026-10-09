"""Inert controls for the grounded-helper hosted witness; never native evidence."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from biocompiler import policy as p
from biocompiler import core_policy_component_material as transport
from tools import check_policy_grounded_helper_material as campaign
from tests import test_policy_component_material_campaign as peer
from tests import test_policy_multi_member_campaign as payload_peer

ROOT = Path(__file__).resolve().parents[1]


def original(alternate=False):
    """Literal original edits independent of the typed helper authoring recipe."""
    value, limits = payload_peer.original(False)
    definition = {"$type":"SemanticDefinition", "id":"fixture.grounded_helper_capacity", "version":"1", "category":"capability",
        "meaning":"Supplied source-independent helper expression completion and retained-record capacity; no empirical claim.",
        "parameters":[], "result":None, "clauses":[], "assumptions":[], "executor_kind":None, "subject_kind":None}
    value["document"]["program"]["semantics"]["definitions"].append(definition)
    reference = {"$type":"DefinitionRef", "id":definition["id"], "version":"1", "digest":campaign.canonical_digest(definition)}
    value["document"]["deployment"]["payload"].update(helper_count=1, member_count=3, orf_count=3, product_count=3)
    entry = value["document"]["implementations"]["implementations"][0]
    entry["dependencies"].append(reference)
    value["catalog_bindings"][0]["entry_digest"] = campaign.canonical_digest(entry)
    limits["candidate"]["max_work"] = 2_000_000
    return value, limits


def outer(alternate=False):
    implementation, limits = original(alternate)
    return {"schema_version":transport.GROUNDED_HELPER_REQUEST_SCHEMA, "profile":transport.GROUNDED_HELPER_REQUEST_PROFILE,
        "implementation_request":implementation, "input_bindings":[], "resource_bindings":[],
        **{key:{"inert":key} for key in ("composition_rule","catalog_binding","budgets")},
        # Nonempty legacy-shaped transport data only; no executable component claim.
        "component_library":{"inert":"component_library", "components":[{
            "schema_version":"biocompiler.policy_component_material.v0.1",
            "profile":"biocompiler.policy_exact_local_material.v0.1",
            "body":{"inert":"complete original local component", "alternate":alternate}}]},
        "context":{"profile":transport.GROUNDED_HELPER_REQUEST_PROFILE}}, limits


def fixture():
    cases = []
    for label in ("A","B"):
        request, limits = outer(label == "B")
        cases.append({"id":label, "request":request, "limits":limits,
            "expected":{"sequences":deepcopy(campaign.SEQUENCES[label]), "molecules":[{"id":name,"sequence":sequence} for name,sequence in zip(("payload_a","payload_b","helper_rna"),campaign.SEQUENCES[label])], "ordered_union":{}, "carrier_projections":[],
                "link_projections":[], "helper_projections":[{"member":"helper_rna","literal":label}], "histories":25, "transitions":86, "prefixes_started":87,
                "obligations":deepcopy(campaign.OBLIGATIONS), "prerequisite_closure":{"inert":True}}})
    return {"schema_version":campaign.FIXTURE_SCHEMA, "status":"source_declarations_only", "acceptance":False,
            "source_sha256":{name:campaign.digest_file(ROOT / name) for name in campaign.INPUTS}, "cases":cases}


def synthetic_graph():
    # Format-only model pins and topology; this is not an executable candidate.
    local = lambda index: {"slot":"controller_a" if index < 24 else "stage_b", "node":f"local{index}"}
    endpoint = lambda index, port: {**local(index), "port":port}
    models = [{"identity":{"id":f"inert.model{index}"}, "configuration_digest":str(index) * 64} for index in range(29)]
    union = {"nodes":[{**local(index), "model":model} for index, model in enumerate(models)],
        "wires":[{"producer":endpoint(index % 29,"out"), "consumer":endpoint((index + 1) % 29,f"in{index}")}
                 for index in range(55)],
        "inputs":[{"id":"condition", "kind":"evidence", "consumer":endpoint(0,"samples")}],
        "semantic_exports":[endpoint(28,"out")],
        "atomic_groups":[{"slot":"controller_a", "id":"group", "arbiter":local(3), "commits":[local(index) for index in range(7,14)]}]}
    candidate = {"assembly_proposal":{"nodes":[{**local(index), "actual":f"opaque{index}"} for index in range(29)]},
        "implementation":{"nodes":[{"id":f"opaque{index}", "model":model["identity"], "configuration_digest":model["configuration_digest"]}
                                     for index, model in enumerate(models)],
            "wires":[{"producer":{"node":f"opaque{index % 29}", "port":"out"},
                      "consumer":{"node":f"opaque{(index + 1) % 29}", "port":f"in{index}"}} for index in range(55)],
            "inputs":[{"id":"condition", "kind":"evidence", "consumer":{"node":"opaque0", "port":"samples"}}],
            "semantic_exports":[{"node":"opaque28", "port":"out"}],
            "atomic_groups":[{"id":"group", "arbiter":"opaque3", "commits":[f"opaque{index}" for index in range(7,14)]}]}}
    return union, candidate


def result_and_case():
    # Explicitly synthetic protocol leaves isolate this literal validator.
    expected = {"sequences":["CCAUGGCUUAAGGAAAA","CCAUGCCUUAAGGAAAA","CCAUGGCUUAAGGAAAA"],
        "molecules":[{"id":"payload_a","sequence":"CCAUGGCUUAAGGAAAA"},{"id":"payload_b","sequence":"CCAUGCCUUAAGGAAAA"},
                     {"id":"helper_rna","sequence":"CCAUGGCUUAAGGAAAA"}],
        "carrier_projections":[], "link_projections":[],
        "helper_projections":[{"material":"complete original helper", "product":"MA", "molecule_fingerprint":"original"}],
        "prerequisite_closure":{"member_allocations":[{"member":"payload_a","delivery":{"body":"shared complete original"}},
                                                         {"member":"payload_b","delivery":{"body":"shared complete original"}}],
            "transport_allocations":[{"link":"stage1.product","provider":"original full pin"}],
            "helper_allocations":[{"member":"helper_rna", "material":"original helper pin", "provider_body":"original full body",
                "bootstrap":{"completion":{"earliest":"1","latest":"1"}}, "consumers":["controller_a","stage_b"],
                "resource_allocations":[{"reserved":4},{"reserved":4}], "delivery":{"body":"shared complete original"}}],
            "providers":["original providers"], "graph":{"roots":["catalog transport"],"edges":["transport environment"]}}}
    assembly = {"carrier_projections":[],"link_projections":[],"helper_projections":deepcopy(expected["helper_projections"])}
    closure = {**deepcopy(expected["prerequisite_closure"]), "assembly_fingerprint":campaign.canonical_digest(assembly)}
    report = {"status":transport.ACCEPTED_STATUS,"profile":transport.GROUNDED_HELPER_REQUEST_PROFILE,"claim_scope":transport.CLAIM_SCOPE,
        "premise":transport.PREMISE,"assembly_status":"pass","context_status":"pass","prerequisite_status":"pass",
        "all_original_obligations_discharged":True,"empirical":"unassessed","artifact":"withheld","export":"withheld",
        "assembly":assembly,"context":{"discharges":[{"id":name} for name in campaign.CONTEXT_DISCHARGES],
            "prerequisite_closure":deepcopy(closure), **{key:deepcopy(closure[key]) for key in ("member_allocations","transport_allocations","helper_allocations")}},
        "prerequisites":closure,
        "obligations":[{"obligation":name,"status":"discharged","stage":"declared_context", "evidence":{"prerequisites":campaign.canonical_digest(closure)}}
                       for name in campaign.OBLIGATIONS],
        "preservation":{"preservation":"pass","coverage":{"complete":True,"histories":25,"transitions":86,"prefixes_started":87,"matched_prefixes":87},
            "requirements":[{"id":name,"status":"pass","nonvacuous":True,"histories":deepcopy(campaign.REQUIREMENT_HISTORIES[name])}
                            for name in ("first_initiation","second_initiation")]}}
    union, candidate = synthetic_graph()
    expected["ordered_union"] = union
    candidate["construction"] = {"inventory":{"molecules":deepcopy(expected["molecules"])}}
    return {"artifact":None,"report":report,"candidate":candidate}, {"expected":expected}


class GroundedHelperCampaignTests(unittest.TestCase):
    def setUp(self):
        for target in ("subprocess.Popen","subprocess.run"):
            guard = patch(target, side_effect=AssertionError("No native or process execution"))
            guard.start(); self.addCleanup(guard.stop)

    def test_typed_authoring_preserves_full_independent_a_b_originals(self):
        for alternate in (False,True):
            declared, limits = original(alternate)
            authored, actual_limits = campaign.independent_original(ROOT,alternate)
            self.assertEqual((authored,actual_limits),(declared,limits))
            supplied,_ = outer(alternate)
            before = deepcopy(supplied)
            request,evidence = campaign.author_request(supplied,alternate)
            self.assertEqual(request,before)
            self.assertEqual(supplied,before)
            self.assertEqual(evidence["request_digest"],campaign.canonical_digest(before))
            self.assertEqual(evidence["runtime_semantics"],"not_executed")

    def test_source_maps_and_fixed_product_uses_preserve_distinct_identity(self):
        document,_ = campaign.authored_document(ROOT,False)
        declarations = document.program.declarations
        parameters = [row for row in declarations if isinstance(row,p.Parameter)]
        self.assertEqual([(row.id,row.value) for row in parameters],[("product_a","fixture.product.alpha"),("product_b","fixture.product.beta")])
        self.assertEqual([row.declaration_id for row in document.program.source_map],[row.id for row in declarations])
        self.assertEqual([row.parameters[0].value.ref.id for row in declarations if isinstance(row,p.Effect)],["product_a","product_b"])
        self.assertEqual((document.deployment.payload.design_count,document.deployment.payload.member_count),(1,3))

    def test_original_packet_requires_exact_five_source_pins_and_full_domain(self):
        value = fixture()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "originals.json"
            path.write_text(json.dumps(value))
            self.assertEqual(campaign.checked_fixture(ROOT,path),value)
            controls = []
            changed = deepcopy(value); changed["source_sha256"].pop(campaign.INPUTS[-1]); controls.append(changed)
            changed = deepcopy(value); changed["acceptance"] = True; controls.append(changed)
            changed = deepcopy(value); changed["cases"].reverse(); controls.append(changed)
            changed = deepcopy(value); changed["cases"][0]["request"]["implementation_request"]["operating_domain"]["horizon_ticks"] -= 1; controls.append(changed)
            changed = deepcopy(value); changed["cases"][0]["expected"]["sequences"].pop(); controls.append(changed)
            changed = deepcopy(value); changed["cases"][1]["request"]["implementation_request"]["document"]["program"]["declarations"][6]["value"] = "fixture.product.gamma"; controls.append(changed)
            for changed in controls:
                with self.subTest(changed=controls.index(changed)):
                    path.write_text(json.dumps(changed))
                    with self.assertRaises(AssertionError): campaign.checked_fixture(ROOT,path)

    def test_independent_oracle_requires_three_members_and_complete_helper_allocation(self):
        value,case = result_and_case()
        campaign.checked_result(value,case)
        mutations = [lambda v:v["candidate"]["construction"]["inventory"]["molecules"].reverse(),
            lambda v:v["candidate"]["construction"]["inventory"]["molecules"].pop(),
            lambda v:v["report"]["prerequisites"]["member_allocations"].pop(),
            lambda v:v["report"]["context"]["transport_allocations"].clear(),
            lambda v:v["report"]["context"]["helper_allocations"].clear(),
            lambda v:v["report"]["assembly"]["helper_projections"].clear(),
            lambda v:v["report"]["prerequisites"]["helper_allocations"][0]["bootstrap"]["completion"].update(latest="2"),
            lambda v:v["report"]["prerequisites"]["helper_allocations"][0]["resource_allocations"][1].update(reserved=3),
            lambda v:v["report"]["obligations"].pop(),
            lambda v:v["report"]["preservation"]["coverage"].update(histories=1),
            lambda v:v["report"]["preservation"]["requirements"][1]["histories"].update(pass_=25),
            lambda v:v["report"]["preservation"]["requirements"][1].update(nonvacuous=False),
            lambda v:v["report"].update(empirical="verified")]
        for mutate in mutations:
            changed = deepcopy(value); mutate(changed)
            with self.subTest(mutate=mutate):
                with self.assertRaises(AssertionError): campaign.checked_result(changed,case)

    def test_guard_and_machine_write_controls_are_staged_and_nonmutating(self):
        candidate = {"binding":{"rules":[],"transitions":[{"gate":"g0","commit":"c0"},{"gate":"g1","commit":"c1"}]},
            "implementation":{"wires":[{"producer":{"node":"evidence","port":"value"},"consumer":{"node":"g0","port":"guard"}},
                {"producer":{"node":"true","port":"out"},"consumer":{"node":"g1","port":"guard"}},
                {"producer":{"node":"c0","port":"machine_write"},"consumer":{"node":"machine","port":"write0"}},
                {"producer":{"node":"c1","port":"machine_write"},"consumer":{"node":"machine","port":"write1"}}]}}
        before = deepcopy(candidate)
        guard = campaign.changed_candidate(candidate,"guard")
        state = campaign.changed_candidate(candidate,"state")
        self.assertEqual(candidate,before)
        self.assertEqual(guard["implementation"]["wires"][0]["producer"],{"node":"true","port":"out"})
        self.assertEqual(state["implementation"]["wires"][2]["consumer"]["port"],"write1")
        self.assertEqual(state["implementation"]["wires"][3]["consumer"]["port"],"write0")

    def test_full_ordered_graph_oracle_rejects_same_census_identity_changes(self):
        union, candidate = synthetic_graph()
        campaign.checked_graph(candidate,union)
        mutations = [lambda v:v["assembly_proposal"]["nodes"].reverse(),
            lambda v:v["assembly_proposal"]["nodes"][1].update(actual="opaque0"),
            lambda v:v["implementation"]["nodes"][1].update(model={"id":"another"}),
            lambda v:v["implementation"]["nodes"][1].update(configuration_digest="changed"),
            lambda v:v["implementation"]["wires"][1]["consumer"].update(port="another"),
            lambda v:v["implementation"]["inputs"][0].update(id="another"),
            lambda v:v["implementation"]["semantic_exports"][0].update(node="opaque0"),
            lambda v:v["implementation"]["atomic_groups"][0]["commits"].reverse()]
        for mutate in mutations:
            changed = deepcopy(candidate); mutate(changed)
            with self.subTest(mutate=mutate):
                with self.assertRaises(AssertionError): campaign.checked_graph(changed,union)

    def test_material_control_changes_only_helper_and_rehashes_only_its_role(self):
        candidate = {"construction":{"inventory":{"molecules":[{"id":"payload_a","sequence":"CC"},{"id":"payload_b","sequence":"CU"},
            {"id":"helper_rna","sequence":"CA"}], "role_instances":[{"subject_id":name,"subject_fingerprint":name}
                for name in ("payload_a","payload_b","helper_rna")]}}}
        before = deepcopy(candidate)
        changed = campaign.changed_candidate(candidate,"material")["construction"]["inventory"]
        self.assertEqual(candidate,before)
        self.assertEqual(changed["molecules"][:2],candidate["construction"]["inventory"]["molecules"][:2])
        self.assertEqual(changed["molecules"][2]["sequence"],"GA")
        self.assertEqual(changed["role_instances"][:2],candidate["construction"]["inventory"]["role_instances"][:2])
        self.assertEqual(changed["role_instances"][2]["subject_fingerprint"],campaign.canonical_digest(changed["molecules"][2]))
        controls = [lambda v:v["construction"]["inventory"]["molecules"].pop(),
                    lambda v:v["construction"]["inventory"]["molecules"][2].update(id="payload_b"),
                    lambda v:v["construction"]["inventory"]["role_instances"].pop()]
        for mutate in controls:
            bad = deepcopy(candidate); mutate(bad)
            with self.assertRaises(AssertionError): campaign.changed_candidate(bad,"material")

    def test_retained_protocol_requires_complete_twenty_six_observations(self):
        packet = {"cases":[{"id":label,"request":{"case":label},"limits":{"limit":1}} for label in ("A","B")]}
        rows = peer.observations(packet)
        for row in rows:
            if row["name"] == "changed-material":
                row["result"]["report"]["obligations"] = [{"obligation":name,"status":"unresolved"} for name in campaign.OBLIGATIONS]
        with patch.object(campaign,"changed_candidate",side_effect=lambda value,kind:{**value,"changed":kind}), \
             patch("biocompiler.core_policy_component_material._result",side_effect=lambda response,payload:SimpleNamespace(result=response.result)):
            checked = campaign.check_observations(rows,packet,validate_result=lambda *_:None)
            self.assertEqual(set(checked),{"A","B"})
            for changed in (rows[:-1],rows + [rows[-1]],list(reversed(rows))):
                with self.assertRaises(AssertionError): campaign.check_observations(changed,packet,validate_result=lambda *_:None)
            changed = deepcopy(rows)
            next(row for row in changed if row["name"] == "changed-state")["result"]["diagnostics"][0]["code"] = "unrelated"
            with self.assertRaises(AssertionError): campaign.check_observations(changed,packet,validate_result=lambda *_:None)

    def test_a_b_preserve_whole_therapeutic_source_and_change_helper_only(self):
        self.assertEqual(original(False),original(True))
        self.assertEqual(campaign.independent_original(ROOT,False),campaign.independent_original(ROOT,True))
        document,_ = campaign.authored_document(ROOT,False)
        payload = document.deployment.payload
        self.assertEqual((payload.design_count,payload.member_count,payload.helper_count,payload.orf_count,payload.product_count),(1,3,1,3,3))
        self.assertEqual([ref.id for ref in document.implementations.implementations[0].dependencies],
                         ["fixture.inter_member_transport","fixture.grounded_helper_capacity"])
        self.assertEqual(campaign.SEQUENCES["A"][:2],campaign.SEQUENCES["B"][:2])
        self.assertNotEqual(campaign.SEQUENCES["A"][2],campaign.SEQUENCES["B"][2])
        self.assertEqual(len(campaign.OBLIGATIONS),24)
        self.assertEqual(len(campaign.CONTEXT_DISCHARGES),7)

    def test_typed_authoring_refuses_complete_source_or_profile_substitution(self):
        request,_ = outer()
        changes = [lambda v:v["implementation_request"]["document"]["program"]["source_map"][0].update(file="changed.py"),
                   lambda v:v["implementation_request"]["document"]["deployment"]["payload"].update(helper_count=0),
                   lambda v:v.update(schema_version=transport.MULTI_MEMBER_REQUEST_SCHEMA,profile=transport.MULTI_MEMBER_REQUEST_PROFILE)]
        for change in changes:
            bad = deepcopy(request); change(bad)
            with self.assertRaises(AssertionError): campaign.author_request(bad,False)

    def test_fresh_publication_requires_all_three_complete_manifest_members(self):
        value,case = result_and_case()
        case.update(request={"original":"independent"},limits={"candidate":{"max_work":2_000_000}})
        molecules = case["expected"]["molecules"]
        fasta = "".join(f">rna_{index + 1:04d} alphabet=RNA\n{molecule['sequence']}\n" for index,molecule in enumerate(molecules))
        manifest = {"request":deepcopy(case["request"]),"candidate":deepcopy(value["candidate"]),"limits":deepcopy(case["limits"]),
            "assessment":deepcopy(value["report"]),"members":[{"fasta_id":f"rna_{index + 1:04d}","member_id":molecule["id"],
                "molecule":deepcopy(molecule),"sequence_sha256":campaign.hashlib.sha256(molecule["sequence"].encode()).hexdigest()}
                for index,molecule in enumerate(molecules)]}
        value["artifact"] = {"fasta":fasta,"fasta_sha256":campaign.hashlib.sha256(fasta.encode()).hexdigest(),
                             "manifest":manifest,"manifest_sha256":campaign.canonical_digest(manifest)}
        campaign.checked_result(value,case)
        mutations = [lambda m:m["members"].pop(), lambda m:m["members"].reverse(),
            lambda m:m["members"][2]["molecule"].update(sequence="CCAUGGGUUAAGGAAAA"),
            lambda m:m["members"][2].update(sequence_sha256="0"*64),
            lambda m:m["members"][2].update(fasta_id="rna_0002"),
            lambda m:m["request"].update(original="different")]
        for mutate in mutations:
            changed = deepcopy(value); mutate(changed["artifact"]["manifest"])
            changed["artifact"]["manifest_sha256"] = campaign.canonical_digest(changed["artifact"]["manifest"])
            with self.assertRaises(AssertionError): campaign.checked_result(changed,case)
        changed = deepcopy(value)
        changed["artifact"]["fasta"] = fasta.rsplit(">rna_0003",1)[0]
        changed["artifact"]["fasta_sha256"] = campaign.hashlib.sha256(changed["artifact"]["fasta"].encode()).hexdigest()
        with self.assertRaises(AssertionError): campaign.checked_result(changed,case)

    def test_hosted_identity_guard_precedes_any_native_or_fixture_access(self):
        with patch.object(campaign,"identity",side_effect=ValueError("hosted identity required")), \
             patch.object(campaign,"checked_fixture") as fixture_check:
            with self.assertRaisesRegex(ValueError,"hosted identity"):
                campaign.run(SimpleNamespace())
            fixture_check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
