"""Inert audit of one externally pinned successful DEVELOPMENT evidence packet.

Only local immutable Git objects are read before process denial. No product
module, downloaded executable, native build, semantic replay, or network call
is admitted. This does not establish installed/release/main acceptance.
"""
import argparse
import ast
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import subprocess
import sys
import zipfile

if not __debug__:
    raise RuntimeError("Assertions must be enabled")
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
parser.add_argument("--evidence-dir", type=Path, required=True)
for name in ("head", "tree", "artifact-sha256"):
    parser.add_argument("--" + name, required=True)
for name in ("run-id", "run-attempt", "suite-id", "job-id", "artifact-id", "artifact-size", "source-count"):
    parser.add_argument("--" + name, type=int, required=True)
args = parser.parse_args()
ROOT, OUT = args.root.resolve(strict=True), args.evidence_dir.resolve(strict=True)
H, TREE, RUN = args.head, args.tree, args.run_id
ATTEMPT = args.run_attempt
assert re.fullmatch("[0-9a-f]{40}", H) and re.fullmatch("[0-9a-f]{40}", TREE)
assert re.fullmatch("[0-9a-f]{64}", args.artifact_sha256)
assert all(type(getattr(args, key)) is int and 0 < getattr(args, key) < 2**63 for key in
           ("run_id", "run_attempt", "suite_id", "job_id", "artifact_id", "artifact_size", "source_count"))
assert args.artifact_size <= 16 * 1024 * 1024 and args.source_count <= 5000
assert OUT.is_relative_to(ROOT / "generated")
BRANCH = "codex/dev-policy/material-selection-domain"
WORKFLOW = ".github/workflows/policy-development.yml"
WORKFLOW_SHA256 = "c7b5211cf0fe6e606767255b21dd55c263eeb280f6c730db330434ddda23f3aa"
REPOSITORY = "logannye/biocompiler"
SOURCE_ROOTS = ("core", "src", "tools", "protocol", ".github", "pyproject.toml")
HOST = "/home/runner/work/biocompiler/biocompiler/"

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()

def pin(raw):
    return {"sha256": sha(raw), "size": len(raw)}

def decode(raw):
    def pairs(rows):
        value = {}
        for key, item in rows:
            assert key not in value, "Duplicate JSON key"
            value[key] = item
        return value
    def invalid(value):
        raise AssertionError("Nonfinite JSON value")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)

def read(name, maximum=16 * 1024 * 1024):
    path = OUT / name
    assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(OUT)
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    assert len(raw) <= maximum
    return decode(raw)

def pages(name, key):
    values = read(name)
    assert type(values) is list and values and all(type(page) is dict for page in values)
    assert all(type(page["total_count"]) is int and page["total_count"] == 1 for page in values)
    rows = [row for page in values for row in page[key]]
    assert len(rows) == 1 and len({row["id"] for row in rows}) == 1
    return rows

r, commit = read("api/run.json"), read("api/commit.json")
jobs, arts = pages("api/jobs.json", "jobs"), pages("api/artifacts.json", "artifacts")
assert (r["id"], r["run_attempt"], r["head_sha"], r["event"], r["head_branch"], r["status"], r["conclusion"], r["workflow_id"]) == (
    RUN, ATTEMPT, H, "push", BRANCH, "completed", "success", 376732846)
assert r["path"] == WORKFLOW and r["check_suite_id"] == args.suite_id
assert r["repository"]["full_name"] == REPOSITORY and r["repository"]["id"] == 1395674522
assert r["head_repository"]["full_name"] == REPOSITORY and r["head_repository"]["id"] == 1395674522
assert commit["sha"] == H and commit["tree"]["sha"] == TREE
job = jobs[0]
assert (job["id"], job["run_id"], job["head_sha"], job["run_attempt"], job["name"], job["status"], job["conclusion"]) == (
    args.job_id, RUN, H, ATTEMPT, "development-feedback", "completed", "success")
assert job["labels"] == ["ubuntu-24.04"]
assert all(step["status"] == "completed" and step["conclusion"] == "success" for step in job["steps"])
assert [(step["number"], step["name"]) for step in job["steps"]] == [
    (1, "Set up job"), (2, "Run actions/checkout@v4"), (3, "Run actions/setup-python@v5"),
    (4, "Authenticate hosted push and exact sources before native setup"),
    (5, "Run ocaml/setup-ocaml@93303b622b2522e4411e295f9e77411a24912ac7"),
    (6, "Install ordinary dependencies, build once and run twenty-three fixed suites"),
    (7, "Exercise Python authored component policies through fresh paired export"),
    (8, "Exercise supplied alternatives through independent selection and paired export"),
    (9, "Retain diagnostic evidence even when native work fails"),
    (16, "Post Run ocaml/setup-ocaml@93303b622b2522e4411e295f9e77411a24912ac7"),
    (17, "Post Run actions/setup-python@v5"), (18, "Post Run actions/checkout@v4"), (19, "Complete job")]
art = arts[0]
assert (art["id"], art["name"], art["size_in_bytes"], art["digest"], art["expired"]) == (
    args.artifact_id, f"development-feedback-{RUN}-{ATTEMPT}", args.artifact_size, "sha256:" + args.artifact_sha256, False)
assert art["workflow_run"]["id"] == RUN and art["workflow_run"]["head_sha"] == H
assert art["workflow_run"]["head_branch"] == BRANCH
assert art["created_at"] >= r["run_started_at"]

