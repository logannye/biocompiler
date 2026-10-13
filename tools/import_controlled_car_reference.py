"""Replay the recorded controlled-CAR acquisition using explicit local inputs.

This offline maintainer tool emits only an inert, deterministic fragment receipt.
It does not emit RNA, qualify behavior, authenticate a publication, or grant reuse
rights. The tracked inventory pins both original PDFs and same-operator manual
entries; fresh consistency checks do not prove that those entries match pixels.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data/car_controlled_reference/source-inventory.json"
REFERENCE = "WO2014127261A1-197-206"
PDFS = ("wu-linked-patent-WO2014127261A1.pdf", "patent-us-publication.pdf")
ENTRIES = ("patent-domain-transcription.json", "patent-listing-transcription.json")
INPUTS = PDFS + ENTRIES
MAX_BYTES = 25 * 1024 * 1024
MAX_JSON_BYTES = 256 * 1024
LENGTHS = {1: 63, 3: 30, 5: 726, 7: 207, 11: 324, 15: 30, 17: 336,
           19: 30, 21: 708, 23: 126, 27: 144, 29: 72, 31: 48, 33: 279}
ORDER = {"197": ["1", "3", "5", "7", "197-short-linker", "23", "19", "11"],
         "206": ["27", "29", "206-short-linker", "23", "31", "33", "15", "17", "19", "21"]}
TABLE = dict(zip(map("".join, itertools.product("TCAG", repeat=3)),
                 "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"))


class ImportRejected(ValueError):
    """An incomplete, changed, malformed, or unsafe input cannot be imported."""


def require(condition, message):
    if not condition:
        raise ImportRejected(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON object key: " + key)
        result[key] = value
    return result


def decode(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_JSON_BYTES, "JSON byte limit")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                           parse_constant=lambda _: require(False, "Nonfinite JSON number"))
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        raise ImportRejected("Invalid bounded JSON: " + str(error)) from error
    stack = [(value, 0)]
    count = 0
    while stack:
        item, depth = stack.pop()
        count += 1
        require(count <= 20000 and depth <= 20, "JSON structure limit")
        if type(item) is dict:
            stack.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            stack.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            require(len(item) <= 16384 and not any(0xD800 <= ord(c) <= 0xDFFF for c in item),
                    "Invalid or oversized JSON text")
        else:
            require(item is None or type(item) in (bool, int), "Unsupported JSON scalar")
    return value


def fields(value, expected, label):
    require(type(value) is dict and set(value) == set(expected), label + ": exact fields required")


def text(value, label):
    require(type(value) is str and bool(value.strip()), label + ": nonempty text required")


def _read(path, maximum, *, directory_fd=None):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= maximum,
                "Input must be a nonempty bounded regular file")
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    require(len(raw) == before.st_size <= maximum and
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "Input changed during reading")
    return raw


def authority(raw):
    inventory = decode(raw)
    require(type(inventory) is dict and inventory.get("schema") ==
            "biocompiler.car_controlled_reference.source_inventory.v0.1" and
            inventory.get("selected_acquisition_reference") == REFERENCE, "Unsupported acquisition inventory")
    contract = inventory.get("authorized_input_import_contract")
    require(type(contract) is dict and contract.get("original_authority") == list(INPUTS),
            "Inventory must retain exactly the four recorded original inputs")
    sources, artifacts = inventory.get("sources"), inventory.get("local_material_artifacts")
    require(type(sources) is list and type(artifacts) is list, "Missing acquisition pin inventories")
    pins = {}
    for name in INPUTS:
        if name in PDFS:
            matches = [row for row in sources if type(row) is dict and row.get("id") == name]
        else:
            matches = [row for row in artifacts if type(row) is dict and
                       row.get("path") == "generated/car-controlled-composition/reference-acquisition/" + name]
        require(len(matches) == 1, "Missing or duplicate independent input pin: " + name)
        row = matches[0]
        size, sha = row.get("size_bytes"), row.get("sha256")
        require(type(size) is int and 0 < size <= (MAX_BYTES if name in PDFS else MAX_JSON_BYTES),
                "Invalid pinned size: " + name)
        require(type(sha) is str and re.fullmatch("[0-9a-f]{64}", sha), "Invalid input hash: " + name)
        pins[name] = {"size_bytes": size, "sha256": sha}
    require(sum(row["size_bytes"] for row in pins.values()) <= MAX_BYTES, "Aggregate input byte limit")
    return pins


def translate(dna):
    require(type(dna) is str and bool(dna) and set(dna) <= set("ACGT") and len(dna) % 3 == 0,
            "Incomplete codons or invalid DNA alphabet")
    return "".join(TABLE[dna[i:i + 3]] for i in range(0, len(dna), 3))


def reconstruct(figures, listing, pins):
    """Fresh literal reconstruction; no saved receipt is consulted."""
    fields(figures, ("schema", "reference", "source_sha256", "status", "normalization", "records",
                     "construct_block_order", "not_supplied"), "Figure entry")
    fields(listing, ("schema", "source", "source_sha256", "status", "independence_limit", "records"), "Listing entry")
    require(figures["schema"] == "biocompiler.car_controlled_reference.manual_figure_transcription.v0.1" and
            figures["reference"] == REFERENCE and listing["schema"] ==
            "biocompiler.car_controlled_reference.manual_listing_transcription.v0.1" and
            listing["source"] == "US20150368342A1", "Transcription identity differs")
    require(figures["source_sha256"] == pins[PDFS[0]]["sha256"] and
            listing["source_sha256"] == pins[PDFS[1]]["sha256"], "Transcription source pin differs")
    require(figures["construct_block_order"] == ORDER, "Explicit source block order differs")
    require(figures["not_supplied"] == ["stop codons", "RNA context", "RNA chemistry", "full plasmid/vector"],
            "Missing-material declarations differ")
    for record, keys in ((figures, ("status", "normalization")), (listing, ("status", "independence_limit"))):
        for key in keys:
            text(record[key], key)
    require(type(figures["records"]) is list and len(figures["records"]) == 16 and
            type(listing["records"]) is list and len(listing["records"]) == 14, "Exact record census required")
    fs, ls = {}, {}
    for record in listing["records"]:
        fields(record, ("dna_seq_id", "printed_length", "pdf_page_one_based", "grouped_text", "dna"), "Listing record")
        identity = record["dna_seq_id"]
        require(type(identity) is int and identity in LENGTHS and identity not in ls, "Listing IDs differ or repeat")
        require(type(record["printed_length"]) is int and record["printed_length"] == LENGTHS[identity], "Printed length differs")
        require(type(record["pdf_page_one_based"]) is int and 93 <= record["pdf_page_one_based"] <= 103,
                "Listing page outside reviewed range")
        text(record["grouped_text"], "Listing text")
        require(record["dna"] == "".join(record["grouped_text"].split()).upper(), "Listing normalization differs")
        ls[identity] = record
    for record in figures["records"]:
        fields(record, ("id", "dna_seq_id", "protein_seq_id", "pdf_page_one_based", "figure", "label",
                        "dna_figure_text", "protein_figure_text", "dna", "protein"), "Figure record")
        identity = record["id"]
        require(type(identity) is str and identity in {str(n) for n in LENGTHS} |
                {"197-short-linker", "206-short-linker"} and identity not in fs, "Figure IDs differ or repeat")
        require(type(record["pdf_page_one_based"]) is int and 90 <= record["pdf_page_one_based"] <= 94,
                "Figure page outside reviewed range")
        for key in ("figure", "label", "dna_figure_text", "protein_figure_text"):
            text(record[key], key)
        dna, protein = record["dna"], record["protein"]
        require(dna == "".join(record["dna_figure_text"].split()).upper() and
                protein == "".join(record["protein_figure_text"].split()).upper(), "Literal normalization differs")
        require(type(protein) is str and set(protein) <= set("ACDEFGHIKLMNPQRSTVWY") and
                translate(dna) == protein, "Printed protein translation differs")
        n = record["dna_seq_id"]
        if identity.endswith("-short-linker"):
            require(n is None and record["protein_seq_id"] is None and len(dna) == 6 and protein == "SL",
                    "Unnumbered linker differs")
        else:
            require(type(n) is int and identity == str(n) and type(record["protein_seq_id"]) is int and
                    record["protein_seq_id"] == n + 1, "Paired sequence IDs differ")
            require(len(dna) == LENGTHS[n] and dna == ls[n]["dna"], "Figure/listing DNA differs")
        fs[identity] = record
    require(fs["197-short-linker"]["dna"] != fs["206-short-linker"]["dna"], "Distinct linkers collapsed")
    products = []
    for construct, order in ORDER.items():
        dna = "".join(fs[n]["dna"] for n in order)
        protein = "".join(fs[n]["protein"] for n in order)
        require(dna.startswith("ATG") and translate(dna) == protein and "*" not in protein, "Product boundary or translation differs")
        spans, cursor = [], 0
        for identity in order:
            end = cursor + len(fs[identity]["dna"])
            spans.append({"block_id": identity, "dna_start_zero_based": cursor, "dna_end_exclusive": end})
            cursor = end
        products.append({"construct": construct, "dna_nt": len(dna), "protein_aa": len(protein),
                         "dna_sha256": digest(dna.encode()), "protein_sha256": digest(protein.encode()),
                         "spans": spans, "stop_codon_present": False})
    components = [{"id": n, "dna_nt": len(fs[n]["dna"]), "protein_aa": len(fs[n]["protein"]),
                   "dna_sha256": digest(fs[n]["dna"].encode()), "protein_sha256": digest(fs[n]["protein"].encode())}
                  for n in sorted(fs)]
    return components, products


def load_inputs(input_root, *, inventory_path=INVENTORY):
    """Return freshly pinned immutable input bytes for one bounded invocation."""
    inventory_raw = _read(inventory_path, MAX_JSON_BYTES)
    pins = authority(inventory_raw)
    root = Path(input_root)
    require(not root.is_symlink(), "Input root cannot be a symbolic link")
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        inputs = {name: _read(name, pins[name]["size_bytes"], directory_fd=descriptor) for name in INPUTS}
    finally:
        os.close(descriptor)
    # Every source and transcription is pinned before either transcription is parsed.
    for name, raw in inputs.items():
        require(len(raw) == pins[name]["size_bytes"] and digest(raw) == pins[name]["sha256"], "Original input pin differs: " + name)
        require(name not in PDFS or raw.startswith(b"%PDF-"), "Original source lacks PDF signature")
    return inventory_raw, pins, inputs


def inspect(input_root, *, inventory_path=INVENTORY):
    inventory_raw, pins, inputs = load_inputs(input_root, inventory_path=inventory_path)
    components, products = reconstruct(*(decode(inputs[name]) for name in ENTRIES), pins)
    report = {"schema": "biocompiler.controlled_car_fragment_import.v0.1", "reference": REFERENCE,
              "status": "fresh_literal_material_consistency_only", "input_pins": pins,
              "inventory_sha256": digest(inventory_raw), "checker_sha256": digest(Path(__file__).read_bytes()),
              "components": components, "products": products,
              "source_bytes": "matched_to_recorded_inventory", "source_authenticity": "unassessed",
              "acquisition_limit": "Same-operator manual double entry; visual source reading remains trusted.",
              "distribution_status": "unassessed_local_authorized_input_only", "is_rna_design": False,
              "is_admitted_molecular_pack": False, "native_status": "not_run", "biological_status": "unassessed",
              "human_use_status": "not_assessed", "wu_publication_pair_identity": "not_established",
              "missing_rna_design": ["termination", "complete transcript regions and ordering", "cap/end chemistry",
                                     "nucleotide modifications", "tail", "recipient/co-delivery and availability",
                                     "independent activity/control/observation contract"]}
    encoded = (json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    require(len(encoded) <= MAX_JSON_BYTES, "Output receipt byte limit")
    return encoded


def publish(raw, output):
    """Stage complete bytes, then publish atomically without replacing any path."""
    output = Path(output)
    require(not output.exists() and not output.is_symlink(), "Output already exists")
    descriptor, temporary = tempfile.mkstemp(prefix=".controlled-car-import-", dir=output.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output, follow_symlinks=False)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path, help="Directory containing the four recorded authorized local inputs")
    parser.add_argument("--output", required=True, type=Path, help="New metadata receipt; parent directory must exist")
    args = parser.parse_args(argv)
    try:
        publish(inspect(args.inputs), args.output)
    except (ImportRejected, OSError) as error:
        print("Controlled CAR import rejected: " + str(error), file=sys.stderr)
        return 1
    print("Fresh fragment consistency receipt written; complete RNA and biological behavior remain unassessed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
