"""Immutable chemistry declarations and strict native-import oracle evidence."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from biocompiler.errors import SerializationError
from biocompiler.ir.molecule_records import _bounded_tree

_PATH=Path(__file__).resolve().parents[1]/"tools/freeze_molecule_chemistry.py"
_SPEC=importlib.util.spec_from_file_location("molecular_chemistry_corpus_under_test",_PATH)
campaign=importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(campaign)


class MoleculeChemistryCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retained=campaign.CORPUS.read_bytes()
        cls.corpus=json.loads(cls.retained)

    def test_retained_declarations_reproduce_exactly(self):
        rebuilt=campaign.build_corpus();campaign.check_corpus(rebuilt)
        self.assertEqual(campaign.encoded(rebuilt),self.retained)
        self.assertEqual(rebuilt["coverage"],dict(kinds=sorted(campaign.KINDS),records=47,rejections=82,validations=29,text_cases=10,pretty_cases=50))

    def test_provenance_changes_artifact_without_inventing_nominal_chemistry(self):
        records={item["id"]:item for item in self.corpus["records"]}
        plain,declared=records["chemistry_plain"],records["chemistry_declared_provenance"]
        self.assertNotEqual(plain["fingerprint"],declared["fingerprint"])
        self.assertEqual(plain["nominal"],declared["nominal"])
        self.assertTrue(plain["declared_nominal_complete"])
        self.assertFalse(records["chemistry_unknown_inventory"]["declared_nominal_complete"])
        self.assertEqual(records["modification_positions"]["nominal"]["canonical_base"],"A")
        self.assertNotEqual(records["modification_positions"]["nominal"],records["modification_policy"]["nominal"])

    def test_bad_nominal_identity_and_completeness_are_rejected(self):
        for field,value,message in (("fingerprint","0"*64,"fingerprint"),("nominal",{},"nominal content"),("declared_nominal_complete",True,"completeness")):
            changed=deepcopy(self.corpus);changed["records"][0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(AssertionError,message):campaign.check_corpus(changed)

    def test_shape_rejection_cannot_be_replaced_with_a_valid_record(self):
        changed=deepcopy(self.corpus)
        kind=changed["rejections"][0]["kind"]
        changed["rejections"][0]["input"]=next(item["normalized"] for item in changed["records"] if item["kind"]==kind)
        with self.assertRaisesRegex(AssertionError,"Accepted intended chemistry decode rejection"):campaign.check_corpus(changed)

    def test_context_rejections_are_not_decoder_rejections(self):
        changed=deepcopy(self.corpus)
        case=next(item for item in changed["validations"] if item["id"]=="invalid_tail_frame")
        case["expected_code"]=None
        with self.assertRaisesRegex(AssertionError,"Unexpected chemistry validation failure"):campaign.check_corpus(changed)
        for item in self.corpus["validations"]:
            source=next(record for record in self.corpus["records"] if record["id"]==item["chemistry_id"])
            campaign.MoleculeChemistry.from_dict(source["normalized"])
            campaign.CoordinateSpace.from_dict(item["space"])

    def test_pretty_byte_corpus_covers_every_supported_indent(self):
        self.assertEqual({item["indent"] for item in self.corpus["pretty_cases"]},{None,*range(9)})
        changed=deepcopy(self.corpus);changed["pretty_cases"][0]["bytes"]+=1
        with self.assertRaisesRegex(AssertionError,"pretty byte size"):campaign.check_corpus(changed)
        changed=deepcopy(self.corpus);changed["text_cases"][0]["accepted"]=False
        with self.assertRaisesRegex(AssertionError,"text acceptance"):campaign.check_corpus(changed)

    def test_molecular_resource_contract_literals_match_native_test_limits(self):
        _bounded_tree([None]*99_999)
        with self.assertRaises(SerializationError):_bounded_tree([None]*100_000)
        _bounded_tree(1<<4095)
        with self.assertRaises(SerializationError):_bounded_tree(1<<4096)
        value=None
        for _ in range(96):value=[value]
        _bounded_tree(value)
        with self.assertRaises(SerializationError):_bounded_tree([value])
        escaped="\u0001"*700_000
        _bounded_tree(escaped)
        self.assertGreater(len(json.dumps(escaped,ensure_ascii=False,indent=2).encode())+1,4_000_000)

    def test_missing_case_cannot_hide_in_recomputed_coverage(self):
        changed=deepcopy(self.corpus);changed["rejections"].pop();changed["coverage"]=campaign.census(changed)
        with self.assertRaisesRegex(AssertionError,"Missing mandatory chemistry cases"):campaign.check_corpus(changed)

    def test_check_mode_cannot_create_missing_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"missing.json"
            with self.assertRaises(FileNotFoundError):campaign.main(["--output",str(output)])
            self.assertFalse(output.exists())


if __name__=="__main__":unittest.main()
