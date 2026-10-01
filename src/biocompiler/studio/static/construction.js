/* Read-only artifact transport. Authority JSON is never parsed in the browser. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const maxBytes = 1024 * 1024;
  let token = null, revision = 0, inspected = null, controller = null;
  const rawFiles = new Map();
  const fileReads = new Map();
  const records = ['build', 'authority', 'source-inventory', 'binding-request', 'evidence-request', 'evidence-receipt'];
  const inputs = records.flatMap(id => [id + '-json', id + '-file']);
  function invalidate(message = 'Inputs changed. Inspect again before saving.') {
    revision += 1;
    controller?.abort(); controller = null; inspected = null;
    $('result').hidden = true; $('empty').hidden = false;
    $('save').disabled = true; $('inspection').setAttribute('aria-busy', 'false');
    $('inspect').disabled = !token || fileReads.size > 0; $('status').textContent = message;
    $('error').hidden = true;
  }
  function error(err) { $('error').textContent = err.message; $('error').hidden = false; }
  function payload() {
    const original = id => {
      const raw = rawFiles.get(id), value = $(id).value;
      return raw && raw.view === value ? raw.text : value;
    };
    const documents = Object.fromEntries(records.map(id => [id, original(id + '-json')]));
    for (const text of Object.values(documents)) {
      if (new TextEncoder().encode(text).length > maxBytes) throw new Error('Each input must be at most 1 MiB.');
    }
    const optional = id => documents[id].trim() ? documents[id] : null;
    return { build_json: documents.build, expected_request_json: optional('authority'),
      review: Object.fromEntries(records.slice(2).map(id => [id.replaceAll('-', '_') + '_json', optional(id)])),
    };
  }
  async function post(route, body, signal) {
    const document = JSON.stringify(body);
    if (new TextEncoder().encode(document).length > 2 * maxBytes) throw new Error('Encoded operation exceeds 2 MiB.');
    const response = await fetch(route, { method: 'POST', signal, headers: {
      'Content-Type': 'application/json', 'X-Biocompiler-Token': token,
    }, body: document });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error?.message || 'The local operation failed.');
    return result.result;
  }
  function rows(id, data) {
    const fragment = document.createDocumentFragment();
    for (const values of data) {
      const row = document.createElement('tr');
      for (const value of values) { const cell = document.createElement('td'); cell.textContent = String(value); row.append(cell); }
      fragment.append(row);
    }
    $(id).replaceChildren(fragment);
  }
  function list(id, values, fallback) {
    $(id).replaceChildren(...(values.length ? values : [fallback]).map(text => {
      const item = document.createElement('li'); item.textContent = text; return item;
    }));
  }
  function renderReview(review) {
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
    const missing = { missing_authority: 'Not checked — current independent evidence authority is missing.', missing_receipt: 'Not checked — historical evidence receipt is missing.' };
    $('evidence-status').textContent = missing[evidence.status] || 'Dependency freshness: ' + evidence.status + '. Model prediction: unsupported.';
    rows('evidence-dependencies', (evidence.dependencies || []).map(d => [d.id, d.status]));
    rows('evidence-sources', evidence.sources.map(s => [s.id, s.kind, s.use, s.observations.map(o => o.requirement_id + ': ' + o.observation_id).join('; ') || 'None declared']));
    $('evidence-details').textContent = JSON.stringify(evidence, null, 2);
  }
  function render(report) {
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
  for (const id of records.map(name => name + '-json')) $(id).addEventListener('input', () => { fileReads.delete(id); rawFiles.delete(id); invalidate(); });
  for (const [fileId, textId] of records.map(name => [name + '-file', name + '-json'])) {
    $(fileId).addEventListener('change', async () => {
      const readId = {}, file = $(fileId).files[0];
      rawFiles.delete(textId); fileReads.delete(textId); $(textId).value = '';
      if (file) fileReads.set(textId, readId);
      invalidate(file ? 'Reading the selected file…' : 'Choose a saved build to begin.');
      if (!file) return;
      try {
        if (file.size > maxBytes) throw new Error('File exceeds 1 MiB.');
        const text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(await file.arrayBuffer());
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
    } catch (err) { if (revision === current && err.name !== 'AbortError') error(err); }
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
    } catch (err) { if (current === revision && err.name !== 'AbortError') error(err); }
    finally { if (current === revision && inspected) $('save').disabled = false; }
  });
  fetch('/api/session').then(response => response.json()).then(session => {
    if (!session.ok) throw new Error('Could not connect to the local workspace.');
    token = session.result.token; inputs.forEach(id => { $(id).disabled = false; }); $('inspect').disabled = false;
    $('connection').textContent = 'Connected locally. Files stay in this workspace.';
  }).catch(error);
})();