# Read only immutable local Git objects; explicitly disable lazy fetch/replaces.
git_env = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1", GIT_OPTIONAL_LOCKS="0")
def git(argv, input=None, maximum=128 * 1024 * 1024):
    value = subprocess.run(["git", *argv], input=input, cwd=ROOT, env=git_env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=True)
    assert len(value.stdout) <= maximum and len(value.stderr) <= 65536
    return value.stdout

commit_raw = git(["cat-file", "commit", H], maximum=1024 * 1024)
assert hashlib.sha1(b"commit " + str(len(commit_raw)).encode() + b"\0" + commit_raw).hexdigest() == H
assert commit_raw.splitlines()[0] == b"tree " + TREE.encode()
rawtree = git(["ls-tree", "-rl", "-z", H, "--", *SOURCE_ROOTS], maximum=2 * 1024 * 1024)
rows = [row.split(b"\t", 1) for row in rawtree.split(b"\0") if row]
assert len(rows) == args.source_count
headers = [header.decode().split() for header, _ in rows]
assert all(len(header) == 4 and header[0] in ("100644", "100755") and header[1] == "blob"
           and re.fullmatch("[0-9a-f]{40}", header[2]) and 0 <= int(header[3]) <= 8 * 1024 * 1024 for header in headers)
assert sum(int(header[3]) for header in headers) <= 128 * 1024 * 1024
objects = [header[2] for header in headers]
rawobjects = git(["cat-file", "--batch"], input=("\n".join(objects) + "\n").encode(),
    maximum=128 * 1024 * 1024 + 1024 * 1024)
stream, sources, contents = io.BytesIO(rawobjects), {}, {}
for (_, name), (mode, kind, blob, declared_size) in zip(rows, headers):
    actual, typ, size = stream.readline().decode().split()
    assert actual == blob and typ == kind == "blob" and int(size) == int(declared_size)
    raw = stream.read(int(size))
    assert len(raw) == int(size) and stream.read(1) == b"\n"
    assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == blob
    name = name.decode("utf-8")
    path = PurePosixPath(name)
    assert name not in sources and path.as_posix() == name and not path.is_absolute() and ".." not in path.parts and "\\" not in name
    sources[name] = {**pin(raw), "git_blob": blob, "mode": mode}
    contents[name] = raw
assert not stream.read() and sha(contents[WORKFLOW]) == WORKFLOW_SHA256
snapshot = (json.dumps(sources, sort_keys=True, indent=2) + "\n").encode()
if (OUT / "source-snapshot.json").exists():
    assert (OUT / "source-snapshot.json").read_bytes() == snapshot
else:
    (OUT / "source-snapshot.json").write_bytes(snapshot)

def deny(event, unused):
    if event.startswith(("subprocess.", "socket.", "os.exec", "os.spawn", "ctypes.dlopen")) or event in {
        "os.system", "os.fork", "os.forkpty", "os.posix_spawn"}:
        raise AssertionError("Process/network/native-load denied: " + event)
sys.addaudithook(deny)

