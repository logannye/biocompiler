#!/usr/bin/env python3
"""Offline factual-source comparison, never compiler or biological acceptance.

The supplied XML must be the complete pinned public WIPO original. The reference
JSON cannot supply its own expected identities, coordinate system, or claims.
No network, product imports, native execution, or previous assessment is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterator, NoReturn, cast


SCHEMA = "biocompiler.car_rm61461_reference.v0.1"
REPORT_SCHEMA = "biocompiler.car_rm61461_source_consistency.v0.1"
MAX_XML_BYTES = 1_048_576
MAX_XML_NODES = 12_000
MAX_XML_DEPTH = 16
MAX_SEQUENCES = 512
MAX_SEQUENCE_LENGTH = 20_000
MAX_PACK_BYTES = 131_072
MAX_JSON_NODES = 4_096
OMITTED_SEQUENCE_IDS = {9, 10, 244, 296}
XML_NAME = "23-1871-WO_SequenceListing.xml"
XML_SHA256 = "7df4fd171f285adc6e5d0b37442a8bc77ab1b28c275b04a52c822ed15e7b938e"
XML_BYTES = 669_450
ZIP_URL = "https://www.wipo.int/published_pct_sequences/publication/2025/0508/WO25_096878/WO2025-096878-TAB-20241115-001.zip"
PDF_URL = "https://patentimages.storage.googleapis.com/aa/28/2d/e21333e54fee5a/WO2025096878A9.pdf"
DOCTYPE = '<!DOCTYPE ST26SequenceListing PUBLIC "-//WIPO//DTD Sequence Listing 1.3//EN" "ST26SequenceListing_V1_3.dtd">'

# Independently reviewed original literal identities; lowercase ST.26 RNA text
# remains distinct from the explicitly converted uppercase RNA display text.
SEQUENCE_PINS = {
    2: ("AA", 485, "833bd17e675e9595d01865a0109c9c795d2ba8b78481ab06f12da043019e404d"),
    11: ("RNA", 79, "98c92e9f43c45c6519c3d3fb4b1f79f9e2e5a68937897f85899a28ee68aa884f"),
    34: ("RNA", 126, "c942e06e4e3dcf5697de9776d97fc776bff7f532abd89221caf48a579b954f49"),
    65: ("RNA", 1461, "1957daeb1aa469beb9734bc9b087d4808482a69c6161e774fc01305bf847ce66"),
    101: ("RNA", 1455, "427ae16db5827cf3edef611b5549cfcf86dcab117596556bb9e5d0481b8a7f47"),
    151: ("RNA", 1776, "6b37aa3ffd966eba206f4cc465e1f20ae62bbb2b658c0a041527cb4d12b58f0e"),
}

# NCBI standard genetic code, table 1, in fixed T/C/A/G lexical base order.
# This independent constant is not read from the reference or an optimizer.
CODON_AMINO_ACIDS = (
    "FFLLSSSSYY**CC*W" "LLLLPPPPHHQQRRRR"
    "IIIMTTTTNNKKSSRR" "VVVVAAAADDEEGGGG"
)
CODON_TABLE = dict(zip(
    (a + b + c for a in "TCAG" for b in "TCAG" for c in "TCAG"),
    CODON_AMINO_ACIDS,
))
STANDARD_CODE_SHA256 = "bef1a40d752e3d2fabb4df27de6a194c598a274be08b2b958d30632a22d18ae7"


class ReferenceError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> NoReturn:
    raise ReferenceError(code, message)


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: Any) -> bytes:
    """Bound JSON before encoding; reject non-JSON Python values and NaN."""
    stack = [(value, 0)]
    visits = 0
    while stack:
        item, depth = stack.pop()
        visits += 1
        if visits > MAX_JSON_NODES or depth > 16:
            fail("reference_limit", "Reference JSON exceeds its closed resource bounds.")
        if type(item) is dict:
            if len(item) > MAX_JSON_NODES:
                fail("reference_limit", "Reference object has too many fields.")
            for key, child in item.items():
                if type(key) is not str or len(key) > 256:
                    fail("reference_json", "Reference keys must be bounded strings.")
                visits += 1
                stack.append((child, depth + 1))
        elif type(item) is list:
            if len(item) > MAX_JSON_NODES:
                fail("reference_limit", "Reference array has too many entries.")
            stack.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            if len(item) > MAX_SEQUENCE_LENGTH:
                fail("reference_limit", "Reference string exceeds its bound.")
        elif item is not None and type(item) not in (bool, int, float):
            fail("reference_json", "Reference contains a non-JSON value.")
        elif type(item) is int and item.bit_length() > 64:
            fail("reference_limit", "Reference integer exceeds its bound.")
    try:
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=True,
                             allow_nan=False, separators=(",", ":")).encode("ascii")
    except (ValueError, TypeError, OverflowError) as error:
        fail("reference_json", str(error))
    if len(encoded) > MAX_PACK_BYTES:
        fail("reference_limit", "Reference JSON exceeds its byte bound.")
    return encoded


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail("reference_json", "Duplicate reference JSON field.")
        result[key] = value
    return result


def load_pack(raw: bytes) -> Any:
    if len(raw) > MAX_PACK_BYTES:
        fail("reference_limit", "Reference input exceeds its byte bound.")
    try:
        value = json.loads(raw, object_pairs_hook=_pairs)
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, ReferenceError):
            raise
        fail("reference_json", str(error))
    canonical(value)
    return value


def parse_listing(raw: bytes) -> dict[int, tuple[str, str]]:
    """Bounded inert parser, without authenticity or acceptance authority.

    The one known external DOCTYPE declaration is removed before parsing; it is
    never fetched. Custom/internal entities, numeric entity references and all
    other declarations are rejected. Predefined XML escapes remain permitted.
    """
    if type(raw) is not bytes or len(raw) > MAX_XML_BYTES:
        fail("xml_limit", "Original XML exceeds its byte bound.")
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        fail("xml_parse", "Only the original UTF-8 XML encoding is supported.")
    if text.count(DOCTYPE) > 1:
        fail("xml_parse", "Duplicate XML document declaration.")
    text = text.replace(DOCTYPE, "")
    if "<!" in text or re.search(r"&(?!amp;|apos;|quot;|lt;|gt;)", text):
        fail("xml_entities", "DTD declarations and custom/entity expansions are forbidden.")
    declaration = '<?xml version="1.0" encoding="UTF-8"?>'
    if "<?" in text.removeprefix(declaration):
        fail("xml_parse", "Unexpected XML processing instruction.")
    parser = ET.XMLPullParser(events=("start", "end"))
    root: ET.Element[str] | None = None
    depth = 0
    nodes = 0
    try:
        for offset in range(0, len(text), 4096):
            parser.feed(text[offset:offset + 4096])
            # Only start/end events were requested; namespace-event payloads in
            # ElementTree's broader stub union cannot occur in this parser.
            events = cast("Iterator[tuple[str, ET.Element[str]]]", parser.read_events())
            for event, element in events:
                if event == "start":
                    depth += 1
                    nodes += 1
                    if root is None:
                        root = element
                    if depth > MAX_XML_DEPTH or nodes > MAX_XML_NODES:
                        fail("xml_limit", "Original XML exceeds node/depth bounds.")
                else:
                    if len(element.text or "") > MAX_SEQUENCE_LENGTH:
                        fail("xml_limit", "Original XML text exceeds its bound.")
                    depth -= 1
        parser.close()
    except ET.ParseError as error:
        fail("xml_parse", str(error))
    if root is None or root.tag != "ST26SequenceListing":
        fail("xml_shape", "Expected the original ST.26 listing root.")
    counts = root.findall("SequenceTotalQuantity")
    if len(counts) != 1 or not re.fullmatch(r"[1-9][0-9]{0,2}", counts[0].text or ""):
        fail("xml_shape", "Missing or duplicated listing sequence count.")
    elements = root.findall("SequenceData")
    if len(elements) > MAX_SEQUENCES or int(counts[0].text or "0") != len(elements):
        fail("xml_shape", "Listing sequence count does not match its complete inventory.")
    result: dict[int, tuple[str, str]] = {}
    for element in elements:
        identity = element.get("sequenceIDNumber", "")
        if not re.fullmatch(r"[1-9][0-9]{0,2}", identity):
            fail("xml_shape", "Invalid sequence identity.")
        sequence_id = int(identity)
        if sequence_id in result:
            fail("xml_duplicate", "Duplicate sequence identity.")
        bodies = element.findall("INSDSeq")
        if len(bodies) != 1:
            fail("xml_shape", "Missing or duplicate sequence body.")
        body = bodies[0]
        fields: dict[str, str] = {}
        for field in ("INSDSeq_length", "INSDSeq_moltype", "INSDSeq_sequence"):
            values = body.findall(field)
            if len(values) != 1:
                fail("xml_shape", "Missing or duplicate required sequence field.")
            fields[field] = values[0].text or ""
        sequence = fields["INSDSeq_sequence"]
        length = fields["INSDSeq_length"]
        if sequence == "000" and length == "" and fields["INSDSeq_moltype"] == "":
            result[sequence_id] = ("omitted", "000")
            continue
        if not re.fullmatch(r"[1-9][0-9]{0,4}", length) or int(length) != len(sequence):
            fail("xml_shape", "Declared sequence length differs from original literal.")
        result[sequence_id] = (fields["INSDSeq_moltype"], sequence)
    return result


def _source_sequences(raw: bytes) -> dict[int, tuple[str, str]]:
    if type(raw) is not bytes or len(raw) > MAX_XML_BYTES:
        fail("xml_limit", "Original XML exceeds its byte bound.")
    if len(raw) != XML_BYTES or sha256(raw) != XML_SHA256:
        fail("xml_identity", "Complete original WIPO XML identity differs.")
    sequences = parse_listing(raw)
    if len(sequences) != 401 or set(sequences) != set(range(1, 402)):
        fail("xml_inventory", "Original listing must contain the complete 401-sequence inventory.")
    if {key for key, value in sequences.items() if value[0] == "omitted"} != OMITTED_SEQUENCE_IDS:
        fail("xml_inventory", "Original omitted-entry inventory differs.")
    return sequences


def _selected_records(sequences: dict[int, tuple[str, str]]) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for identity, (moltype, length, digest) in SEQUENCE_PINS.items():
        if identity not in sequences:
            fail("sequence_identity", "A required original sequence is missing.")
        actual_type, literal = sequences[identity]
        if (actual_type != moltype or len(literal) != length
                or sha256(literal.encode("utf-8")) != digest):
            fail("sequence_identity", "A selected sequence differs from its independent original pin.")
        record: dict[str, Any] = {"sequence_id": identity, "moltype": moltype,
                                  "length": length, "original_literal": literal,
                                  "original_literal_sha256": digest}
        if moltype == "RNA":
            if not re.fullmatch("[acgt]+", literal):
                fail("sequence_alphabet", "Selected RNA must preserve original ST.26 spelling.")
            rna = literal.upper().replace("T", "U")
            record.update(rna_sequence=rna, rna_sha256=sha256(rna.encode("ascii")))
        records[str(identity)] = record
    return records


def _check_arithmetic(records: dict[str, Any]) -> None:
    actual_code = "".join(CODON_TABLE[a + b + c]
                          for a in "TCAG" for b in "TCAG" for c in "TCAG")
    if sha256(actual_code.encode("ascii")) != STANDARD_CODE_SHA256:
        fail("genetic_code_identity", "Independent standard-code table differs from its fixed pin.")
    raw = {key: record["original_literal"].upper() for key, record in records.items()}
    full = raw["151"]
    checks = [full[:79] == raw["11"], full[79:1534] == raw["101"],
              full[79:1540] == raw["65"], full[1540:1666] == raw["34"],
              full[1666:] == "A" * 110, len(full) == 1776,
              len(full) - len(full.rstrip("A")) == 111,
              full[:10] == "AGCATAAAAG",
              CODON_TABLE[full[1534:1537]] == "*",
              CODON_TABLE[full[1537:1540]] == "*"]
    protein = "".join(CODON_TABLE[raw["101"][i:i + 3]] for i in range(0, 1455, 3))
    if not all(checks) or protein != raw["2"] or "*" in protein:
        fail("sequence_correspondence", "Published part/stop/cap-prefix/protein correspondence differs.")


def _expected_pack(records: dict[str, Any]) -> dict[str, Any]:
    """Closed reviewed facts; reference input cannot widen these claim scopes."""
    return {
        "schema_version": SCHEMA,
        "reference_id": "WO2025096878A9:RM_61461:SEQ151",
        "scope": {
            "kind": "nominal_published_reference",
            "publication": "WO2025096878A9",
            "a1_equivalence": "unassessed",
            "correction_notice_scope": "unassessed",
            "product_target": "human_immune_cells_in_vivo",
            "reference_antigen": "CD19",
            "product_antigen_selection": "not_selected_by_this_reference",
            "product_indication_selection": "not_selected_by_this_reference",
        },
        "sources": {
            "pdf": {"url": PDF_URL, "bytes": 17_210_052,
                    "sha256": "e95bc99f5cc4f9c69d4ca4a40590fb437b17980b93f5a2f7a18e794ca5b9b2da",
                    "provenance": "public_patent_document_mirror", "verified_by_this_checker": False},
            "zip": {"url": ZIP_URL, "bytes": 50_876,
                    "sha256": "9ea75052596054c5301fd000ea39a60cbb3b024499c0213c075428bafc417092",
                    "provenance": "official_wipo_public_sequence_archive", "verified_by_this_checker": False},
            "xml": {"archive_url": ZIP_URL, "member": XML_NAME, "bytes": XML_BYTES,
                    "sha256": XML_SHA256, "provenance": "official_wipo_archive_member",
                    "source_join": "A9 paragraph [0002]: filename, 2024-10-28 creation date, 669450 bytes",
                    "verified_by_this_checker": True},
        },
        "source_records": records,
        "listing_inventory": {"entry_count": 401, "sequence_count": 397,
                              "omitted_sequence_ids": [9, 10, 244, 296]},
        "transcript": {
            "source_sequence_id": 151, "length": 1776,
            "literal_conversion": "preserve_original_then_uppercase_and_replace_T_with_U",
            "conversion_authority": "WIPO ST.26: RNA uracil is represented by t",
            "conversion_url": "https://www.wipo.int/en/web/pct-system/w/news/2022/news_0039",
            "coordinates": "zero_based_half_open",
            "regions": [
                {"role": "five_prime_utr", "name": "mHBB", "start": 0, "end": 79, "sequence_id": 11},
                {"role": "orf_excluding_stops", "name": "CAR2-OPT4", "start": 79, "end": 1534, "sequence_id": 101},
                {"role": "double_stop", "start": 1534, "end": 1540, "contained_in_sequence_id": 65},
                {"role": "three_prime_utr", "name": "PNLIP-RPS3A", "start": 1540, "end": 1666, "sequence_id": 34},
                {"role": "encoded_poly_a", "start": 1666, "end": 1776, "length": 110},
            ],
            "terminal_a_run": 111,
            "terminal_a_run_explanation": "The final A of SEQ34 precedes the encoded 110-A tail.",
        },
        "protein": {"name": "CAR2", "sequence_id": 2, "length": 485,
                    "signal_peptide_included": True, "genetic_code": "NCBI_standard_table_1",
                    "genetic_code_table_sha256": STANDARD_CODE_SHA256,
                    "genetic_code_url": "https://www.ncbi.nlm.nih.gov/Taxonomy/Utils/wprintgc.cgi#SG1",
                    "meaning": "nominal_coding_identity_only"},
        "nominal_chemistry": {
            "cap": {"kind": "Cap1", "source_reagent": "Cap-AG",
                    "source_structure": "m7G(5')ppp(5')(2'OMeA)pG", "anchor": "A9 [00408]",
                    "provenance": "source_declared", "batch_verified": False,
                    "prefix_match": "listed_transcript_already_starts_AG_no_added_initiator_bases"},
            "nucleotides": {"replacement": "all_uridine_by_N1_methylpseudouridine",
                            "anchor": "A9 [00408]", "provenance": "source_declared",
                            "batch_verified": False},
            "three_prime_end": {"identity": None, "provenance": "unreported_in_qualified_source",
                                "designer_choice": None},
        },
        "evidence": [
            {"kind": "expression", "status": "source_disclosed_not_independently_validated",
             "context": "primary_human_T_cells_ex_vivo_expanded_and_freshly_activated",
             "anchors": ["A9 Examples 1 and 2", "A9 Figure 5H"],
             "delivery_context": "source_CD5_targeted_LNP", "human_in_vivo": False},
            {"kind": "function", "status": "source_disclosed_with_donor_conflict",
             "context": "human_T_cells_ex_vivo_Nalm6_coculture",
             "anchors": ["A9 Example 3", "A9 Figure 10"],
             "donor": None,
             "donor_conflict": {"donor_3": ["A9 [00414]", "A9 [00451]"], "donor_4": ["A9 [0030]"]},
             "readout": "source_labeled_residual_Nalm6_readout_not_general_efficacy",
             "human_in_vivo": False},
        ],
        "applicability": {
            "human_T_cell_source_context": "source_disclosed",
            "human_in_vivo_delivery": "unassessed", "clinical_benefit": "unassessed",
            "safety": "unassessed", "physical_material_reproduction": "unassessed",
            "raw_data_and_independent_replication": "unassessed",
            "capping_fraction_and_tail_distribution": "unassessed",
            "source_parts_may_have_nonhuman_origin": True,
        },
        "access_and_reuse": {
            "public_unauthenticated_retrieval": "observed",
            "affirmative_content_reuse_license": "not_identified_in_this_review",
            "patent_permission": "not_assessed", "legal_conclusion": None,
            "pdf_redistributed_in_pack": False,
        },
        "acceptance": {"compiler": False, "material": False, "empirical": False,
                       "clinical": False, "manufacturing": False},
    }


def _check_pack_contents(pack: Any, sequences: dict[int, tuple[str, str]]) -> None:
    records = _selected_records(sequences)
    _check_arithmetic(records)
    if canonical(pack) != canonical(_expected_pack(records)):
        fail("reference_mismatch", "Complete reference differs from the reviewed facts, original sequences or claim scope.")


def check_reference(pack: Any, original_xml: bytes) -> dict[str, Any]:
    """Freshly compare supplied original bytes and complete reference facts."""
    encoded = canonical(pack)
    sequences = _source_sequences(original_xml)
    _check_pack_contents(pack, sequences)
    return {
        "schema_version": REPORT_SCHEMA,
        "status": "consistent",
        "claim": "pinned_original_source_and_closed_nominal_reference_correspondence",
        "reference_sha256": sha256(encoded),
        "original_xml_sha256": sha256(original_xml),
        "original_xml_bytes": len(original_xml),
        "source_entry_count": len(sequences),
        "source_sequence_count": len(sequences) - len(OMITTED_SEQUENCE_IDS),
        "omitted_sequence_ids": sorted(OMITTED_SEQUENCE_IDS),
        "checked_sequence_ids": sorted(SEQUENCE_PINS),
        "xml_authenticated_by_complete_bytes": True,
        "pdf_and_zip_bytes_checked_this_invocation": False,
        "native_execution": False, "network_access": False,
        "compiler_acceptance": False, "material_acceptance": False,
        "empirical_acceptance": False, "clinical_acceptance": False,
        "manufacturing_acceptance": False,
        "unresolved": ["three_prime_terminal_chemistry", "functional_assay_donor_conflict",
                       "historical_correction_scope", "actual_material_quality",
                       "raw_data_and_independent_replication", "reuse_permissions",
                       "human_in_vivo_delivery_safety_and_benefit"],
    }


def _read(path: Path, maximum: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
            fail("input_limit", "Supplied input must be a bounded regular file.")
        data = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    if (len(data) > maximum or len(data) != before.st_size
            or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
        fail("input_limit", "Supplied file exceeds its bound or changed during reading.")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--xml", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = check_reference(load_pack(_read(args.pack, MAX_PACK_BYTES)),
                                 _read(args.xml, MAX_XML_BYTES))
        code = 0
    except (ReferenceError, OSError) as error:
        report = {"schema_version": REPORT_SCHEMA, "status": "rejected",
                  "code": error.code if isinstance(error, ReferenceError) else "input_io",
                  "detail": str(error), "compiler_acceptance": False,
                  "material_acceptance": False, "empirical_acceptance": False,
                  "clinical_acceptance": False, "manufacturing_acceptance": False}
        code = 1
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        if (args.output.resolve() in {args.pack.resolve(), args.xml.resolve()}
                or (args.output.exists() and any(source.exists() and
                    os.path.samefile(args.output, source) for source in (args.pack, args.xml)))):
            parser.error("Report output must not overwrite either original input.")
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
