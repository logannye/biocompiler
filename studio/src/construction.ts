import { authorityText, decodeResponse, element, errorInfo } from "./transport.js";
import type { AuthorityText, ConstructionInspection, ConstructionPayload, ConstructionReview, Fingerprint, RequestByRoute, ResponseFor } from "./transport.js";
type ConstructionRoute = "/api/construction/inspect" | "/api/construction/save";
interface InspectedSnapshot { body: ConstructionPayload; fingerprint: Fingerprint }
interface RawFile { text: AuthorityText; view: string }
/* Read-only artifact transport. Authority JSON is never parsed in the browser. */
(() => {
  'use strict';
const tags = {
  "workspace": "main",
  "connection": "p",
  "error": "p",
  "inputs-title": "h2",
  "build-file": "input",
  "build-json": "textarea",
  "construction-authority": "details",
  "authority-file": "input",
  "authority-json": "textarea",
  "review-inputs": "details",
  "source-inventory-file": "input",
  "source-inventory-json": "textarea",
  "binding-request-file": "input",
  "binding-request-json": "textarea",
  "evidence-request-file": "input",
  "evidence-request-json": "textarea",
  "evidence-receipt-file": "input",
  "evidence-receipt-json": "textarea",
  "inspect": "button",
  "save": "button",
  "status": "p",
  "inspection": "section",
  "inspection-title": "h2",
  "empty": "p",
  "result": "div",
  "freshness": "p",
  "identity": "dd",
  "stored-outcome": "dd",
  "current-outcome": "dd",
  "review-title": "h3",
  "software-track": "dd",
  "reference-track": "dd",
  "human-track": "dd",
  "prediction-track": "dd",
  "review-table-help": "p",
  "source-review": "section",
  "source-title": "h4",
  "source-status": "p",
  "source-diagnostics": "ul",
  "source-gaps": "tbody",
  "source-details": "pre",
  "binding-review": "section",
  "binding-title": "h4",
  "binding-status": "p",
  "binding-rows": "tbody",
  "binding-diagnostics": "ul",
  "binding-details": "pre",
  "evidence-review": "section",
  "evidence-title": "h4",
  "evidence-status": "p",
  "evidence-dependencies": "tbody",
  "evidence-sources": "tbody",
  "evidence-details": "pre",
  "members": "tbody",
  "roles": "tbody",
  "diagnostics": "ul",
  "maps": "pre",
  "authority-view": "pre"
} as const;
type ElementId = keyof typeof tags;
function $<K extends ElementId>(id: K): HTMLElementTagNameMap[(typeof tags)[K]] { return element(id, tags[id]); }

  const maxBytes = 1024 * 1024;
  let token: string | null = null, revision = 0;
  let inspected: InspectedSnapshot | null = null, controller: AbortController | null = null;
  const rawFiles = new Map<string, RawFile>();
  const fileReads = new Map<string, object>();
  const records = ['build', 'authority', 'source-inventory', 'binding-request', 'evidence-request', 'evidence-receipt'] as const;
  const inputs = records.flatMap(id => [`${id}-json`, `${id}-file`] as const);
  function invalidate(message = 'Inputs changed. Inspect again before saving.') {
    revision += 1;
    controller?.abort(); controller = null; inspected = null;
    $('result').hidden = true; $('empty').hidden = false;
    $('save').disabled = true; $('inspection').setAttribute('aria-busy', 'false');
    $('inspect').disabled = !token || fileReads.size > 0; $('status').textContent = message;
    $('error').hidden = true;
  }
  function error(err: unknown) { $('error').textContent = errorInfo(err).message; $('error').hidden = false; }
  function payload(): ConstructionPayload {
    const original = (id: `${typeof records[number]}-json`): AuthorityText => {
      const raw = rawFiles.get(id), value = $(id).value;
      return raw && raw.view === value ? raw.text : authorityText(value);
    };
    const documents = new Map(records.map(id => [id, original(`${id}-json`)]));
    for (const text of documents.values()) {
      if (new TextEncoder().encode(text).length > maxBytes) throw new Error('Each input must be at most 1 MiB.');
    }
    const required = (id: typeof records[number]): AuthorityText => {
      const value = documents.get(id);
      if (value === undefined) throw new Error(`Missing construction input: ${id}.`);
      return value;
    };
    const optional = (id: typeof records[number]): AuthorityText | null => {
      const value = required(id); return value.trim() ? value : null;
    };
    return { build_json: required('build'), expected_request_json: optional('authority'),
      review: {
        source_inventory_json: optional('source-inventory'), binding_request_json: optional('binding-request'),
        evidence_request_json: optional('evidence-request'), evidence_receipt_json: optional('evidence-receipt'),
      },
    };
  }
  async function post<K extends ConstructionRoute>(route: K, body: RequestByRoute[K], signal: AbortSignal): Promise<ResponseFor<K>> {
    if (!token) throw new Error("The Studio session is missing. Reload the page.");
    const document = JSON.stringify(body);
    if (new TextEncoder().encode(document).length > 2 * maxBytes) throw new Error('Encoded operation exceeds 2 MiB.');
    const response = await fetch(route, { method: 'POST', signal, headers: {
      'Content-Type': 'application/json', 'X-Biocompiler-Token': token,
    }, body: document });
    const result: unknown = await response.json();
    return decodeResponse(route, result, response.status);
  }
  function rows(id: ElementId, data: unknown[][]) {
    const fragment = document.createDocumentFragment();
    for (const values of data) {
      const row = document.createElement('tr');
      for (const value of values) { const cell = document.createElement('td'); cell.textContent = String(value); row.append(cell); }
      fragment.append(row);
    }
    $(id).replaceChildren(fragment);
  }
  function list(id: ElementId, values: string[], fallback: string) {
    $(id).replaceChildren(...(values.length ? values : [fallback]).map(text => {
      const item = document.createElement('li'); item.textContent = text; return item;
    }));
  }
  function renderReview(review: ConstructionReview) {
    const source = review.sources, bindings = review.bindings, evidence = review.evidence;
    $('software-track').textContent = 'See each current structural, metadata and nominal check below.';
    $('reference-track').textContent = 'Not established';
    $('human-track').textContent = 'Unassessed; human therapeutic admission is not granted.';
    $('prediction-track').textContent = 'Unsupported';
    const readiness = source.readiness;
    $('source-status').textContent = readiness ? 'Metadata consistency: ' + readiness.metadata_consistency + '. Reference case readiness: not established.' : 'Not checked — current source inventory is missing.';
    list('source-diagnostics', readiness?.diagnostics || [], readiness ? 'No metadata consistency diagnostics. Scientific acceptance remains unresolved.' : 'Supply an inventory to inspect its metadata and missing fields.');
    rows('source-gaps', (readiness?.cases || []).flatMap(c => c.fields.map(f => [c.case_id, f.field, f.availability + ' (unverified)', f.note])));
    $('source-details').textContent = JSON.stringify(readiness || { status: source.status }, null, 2);
    $('binding-status').textContent = bindings.assessment ? 'Nominal correspondence: ' + bindings.assessment.outcome + '.' : 'Not checked — independent binding authority is missing.';
    rows('binding-rows', bindings.bindings.map(b => [b.requirement_id, b.source_kind + ': ' + b.source_id, b.construction_requirement_id, b.role_id]));
    list('binding-diagnostics', bindings.assessment?.diagnostics || [], bindings.assessment ? 'No nominal binding diagnostics.' : 'Supply the complete binding request to check requirement and role correspondence.');
    $('binding-details').textContent = JSON.stringify(bindings, null, 2);
    const missing: Readonly<Record<string, string>> = { missing_authority: 'Not checked — current independent evidence authority is missing.', missing_receipt: 'Not checked — historical evidence receipt is missing.' };
    $('evidence-status').textContent = missing[evidence.status] || 'Dependency freshness: ' + evidence.status + '. Model prediction: unsupported.';
    rows('evidence-dependencies', (evidence.dependencies || []).map(d => [d.id, d.status]));
    rows('evidence-sources', evidence.sources.map(s => [s.id, s.kind, s.use, s.observations.map(o => o.requirement_id + ': ' + o.observation_id).join('; ') || 'None declared']));
    $('evidence-details').textContent = JSON.stringify(evidence, null, 2);
  }
  function render(report: ConstructionInspection) {
    $('identity').textContent = report.build_fingerprint;
    $('stored-outcome').textContent = report.stored_assessment.outcome + ' (historical)';
    const replay = report.freshness.assessment;
    $('freshness').textContent = replay ? 'Replayed against supplied independent authority.' : 'Historical record — independent authority was not replayed.';
    $('current-outcome').textContent = replay ? replay.outcome + ' — supplied structural correspondence only' : 'Not assessed';
    rows('members', report.molecules.map(m => [m.id, m.form, m.space.alphabet, m.space.topology, m.space.length]));
    rows('roles', report.request.required_members.map(r => [r.id, r.category, r.member_id || r.external_id, r.roles.map(v => v.role + ' · ' + v.compartment).join('; ')]));
    const diagnostics = [...report.missing_members, ...report.construction_diagnostics, ...(replay || report.stored_assessment).diagnostics];
    $('diagnostics').replaceChildren(...(diagnostics.length ? diagnostics : ['No structural diagnostics recorded. Biological function and human admission remain unresolved.']).map(text => { const item = document.createElement('li'); item.textContent = text; return item; }));
    $('maps').textContent = JSON.stringify({roots: report.roots, steps: report.steps, values: report.values, molecules: report.molecules, complexes: report.complexes, amounts: report.amounts}, null, 2);
    $('authority-view').textContent = JSON.stringify({request: report.request, claims: report.claims}, null, 2);
    renderReview(report.review);
    $('empty').hidden = true; $('result').hidden = false;
  }
  for (const id of records.map(name => `${name}-json` as const)) $(id).addEventListener('input', () => { fileReads.delete(id); rawFiles.delete(id); invalidate(); });
  for (const [fileId, textId] of records.map(name => [`${name}-file`, `${name}-json`] as const)) {
    $(fileId).addEventListener('change', async () => {
      const readId = {}, file = $(fileId).files?.[0];
      rawFiles.delete(textId); fileReads.delete(textId); $(textId).value = '';
      if (file) fileReads.set(textId, readId);
      invalidate(file ? 'Reading the selected file…' : 'Choose a saved build to begin.');
      if (!file) return;
      try {
        if (file.size > maxBytes) throw new Error('File exceeds 1 MiB.');
        const text = authorityText(new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(await file.arrayBuffer()));
        if (fileReads.get(textId) === readId) {
          $(textId).value = text;
          // Textareas normalize line endings. Preserve the exact valid UTF-8
          // import until the user edits its visible representation.
          rawFiles.set(textId, { text, view: $(textId).value });
        }
      } catch (err) { if (fileReads.get(textId) === readId) error(err); }
      finally {
        if (fileReads.get(textId) === readId) {
          fileReads.delete(textId); $('inspect').disabled = !token || fileReads.size > 0;
          $('status').textContent = 'File read finished. Inspect the current inputs.';
        }
      }
    });
  }
  $('inspect').addEventListener('click', async () => {
    invalidate('Inspecting the retained record…'); const current = revision;
    controller = new AbortController(); $('inspection').setAttribute('aria-busy', 'true'); $('inspect').disabled = true;
    try {
      const body = payload();
      const report = await post('/api/construction/inspect', body, controller.signal);
      if (revision !== current) return;
      inspected = { body, fingerprint: report.build_fingerprint }; render(report);
      $('save').disabled = false; $('status').textContent = 'Inspection ready. Save preserves the original artifact.';
    } catch (err) { if (revision === current && errorInfo(err).name !== 'AbortError') error(err); }
    finally { if (revision === current) { $('inspection').setAttribute('aria-busy', 'false'); $('inspect').disabled = false; } }
  });
  $('save').addEventListener('click', async () => {
    if (!inspected) return;
    const current = revision, snapshot = inspected;
    controller = new AbortController(); $('save').disabled = true;
    try {
      const saved = await post('/api/construction/save', {...snapshot.body, expected_build_fingerprint: snapshot.fingerprint}, controller.signal);
      if (current !== revision || inspected !== snapshot) return;
      const url = URL.createObjectURL(new Blob([saved.build_json], { type: 'application/json' }));
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'construction.build.json'; anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000); $('status').textContent = 'Original build saved. No deployment admission is granted.';
    } catch (err) { if (current === revision && errorInfo(err).name !== 'AbortError') error(err); }
    finally { if (current === revision && inspected) $('save').disabled = false; }
  });
  fetch('/api/session').then(async response => decodeResponse('/api/session', await response.json(), response.status)).then(session => {
    token = session.token; inputs.forEach(id => { $(id).disabled = false; }); $('inspect').disabled = false;
    $('connection').textContent = 'Connected locally. Files stay in this workspace.';
  }).catch(error);
})();
