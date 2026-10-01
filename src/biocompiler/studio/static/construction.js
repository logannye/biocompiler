/* Read-only artifact transport. Authority JSON is never parsed in the browser. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const maxBytes = 1024 * 1024;
  let token = null, revision = 0, inspected = null, controller = null;
  const rawFiles = new Map();
  const fileReads = new Map();
  const inputs = ['build-json', 'authority-json', 'build-file', 'authority-file'];
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
    const build = original('build-json'), authority = original('authority-json');
    for (const text of [build, authority]) {
      if (new TextEncoder().encode(text).length > maxBytes) throw new Error('Each input must be at most 1 MiB.');
    }
    return { build_json: build, expected_request_json: authority.trim() ? authority : null };
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
    $('empty').hidden = true; $('result').hidden = false;
  }
  for (const id of ['build-json', 'authority-json']) $(id).addEventListener('input', () => { fileReads.delete(id); rawFiles.delete(id); invalidate(); });
  for (const [fileId, textId] of [['build-file', 'build-json'], ['authority-file', 'authority-json']]) {
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
