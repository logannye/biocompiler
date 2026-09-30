"""Reconstruct two reviewed source-literal components; never admit a payload.

The trusted input is the reviewed, pinned checkout. These hashes detect changes
within that provenance chain, not scientific truth or authenticated reviewers.
"""

import hashlib
from pathlib import Path, PurePosixPath
import sys

from biocompiler.ir.serialization import fields, fingerprint, parse_json, require
from biocompiler.registry.references import normalize_sequence


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = Path("data/evidence/m11-material-reconciliation")
ROWS = {
    "allen-gal4uas": ("DNA", "regulatory_dna", "raw/allen-gal4uas.txt"),
    "allen-human-il2": ("protein", "protein_component", "raw/allen-human-il2.txt"),
}
CLAIMS = dict.fromkeys(
    ("complete_molecule", "exact_experimental_material", "quantitative_secretion_rate",
     "model_validation", "human_admission"), False,
)


def sha(content):
    return hashlib.sha256(content).hexdigest()


def hash_value(value):
    require(isinstance(value, str) and len(value) == 64
            and set(value) <= set("0123456789abcdef"), "Invalid SHA-256")


def read_bytes(directory, name):
    path = PurePosixPath(name)
    require(isinstance(name, str) and name == path.as_posix()
            and not path.is_absolute() and ".." not in path.parts
            and "\\" not in name, "Unsafe evidence path")
    target = directory
    for part in path.parts:
        target = target / part
        require(not target.is_symlink(), "Evidence symlinks are forbidden")
    require(target.is_file() and target.stat().st_size <= 1_000_000,
            "Missing or oversized evidence input")
    return target.read_bytes()


def strings(values):
    return isinstance(values, list) and bool(values) and all(
        isinstance(value, str) and value.strip() for value in values)


def check_context(authority):
    correction = authority["source"]["correction"]
    fields(correction, {"date", "url", "scope", "supplement_relationship"}, "correction")
    require(strings(list(correction.values())), "Missing correction details")
    require(correction["url"].startswith("https://"), "Invalid correction URL")
    require(strings(authority["limitations"]), "Missing component limitations")
    for key in ("correspondence", "observations"):
        require(isinstance(authority[key], list) and len(authority[key]) == 1,
                "Wrong bounded context inventory")
    relation = authority["correspondence"][0]
    unresolved = {"complete_nucleotide_record", "exact_measured_preparation",
                  "mature_product_boundaries", "delivered_artifact_identity"}
    descriptions = {"id", "locator", "source_construct_label", "relationship", "material_class"}
    fields(relation, descriptions | unresolved | {"source_ordered_elements", "component_ids"},
           "component correspondence")
    require(strings([relation[key] for key in descriptions])
            and strings(relation["source_ordered_elements"]), "Missing correspondence details")
    require(strings(relation["component_ids"]) and len(relation["component_ids"]) == len(ROWS)
            and set(relation["component_ids"]) == set(ROWS), "Wrong associated components")
    require(all(relation[key] is None for key in unresolved), "Material joins remain unresolved")
    observation = authority["observations"][0]
    unknown = {"recipient_organism", "units", "normalization", "replicates_and_uncertainty",
               "numeric_observations", "exact_construct_join"}
    descriptions = {"id", "locator", "producing_cells", "culture_context", "readout", "timing", "limit"}
    fields(observation, descriptions | unknown | {"record_kind"}, "assay descriptor")
    require(strings([observation[key] for key in descriptions]), "Missing assay provenance")
    require(observation["record_kind"] == "assay_descriptor_no_numeric_data"
            and all(observation[key] is None for key in unknown),
            "Assay descriptor cannot establish numerical observations or material joins")