def literal(path, name):
    found = [node for node in ast.parse(contents[path]).body if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
    assert len(found) == 1
    return ast.literal_eval(found[0].value)

def zip_data(raw, *, count, maximum, per_file, expected_names=None):
    result = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        assert len(infos) == count and len({info.filename for info in infos}) == count
        assert sum(info.file_size for info in infos) <= maximum
        if expected_names is not None:
            assert archive.namelist() == expected_names
        for info in infos:
            path = PurePosixPath(info.filename)
            assert path.parts and path.as_posix() == info.filename and info.filename == info.orig_filename
            assert not path.is_absolute() and ".." not in path.parts and "\\" not in info.filename and "\x00" not in info.filename
            assert not info.is_dir() and not info.flag_bits & 1 and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
            assert stat.S_IFMT(info.external_attr >> 16) in (0, stat.S_IFREG)
            assert 0 <= info.file_size <= per_file and 0 <= info.compress_size <= len(raw)
            chunks, total = [], 0
            with archive.open(info) as member:
                while chunk := member.read(65536):
                    total += len(chunk)
                    assert total <= info.file_size <= per_file
                    chunks.append(chunk)
            assert total == info.file_size  # Reading through EOF independently checks every outer/nested CRC.
            result[info.filename] = b"".join(chunks)
    return result

zip_path = OUT / "development-feedback.zip"
assert zip_path.is_file() and not zip_path.is_symlink() and zip_path.stat().st_size == args.artifact_size
zipraw = zip_path.read_bytes()
assert pin(zipraw) == {"sha256": args.artifact_sha256, "size": args.artifact_size}
data = zip_data(zipraw, count=90, maximum=64 * 1024 * 1024, per_file=16 * 1024 * 1024)
def j(name):
    return decode(data[name])

suites = literal("tools/check_policy_development.py", "SUITES")
assert len(suites) == 23 and len({name for name, _ in suites}) == 23
assert [name for name, _ in suites] == ["test_policy_component_" + name for name in (
    "fragment", "material", "assembly_rule", "assembly_check", "material_request", "selection_request",
    "material_candidate", "selection_candidate", "selection_common", "selection_check", "selection_scope", "selection_service",
    "context_check", "material_service")] + ["test_protocol", "test_producer_protocol", "test_policy_implementation_binding",
    "test_policy_preservation_check", "test_policy_material_binding", "test_policy_material_context", "test_policy_material_check",
    "test_policy_mrna_structure", "test_construction_content"]
obligations = literal("tools/check_policy_material.py", "OBLIGATIONS")
discharges = literal("tools/check_policy_material.py", "CONTEXT_DISCHARGES")
assert len(obligations) == 23
identity = {"event": "push", "machine": "x86_64", "ref": "refs/heads/" + BRANCH, "repository": REPOSITORY,
    "revision": H, "run_attempt": str(ATTEMPT), "run_id": str(RUN), "system": "Linux", "tree": TREE,
    "workflow_ref": REPOSITORY + "/" + WORKFLOW + "@refs/heads/" + BRANCH}
prep, feed, public, sdk, fixture = (j(name) for name in (
    "preparation.json", "feedback.json", "public-sdk.json", "sdk-witness.json", "component-originals.json"))
selection_driver, selection_sdk, selection_fixture = (j(name) for name in (
    "selection-public-sdk.json", "selection-sdk-witness.json", "selection-originals.json"))
for record in (prep, feed, public, sdk, selection_driver, selection_sdk):
    assert record["identity"] == identity
assert prep["schema"] == feed["schema"] == "biocompiler.development-feedback.v0.1"
assert public["schema"] == "biocompiler.development-sdk-feedback.v0.1"
assert sdk["schema_version"] == "biocompiler.policy_component_sdk_development.v0.1"
assert selection_driver["schema"] == "biocompiler.development-selection-sdk-feedback.v0.1"
assert selection_sdk["schema_version"] == "biocompiler.policy_component_selection_sdk_development.v0.1"
assert prep["sources"] == sources
for record in (feed, public, selection_driver):
    assert record["sources_before"] == record["sources_after"] == sources
for record in (feed, public, sdk, selection_driver, selection_sdk):
    assert record["status"] == "passed" and record["acceptance"] is False
for record in (sdk, selection_sdk):
    assert record["source_snapshot_sha256"] == sha(canonical(sources))
    assert record["python"] == "3.11.15" and record["python_semantic_authority"] == "forbidden"
assert public["native_feedback"] == selection_driver["native_feedback"] == pin(data["feedback.json"])
assert selection_driver["component_sdk_feedback"] == pin(data["public-sdk.json"])
assert public["outputs"] == {name: pin(data[name]) for name in ("component-originals.json", "sdk-witness.json")}
assert selection_driver["outputs"] == {name: pin(data[name]) for name in ("selection-originals.json", "selection-sdk-witness.json")}
expected_suites = [{"name": name, "executable": "core/_build/default/test/" + name + ".exe",
    "fixtures": {"core/test/" + path: pin(contents["core/test/" + path]) for path in paths},
    "argv": ["opam", "exec", "--", HOST + "core/_build/default/test/" + name + ".exe", *(HOST + "core/test/" + path for path in paths)]}
    for name, paths in suites]
assert prep["suites"] == expected_suites and len(feed["suites"]) == 23
for got, expected in zip(feed["suites"], expected_suites):
    assert {key: got[key] for key in expected} == expected
assert [row["name"] for row in feed["actions"]] == ["dependencies", "build"]
assert [row["name"] for row in public["actions"]] == ["component-originals", "component-sdk"]
assert [row["name"] for row in selection_driver["actions"]] == ["selection-originals", "selection-sdk"]
actions = feed["actions"] + feed["suites"] + public["actions"] + selection_driver["actions"]
for action in actions:
    assert action["log"] == action["name"] + ".log" and action["returncode"] == 0 and action["status"] == "passed"
    assert action["log_pin"] == pin(data[action["log"]])
    assert type(action["elapsed_seconds"]) in (int, float) and action["elapsed_seconds"] >= 0
assert [row["argv"] for row in feed["actions"]] == [["opam", "install", "core/biocompiler_core.opam", "--deps-only", "--with-test", "--yes"],
    ["opam", "exec", "--", "dune", "build", "--root", "core", "@all"]]
host = HOST

# Retain all original A/B SDK and paired-export checks from the accepted audit.
inputs=literal('tools/check_policy_component_material.py','INPUTS')
assert public['actions'][0]['argv']==['opam','exec','--',host+'core/_build/default/test/component_fixture_export/main.exe',*(host+p for p in inputs),host+'generated/development-feedback/component-originals.json']
assert public['actions'][1]['argv']==['/opt/hostedtoolcache/Python/3.11.15/x64/bin/python','-B',host+'tools/check_policy_component_material.py','--fixture',host+'generated/development-feedback/component-originals.json','--core',host+'core/_build/default/bin/core/main.exe','--verify',host+'core/_build/default/bin/verify/main.exe','--output',host+'generated/development-feedback/sdk-witness.json']
assert set(feed['binaries'])=={x['executable'] for x in expected_suites}|set(public['binaries']) and len(feed['binaries'])==26 and len(public['binaries'])==3
for b in feed['binaries'].values(): assert type(b) is dict and set(b)=={'sha256','size'} and type(b['sha256']) is str and re.fullmatch('[0-9a-f]{64}',b['sha256']) and type(b['size']) is int and 0<b['size']<128*1024*1024
for p,b in public['binaries'].items(): assert feed['binaries'][p]==b and re.fullmatch('[0-9a-f]{64}',b['sha256']) and 0<b['size']<128*1024*1024
assert sdk['binary_sha256']=={role:public['binaries']['core/_build/default/bin/'+role+'/main.exe'] for role in ('core','verify')}
assert sdk['python']=='3.11.15' and sdk['python_semantic_authority']=='forbidden' and sdk['fixture_sha256']==sha(data['component-originals.json'])
assert fixture['schema_version']=='biocompiler.policy_component_original_fixture.v0.1' and fixture['status']=='source_declarations_only' and fixture['acceptance'] is False and fixture['source_sha256']=={n:sha(contents[n]) for n in inputs}
assert [c['id'] for c in fixture['cases']]==['A','B']
original_drivers=[c['request']['component_library']['components'][1] for c in fixture['cases']]; assert original_drivers[0]==original_drivers[1] and sdk['shared_driver_fingerprint']==sha(canonical(original_drivers[0]))
names=['compile','check-verify','replay-verify','export-verify','paired-publication','changed-guard','changed-state','changed-feedback','changed-configuration','changed-material','rejected-export','verify-has-no-producer','stale-source']
assert [(x['case'],x['name']) for x in sdk['observations']]==[(c,n) for c in ('A','B') for n in names]
assert len(sdk['authoring'])==2
for row in sdk['observations']:
 assert row['path']=='sdk-witness/'+row['case']+'-'+row['name']+'.json' and row['sha256']==sha(data[row['path']]) and row['bytes']==len(data[row['path']])
zipproof=[]
for ix,case in enumerate(fixture['cases']):
 label=case['id']; expected=case['expected']; source=decode(contents[inputs[ix]])
 assert case['request']['implementation_request']==source['request']['implementation_request'] and case['limits']==source['limits'] and expected['obligations']==obligations
 authored=sdk['authoring'][ix]; assert authored['case']==label and authored['phase']=='python_authoring_before_native_semantic_guard' and authored['runtime_semantics']=='not_executed' and authored['declarations']==14
 assert authored['recipe_sha256']==sha(contents['tools/generate_policy_exclusion_fixture.py']) and authored['source_artifact_digest']==sha(canonical(case['request']['implementation_request']['document'])) and authored['implementation_request_digest']==sha(canonical(case['request']['implementation_request'])) and authored['request_digest']==sha(canonical(case['request']))
 vals={n:j('sdk-witness/'+label+'-'+n+'.json') for n in names}; good=vals['compile']; report=good['report']; candidate=good['candidate']; export=vals['export-verify']
 assert good==vals['check-verify']==vals['replay-verify'] and export['report']==report and export['candidate']==candidate
 assert report['status']=='checked_component_material' and report['claim_scope']=='bounded_conditional_policy_via_reusable_components_to_exact_mrna' and report['premise']=='supplied_component_composition_and_provider_contracts'
 assert report['assembly_status']==report['context_status']=='pass' and report['all_original_obligations_discharged'] is True and report['empirical']=='unassessed' and report['artifact']==report['export']=='withheld'
 assert [x['obligation'] for x in report['obligations']]==obligations and all(x['status']=='discharged' for x in report['obligations']) and [x['id'] for x in report['context']['discharges']]==discharges
 cov=report['preservation']['coverage']; assert cov['complete'] is True and [cov[k] for k in ('histories','transitions','prefixes_started','matched_prefixes')]==[9,47,48,48]
 reqs=report['preservation']['requirements']; assert [x['id'] for x in reqs]==['request_progress','initiation_progress','exclusive_selection'] and all(x['status']=='pass' and x['histories']['pass']==9 for x in reqs)
 sequence=['CCAUGGCUUAAGGAAAA','CGCAUGGCUUAAGGAAAA'][ix]; assert candidate['construction']['inventory']['molecules']==expected['molecules'] and [x['sequence'] for x in expected['molecules']]==[sequence]
 assert report['assembly']['carrier_projections']==expected['carrier_projections'] and len(expected['carrier_projections'])==[96,107][ix] and len(candidate['implementation']['nodes'])==[15,17][ix] and len(candidate['implementation']['wires'])==[22,25][ix]
 bindings={(x['slot'],x['node']):x['actual'] for x in candidate['assembly_proposal']['nodes']}; links=deepcopy(expected['link_projections'])
 for link in links:
  for key in ('producer_endpoint','consumer_endpoint'):
   local=link[key]; link[key]={'node':bindings[(local['slot'],local['node'])],'port':local['port']}
 assert report['assembly']['link_projections']==links
 for n,code in [('changed-guard','policy_implementation_source_binding'),('changed-state','policy_implementation_source_binding'),('changed-feedback','policy_implementation_source_binding'),('changed-configuration','policy_implementation_contract'),('rejected-export','policy_component_material_export_not_accepted'),('verify-has-no-producer','unsupported_operation'),('stale-source','policy_correspondence')]:
  assert vals[n]['status']==('unsupported' if n=='verify-has-no-producer' else 'error') and {x['code'] for x in vals[n]['diagnostics']}=={code} and vals[n]['diagnostics']
 fail=vals['changed-material']['report']; assert fail['status']=='not_accepted' and fail['assembly_status']=='fail' and fail['context_status']=='unassessed' and fail['assembly']['structure']['content_outcome']=='fail' and [x['obligation'] for x in fail['obligations']]==obligations and all(x['status']=='unresolved' for x in fail['obligations'])
 raw=data['sdk-witness/'+label+'-program.zip']; pub=vals['paired-publication']; assert pub['sha256']==sha(raw) and pub['bytes']==len(raw) and pub['fresh_result_fingerprint']==sha(canonical(export))
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  infos=z.infolist(); assert z.namelist()==['program.fasta','manifest.json'] and sum(i.file_size for i in infos)<=16*1024*1024
  for i in infos: assert i.filename==i.orig_filename and not i.flag_bits&1 and 0<=i.file_size<=8*1024*1024 and 0<=i.compress_size<=len(raw) and stat.S_IFMT(i.external_attr>>16) in (0,stat.S_IFREG)
  assert z.testzip() is None
  fasta=z.read('program.fasta'); manifest=z.read('manifest.json'); artifact=export['artifact']
  assert fasta==('>rna_0001 alphabet=RNA\n'+sequence+'\n').encode()==artifact['fasta'].encode() and manifest==canonical(artifact['manifest']) and sha(fasta)==artifact['fasta_sha256'] and sha(manifest)==artifact['manifest_sha256']
  assert pub['members']==[{'name':n,'bytes':len(z.read(n)),'sha256':sha(z.read(n))} for n in z.namelist()]
 zipproof.append({'case':label,'sequence':sequence,'zip':pin(raw),'members':pub['members']})

# Additive selection driver and one-A-program declaration packet.
selection_inputs = literal("tools/check_policy_component_selection.py", "INPUTS")
assert selection_inputs == ("core/test/data/policy_material_request_v01.json",
    "core/test/policy_component_support/literals.ml", "core/test/policy_component_support/requests.ml",
    "core/test/policy_component_support/selection_requests.ml")
assert literal("tools/check_policy_development.py", "SELECTION_ORIGINALS") == selection_inputs
assert selection_driver["source_inputs"] == {name: pin(contents[name]) for name in selection_inputs}
assert selection_driver["binaries"] == public["binaries"]
assert set(public["binaries"]) == {"core/_build/default/test/component_fixture_export/main.exe",
    "core/_build/default/bin/core/main.exe", "core/_build/default/bin/verify/main.exe"}
assert selection_driver["actions"][0]["argv"] == ["opam", "exec", "--",
    HOST + "core/_build/default/test/component_fixture_export/main.exe", "--selection",
    *(HOST + path for path in selection_inputs), HOST + "generated/development-feedback/selection-originals.json"]
assert selection_driver["actions"][1]["argv"] == ["/opt/hostedtoolcache/Python/3.11.15/x64/bin/python", "-B",
    HOST + "tools/check_policy_component_selection.py", "--fixture", HOST + "generated/development-feedback/selection-originals.json",
    "--core", HOST + "core/_build/default/bin/core/main.exe", "--verify", HOST + "core/_build/default/bin/verify/main.exe",
    "--output", HOST + "generated/development-feedback/selection-sdk-witness.json"]
assert selection_sdk["binary_sha256"] == sdk["binary_sha256"]
assert selection_sdk["fixture_sha256"] == sha(data["selection-originals.json"])
assert set(selection_fixture) == {"schema_version", "status", "acceptance", "source_sha256", "request", "limits", "expected"}
assert selection_fixture["schema_version"] == "biocompiler.policy_component_selection_original_fixture.v0.1"
assert selection_fixture["status"] == "source_declarations_only" and selection_fixture["acceptance"] is False
assert selection_fixture["source_sha256"] == {name: sha(contents[name]) for name in selection_inputs}
short_rna, long_rna = "CCAUGGCUUAAGGAAAA", "CGCAUGGCUUAAGGAAAA"
assert selection_fixture["expected"] == {"short_rna": short_rna, "long_rna": long_rna,
    "histories": 9, "transitions": 47, "prefixes_started": 48, "obligations": obligations}
original, limits = selection_fixture["request"], selection_fixture["limits"]
original_A = decode(contents[selection_inputs[0]])
assert original["schema_version"] == "biocompiler.policy_component_selection_request.v0.1"
assert original["profile"] == "biocompiler.policy_component_material_selection.v0.1"
assert original["predicate"] == {"max_total_nt": 17}
assert original["budgets"] == {"profile": "biocompiler.policy_component_selection_resources.v0.2",
    "max_work": 17000000000, "max_report_bytes": 8323072, "max_report_nodes": 1000000}
assert [(row["id"], row["rank"]) for row in original["alternatives"]] == [("short", 1), ("long", 0)]
assert limits == original_A["limits"]
originals = {row["id"]: row["request"] for row in original["alternatives"]}
for name, child in originals.items():
    # Both carry the entire ORIGINAL A document, assurances, definitions,
    # implementation library, operating domain and obligations. Never borrow B.
    assert child["implementation_request"] == original_A["request"]["implementation_request"]
    assert child["context"]["delivery_group"]["max_total_bases"] == 18
    decision, driver = child["component_library"]["components"]
    assert driver == original_drivers[0]
    literal_decision = fixture["cases"][0]["request"]["component_library"]["components"][0]
    for retained in ("fragment", "products", "provider_requirements"):
        assert decision["body"][retained] == literal_decision["body"][retained]
    assert decision["body"]["root"]["id"] == "leader_A"
    assert decision["body"]["root"]["molecule"]["sequence"] == ("CC" if name == "short" else "CGC")
    assert child["composition_rule"]["body"]["join"]["offset"] == (2 if name == "short" else 3)
assert len(selection_sdk["authoring"]) == 2
for authored, name in zip(selection_sdk["authoring"], ("short", "long")):
    child = originals[name]
    assert authored["case"] == name and authored["phase"] == "python_authoring_before_native_semantic_guard"
    assert authored["runtime_semantics"] == "not_executed" and authored["declarations"] == 14
    assert authored["recipe_sha256"] == sha(contents["tools/generate_policy_exclusion_fixture.py"])
    assert authored["source_artifact_digest"] == sha(canonical(child["implementation_request"]["document"]))
    assert authored["implementation_request_digest"] == sha(canonical(child["implementation_request"]))
    assert authored["request_digest"] == sha(canonical(child))
selection_names = ("child-short-compile", "child-long-compile", "check-core", "check-verify", "replay-core", "replay-verify",
    "export-core", "paired-core", "export-verify", "paired-verify", "long-check", "long-export", "long-paired",
    "no-eligible-check", "no-eligible-export", "loser-rank-check", "loser-rank-export", "loser-rank-paired", "stale-replay",
    "verify-no-selection-producer", "core-no-selection-producer")
assert literal("tools/check_policy_component_selection.py", "OBSERVATIONS") == selection_names
assert [(row["case"], row["name"]) for row in selection_sdk["observations"]] == [("selection", name) for name in selection_names]
selection_values = {}
for row in selection_sdk["observations"]:
    path = "selection-sdk-witness/selection-" + row["name"] + ".json"
    assert row["path"] == path and row["sha256"] == sha(data[path]) and row["bytes"] == len(data[path])
    selection_values[row["name"]] = j(path)
candidate = {"schema_version": "biocompiler.policy_component_selection_candidate.v0.1", "alternatives": [
    {"id": name, "candidate": selection_values["child-" + name + "-compile"]["candidate"]} for name in ("short", "long")], "selected_id": "short"}

def child_evidence(child_original, child_candidate, inner, sequence):
    assert inner["status"] == "checked_component_material" and inner["all_original_obligations_discharged"] is True
    assert inner["assembly_status"] == inner["context_status"] == "pass"
    assert inner["claim_scope"] == "bounded_conditional_policy_via_reusable_components_to_exact_mrna"
    assert inner["premise"] == "supplied_component_composition_and_provider_contracts"
    assert inner["artifact"] == inner["export"] == "withheld" and inner["empirical"] == "unassessed"
    assert inner["request_fingerprint"] == sha(canonical(child_original))
    assert inner["candidate_fingerprint"] == sha(canonical(child_candidate)) and inner["limits"] == limits
    assert inner["catalog"]["original_binding"] == child_original["catalog_binding"]
    assert [row["obligation"] for row in inner["obligations"]] == obligations
    assert all(row["status"] == "discharged" for row in inner["obligations"])
    assert [row["id"] for row in inner["context"]["discharges"]] == discharges
    coverage = inner["preservation"]["coverage"]
    assert coverage["complete"] is True and [coverage[key] for key in ("histories", "transitions", "prefixes_started", "matched_prefixes")] == [9, 47, 48, 48]
    requirements = inner["preservation"]["requirements"]
    assert [row["id"] for row in requirements] == ["request_progress", "initiation_progress", "exclusive_selection"]
    assert all(row["status"] == "pass" and row["histories"]["pass"] == 9 for row in requirements)
    molecules = child_candidate["construction"]["inventory"]["molecules"]
    assert len(molecules) == 1 and molecules[0]["id"] == "payload" and molecules[0]["sequence"] == sequence
    assert child_candidate["construction"]["member_order"] == ["payload"]
    assert len(child_candidate["implementation"]["nodes"]) == 15 and len(child_candidate["implementation"]["wires"]) == 22
    # Molecular expectations are separately authored by the domain-only
    # fixture exporter. Its 18-base geometry is material data, never the B
    # policy: complete source/program equality above binds BOTH children to A.
    material_literal = fixture["cases"][0 if sequence == short_rna else 1]["expected"]["molecules"]
    assert molecules == material_literal

for name, sequence in (("short", short_rna), ("long", long_rna)):
    produced = selection_values["child-" + name + "-compile"]
    assert produced["artifact"] is None
    child_evidence(originals[name], produced["candidate"], produced["report"], sequence)

def measured(value):
    pending, nodes = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        assert depth <= 128
        if type(item) is dict:
            nodes += len(item)
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
    return len(canonical(value)), nodes

def selection_result(value, request, proposed, *, winner, maximum, artifact):
    assert set(value) == {"schema_version", "implementation", "resource_profile", "validation_scope", "request_fingerprint",
        "candidate_fingerprint", "invocation_fingerprint", "report_fingerprint", "candidate", "report", "artifact"}
    assert value["schema_version"] == "biocompiler.core.policy_component_selection.v1"
    assert value["implementation"] == "biocompiler.ocaml.policy_component_selection.v0.1"
    assert value["validation_scope"] == "policy-component-selection-mrna-v0.1"
    assert value["resource_profile"] == request["budgets"]["profile"] and value["candidate"] == proposed
    invocation = {"request": request, "candidate": proposed, "limits": limits}
    report = value["report"]
    for key, expected in (("request_fingerprint", request), ("candidate_fingerprint", proposed), ("invocation_fingerprint", invocation)):
        assert value[key] == report[key] == sha(canonical(expected))
    assert value["report_fingerprint"] == sha(canonical(report))
    assert report["schema_version"] == "biocompiler.policy_component_selection_assessment.v0.1"
    assert report["profile"] == request["profile"] and report["resource_profile"] == request["budgets"]["profile"]
    assert report["implementation"] == "biocompiler.ocaml.policy_component_selection_check.v0.1"
    assert report["common_authority_profile"] == "biocompiler.policy_decision_leader_variant.v0.1"
    assert report["status"] == ("no_eligible_alternative" if winner is None else "checked_selection")
    assert report["selected_id"] == report["proposed_selected_id"] == winner and report["winner_matches"] is True
    assert report["census_complete"] is True and report["all_inner_accepted"] is True
    assert report["predicate"] == request["predicate"] == {"max_total_nt": maximum}
    assert report["limits"] == limits and report["budgets"] == request["budgets"]
    assert report["claim_scope"] == "bounded_complete_supplied_catalog_selection"
    assert report["premise"] == "supplied_component_composition_and_provider_contracts"
    assert report["artifact"] == report["export"] == "withheld" and report["empirical"] == "unassessed"
    assert [row["id"] for row in report["alternatives"]] == ["long", "short"]
    sources_by_id = {row["id"]: row for row in request["alternatives"]}
    candidates_by_id = {row["id"]: row["candidate"] for row in proposed["alternatives"]}
    inner_values = []
    for row in report["alternatives"]:
        name = row["id"]
        source = sources_by_id[name]
        sequence = short_rna if name == "short" else long_rna
        assert row["rank"] == source["rank"] and row["request_fingerprint"] == sha(canonical(source["request"]))
        assert row["candidate_fingerprint"] == sha(canonical(candidates_by_id[name]))
        assert row["total_nt"] == len(sequence) and row["sequence_sha256"] == sha(sequence.encode())
        assert row["eligible"] is (len(sequence) <= maximum)
        child_evidence(source["request"], candidates_by_id[name], row["inner"], sequence)
        inner_values.append(row["inner"])
    expected_winners = sorted((row["rank"], row["id"]) for row in report["alternatives"] if row["eligible"])
    assert winner == (expected_winners[0][1] if expected_winners else None)
    assert report["usage"]["reserved_child_work"] == sum(row["request"]["budgets"]["max_work"] for row in request["alternatives"])
    assert report["usage"]["reserved_child_work"] < report["usage"]["charged_work"] <= request["budgets"]["max_work"]
    assert (value["artifact"] is not None) == artifact
    if artifact:
        export = value["artifact"]
        assert set(export) == {"schema_version", "fasta", "fasta_sha256", "manifest", "manifest_sha256"}
        assert export["schema_version"] == "biocompiler.policy_component_selection_mrna_export.v0.1"
        sequence = short_rna if winner == "short" else long_rna
        fasta = ">rna_0001 alphabet=RNA\n" + sequence + "\n"
        assert export["fasta"] == fasta and export["fasta_sha256"] == sha(fasta.encode())
        manifest = export["manifest"]
        assert export["manifest_sha256"] == sha(canonical(manifest))
        selected_original = sources_by_id[winner]["request"]
        selected_candidate = candidates_by_id[winner]
        selected_report = next(row["inner"] for row in report["alternatives"] if row["id"] == winner)
        molecule = selected_candidate["construction"]["inventory"]["molecules"][0]
        expected = {"schema_version": "biocompiler.policy_component_selection_mrna_manifest.v0.1",
            "profile": request["profile"], "claim_scope": "bounded_complete_supplied_catalog_selection_to_exact_mrna",
            "premise": "supplied_component_composition_and_provider_contracts", "request": request, "candidate": proposed,
            "limits": limits, "assessment": report, "bindings": {
                "request_fingerprint": sha(canonical(request)), "candidate_fingerprint": sha(canonical(proposed)),
                "invocation_fingerprint": sha(canonical(invocation)), "assessment_fingerprint": sha(canonical(report))},
            "selected": {"id": winner, "request_fingerprint": sha(canonical(selected_original)),
                "candidate_fingerprint": sha(canonical(selected_candidate)), "assessment_fingerprint": sha(canonical(selected_report))},
            "members": [{"fasta_id": "rna_0001", "member_id": "payload", "molecule": molecule, "sequence_sha256": sha(sequence.encode())}],
            "fasta_sha256": sha(fasta.encode()), "empirical": "unassessed", "original_authority": "retain_original_inputs_separately"}
        assert manifest == expected
    # Exact stored events plus their repeated occurrences in the final result.
    # The transport request ID is not retained: enforce a conservative lower
    # bound here; actual complete-frame admission is authenticated hosted code.
    events = [*inner_values, report, *([value["artifact"]["manifest"]] if artifact else []), {"result": value}]
    sizes = [measured(event) for event in events]
    assert all(size <= 8388608 and nodes <= 250000 for size, nodes in sizes)
    assert sum(size for size, _ in sizes) <= request["budgets"]["max_report_bytes"]
    assert sum(nodes for _, nodes in sizes) <= request["budgets"]["max_report_nodes"]
    envelope_bytes, envelope_nodes = measured({"result": value})
    assert envelope_bytes <= 8323072 and envelope_nodes <= 249968

short_check = selection_values["check-verify"]
for name in ("check-core", "check-verify", "replay-core", "replay-verify"):
    assert selection_values[name] == short_check
    selection_result(selection_values[name], original, candidate, winner="short", maximum=17, artifact=False)
for name in ("export-core", "export-verify"):
    selection_result(selection_values[name], original, candidate, winner="short", maximum=17, artifact=True)
    assert selection_values[name]["report"] == short_check["report"]
assert selection_values["export-core"] == selection_values["export-verify"]
larger, long_candidate = deepcopy(original), deepcopy(candidate)
larger["predicate"]["max_total_nt"] = 18
long_candidate["selected_id"] = "long"
selection_result(selection_values["long-check"], larger, long_candidate, winner="long", maximum=18, artifact=False)
selection_result(selection_values["long-export"], larger, long_candidate, winner="long", maximum=18, artifact=True)
assert selection_values["long-export"]["report"] == selection_values["long-check"]["report"]
empty, none_candidate = deepcopy(original), deepcopy(candidate)
empty["predicate"]["max_total_nt"] = 16
none_candidate["selected_id"] = None
selection_result(selection_values["no-eligible-check"], empty, none_candidate, winner=None, maximum=16, artifact=False)
edited = deepcopy(original)
next(row for row in edited["alternatives"] if row["id"] == "long")["rank"] = 2
selection_result(selection_values["loser-rank-check"], edited, candidate, winner="short", maximum=17, artifact=False)
selection_result(selection_values["loser-rank-export"], edited, candidate, winner="short", maximum=17, artifact=True)
assert selection_values["loser-rank-export"]["report"] == selection_values["loser-rank-check"]["report"]
assert selection_values["loser-rank-export"]["artifact"]["fasta"] == selection_values["export-verify"]["artifact"]["fasta"]
assert selection_values["loser-rank-export"]["artifact"]["manifest_sha256"] != selection_values["export-verify"]["artifact"]["manifest_sha256"]
for name, status, code in (("no-eligible-export", "error", "policy_component_selection_export_not_accepted"),
    ("stale-replay", "error", "policy_component_selection_replay"),
    ("verify-no-selection-producer", "unsupported", "unsupported_operation"),
    ("core-no-selection-producer", "unsupported", "unsupported_operation")):
    record = selection_values[name]
    assert set(record) == {"status", "diagnostics"} and record["status"] == status
    assert [row["code"] for row in record["diagnostics"]] == [code]
selection_zipproof = []
for stem, export_name, receipt_name, sequence in (("core", "export-core", "paired-core", short_rna),
    ("verify", "export-verify", "paired-verify", short_rna), ("long", "long-export", "long-paired", long_rna),
    ("loser-rank", "loser-rank-export", "loser-rank-paired", short_rna)):
    raw = data["selection-sdk-witness/" + stem + "-program.zip"]
    pub, value = selection_values[receipt_name], selection_values[export_name]
    assert pub["sha256"] == sha(raw) and pub["bytes"] == len(raw)
    assert pub["fresh_result_fingerprint"] == sha(canonical(value))
    members = zip_data(raw, count=2, maximum=16 * 1024 * 1024, per_file=8 * 1024 * 1024,
        expected_names=["program.fasta", "manifest.json"])
    artifact = value["artifact"]
    assert members["program.fasta"] == artifact["fasta"].encode() == (">rna_0001 alphabet=RNA\n" + sequence + "\n").encode()
    assert members["manifest.json"] == canonical(artifact["manifest"])
    assert sha(members["program.fasta"]) == artifact["fasta_sha256"] and sha(members["manifest.json"]) == artifact["manifest_sha256"]
    assert pub["members"] == [{"name": name, "bytes": len(content), "sha256": sha(content)} for name, content in members.items()]
    selection_zipproof.append({"case": stem, "sequence": sequence, "zip": pin(raw), "members": pub["members"]})
assert data["selection-sdk-witness/core-program.zip"] == data["selection-sdk-witness/verify-program.zip"]

for record in (sdk, selection_sdk):
    for module, origin in record["parent_imports"].items():
        relative = origin.removeprefix(HOST)
        assert relative in contents and origin.startswith(HOST + "src/biocompiler/")
        allowed = {"biocompiler", "biocompiler.core_client", "biocompiler.core_policy", "biocompiler.core_policy_component_material",
            "biocompiler.core_policy_implementation", "biocompiler.core_policy_material", "biocompiler.core_policy_operational", "biocompiler.policy"}
        if record is selection_sdk:
            allowed.add("biocompiler.core_policy_component_selection")
        assert module in allowed or module.startswith("biocompiler.policy.")
assert {"biocompiler.core_client", "biocompiler.core_policy_component_selection", "biocompiler.policy.component_selection"} <= set(selection_sdk["parent_imports"])
expected_members = {"preparation.json", "feedback.json", "public-sdk.json", "sdk-witness.json", "component-originals.json",
    "selection-public-sdk.json", "selection-sdk-witness.json", "selection-originals.json",
    *(row["log"] for row in actions), *(row["path"] for row in sdk["observations"]),
    *(row["path"] for row in selection_sdk["observations"]), "sdk-witness/A-program.zip", "sdk-witness/B-program.zip",
    *("selection-sdk-witness/" + name + "-program.zip" for name in ("core", "verify", "long", "loser-rank"))}
assert len(expected_members) == 90 and set(data) == expected_members
proof = {"schema": "biocompiler.development_inert_audit.v0.2", "status": "passed", "acceptance": False,
    "identity": identity, "job": job["id"], "suite_id": args.suite_id, "artifact": {"id": art["id"], **pin(zipraw)},
    "source_files": len(sources), "source_snapshot_sha256": sha(canonical(sources)), "native_suites": 23, "native_binary_pin_records": 26,
    "sdk_observations": 26, "selection_sdk_observations": 21, "zip_programs": zipproof, "selection_zip_programs": selection_zipproof,
    "outer_entries": len(data), "outer_expanded_bytes": sum(map(len, data.values())), "outer_crc": "all_streamed",
    "binary_binding": public["binaries"], "limitations": [
        "Development feedback only, not installed, release, merged-main or selection-generation acceptance.",
        "Native binary bytes are not retained: records are cross-bound to hosted source/build snapshots, not independently rehashed locally.",
        "Independent inspection authenticates hosted records and exact exported data; native semantics were not replayed locally.",
        "Retained SDK values omit the raw transport request IDs. Full-frame admission is bound to the authenticated native implementation and hosted tests; local publication totals are conservative lower bounds.",
        "No clinical or biological viability claim."],
    "guard": {"native_execution": False, "product_imports": False, "processes_after_git_snapshot": False, "network": False,
        "optimize": sys.flags.optimize}, "inputs": {str(path.relative_to(OUT)): pin(path.read_bytes()) for path in (OUT / "api").iterdir() if path.is_file()},
    "auditor": pin(Path(__file__).read_bytes())}
target = OUT / ("inert-audit-proof-python-" + platform.python_version() + ".json")
assert not target.exists(), "Preserve earlier audit evidence"
target.write_text(json.dumps(proof, sort_keys=True, indent=2) + "\n")
print(json.dumps({"status": "passed", "native_suites": 23, "sdk_observations": 26,
    "selection_sdk_observations": 21, "proof_sha256": sha(target.read_bytes())}, sort_keys=True))