def reconstruct(authority, directory):
    """Derive candidates from declared raw extracts without filling missing data."""
    fields(authority, {"schema", "source", "rows", "correspondence", "observations",
                       "limitations"}, "material reconciliation authority")
    require(authority["schema"] == "biocompiler.material_reconciliation_authority.v1",
            "Unsupported authority schema")
    source = authority["source"]
    fields(source, {"id", "doi", "sha256", "bytes", "urls", "correction"}, "source")
    require(all(isinstance(source[k], str) and source[k].strip() for k in ("id", "doi")),
            "Missing source identity")
    hash_value(source["sha256"])
    require(type(source["bytes"]) is int and source["bytes"] > 0, "Invalid source size")
    require(isinstance(source["urls"], list) and source["urls"]
            and all(isinstance(url, str) and url.startswith("https://")
                    for url in source["urls"]), "Missing public source locators")
    check_context(authority)
    rows = authority["rows"]
    require(isinstance(rows, list) and len(rows) == len(ROWS), "Wrong row inventory")
    derived, seen = [], set()
    for row in rows:
        fields(row, {"id", "label", "locator", "alphabet", "role", "raw_path"}, "row")
        key = row["id"]
        require(isinstance(key, str) and key in ROWS and key not in seen,
                "Unknown or duplicate component row")
        seen.add(key)
        require((row["alphabet"], row["role"], row["raw_path"]) == ROWS[key],
                "Component alphabet, role or raw path changed")
        require(all(isinstance(row[k], str) and row[k].strip() for k in ("label", "locator")),
                "Missing row source locator")
        raw = read_bytes(directory, row["raw_path"])
        sequence, normalization = normalize_sequence(raw.decode("utf-8"), row["alphabet"])
        derived.append({
            "id": key, "source_id": source["id"], "source_sha256": source["sha256"],
            "label": row["label"], "locator": row["locator"], "alphabet": row["alphabet"],
            "role": row["role"], "scope": "component_only", "raw_sha256": sha(raw),
            "sequence": sequence, "sequence_sha256": sha(sequence.encode("ascii")),
            "length": len(sequence), "normalization": normalization,
        })
    return {"schema": "biocompiler.material_reconciliation_candidates.v1",
            "rows": derived, "claims": dict(CLAIMS)}


def check(root=ROOT):
    root = Path(root).resolve()
    directory = root
    for part in BUNDLE.parts:
        directory = directory / part
        require(not directory.is_symlink(), "Evidence directory symlink is forbidden")
    authority_bytes = read_bytes(directory, "authority.json")
    authority = parse_json(authority_bytes.decode("utf-8"))
    review = parse_json(read_bytes(directory, "review.json").decode("utf-8"))
    fields(review, {"schema", "authority_sha256", "raw_sha256", "expected_sequence_sha256",
                    "review_scope", "reviewers", "status"}, "material review")
    require(review["schema"] == "biocompiler.material_reconciliation_review.v1"
            and review["status"] == "source_literal_extraction_reviewed", "Review pending")
    require(review["authority_sha256"] == sha(authority_bytes), "Reviewed authority changed")
    require(isinstance(review["review_scope"], str) and review["review_scope"].strip(),
            "Missing review scope")
    reviewers = review["reviewers"]
    require(isinstance(reviewers, list) and len(reviewers) >= 2
            and all(isinstance(r, str) and r.strip() for r in reviewers)
            and len(set(reviewers)) == len(reviewers), "Separate review identities required")
    fields(review["raw_sha256"], {r[2] for r in ROWS.values()}, "reviewed raw inventory")
    fields(review["expected_sequence_sha256"], set(ROWS), "reviewed sequence inventory")
    expected = reconstruct(authority, directory)
    for row in expected["rows"]:
        require(row["raw_sha256"] == review["raw_sha256"][ROWS[row["id"]][2]],
                "Reviewed raw extraction changed")
        require(row["sequence_sha256"] == review["expected_sequence_sha256"][row["id"]],
                "Independent sequence expectation mismatch")
    candidate = parse_json(read_bytes(directory, "candidates.json").decode("utf-8"))
    fields(candidate, {"schema", "rows", "claims"}, "component candidates")
    fields(candidate["claims"], set(CLAIMS), "component claim boundaries")
    require(all(value is False for value in candidate["claims"].values()),
            "Component extraction cannot promote a claim")
    require(fingerprint(candidate) == fingerprint(expected),
            "Candidates differ from reconstructed source authority")
    return {"status": "PASS_SOURCE_LITERAL_RECONSTRUCTION_ONLY", "components": len(ROWS),
            "candidate_fingerprint": fingerprint(expected), "complete_reference": False,
            "experimental_material_reconciled": False, "human_admission": False}


if __name__ == "__main__":
    import json

    try:
        print(json.dumps(check(), sort_keys=True))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"Material reconciliation failed: {exc}", file=sys.stderr)
        sys.exit(1)
