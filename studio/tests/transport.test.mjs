import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../', import.meta.url));
const runtime = await readFile(path.join(root, 'src/biocompiler/studio/static/transport.js'));
const { authorityText, decodeResponse, errorInfo, exportFormat } = await import(`data:text/javascript;base64,${runtime.toString('base64')}`);
const fixtures = JSON.parse(execFileSync(process.env.STUDIO_TEST_PYTHON || 'python3',
  [path.join(root, 'studio/tests/fixtures.py')], {
    cwd: root, encoding: 'utf8', maxBuffer: 16 * 1024 * 1024,
    env: { ...process.env, PYTHONPATH: (process.env.STUDIO_TEST_SOURCE === '1'
      ? [path.join(root, 'src'), root] : [root]).join(path.delimiter) },
  }));

test('all live Python Studio response shapes decode without rewriting their values', () => {
  for (const [route, name] of [
    ['/api/session', 'session'], ['/api/prepare', 'prepared'], ['/api/compile', 'compiled'],
    ['/api/export', 'exported'], ['/api/construction/inspect', 'historical'],
    ['/api/construction/inspect', 'reviewed'], ['/api/construction/save', 'saved'],
  ]) {
    assert.equal(decodeResponse(route, { ok: true, result: fixtures[name] }), fixtures[name]);
  }
  assert.equal(fixtures.reviewed.review.evidence.status, 'current');
  assert.equal(fixtures.historical.freshness.assessment, null);
});

test('authority strings retain BOM, CRLF, numeric spellings and hostile labels', () => {
  const raw = '\ufeff{\r\n  "integer": 9007199254740993, "float": 1.0, "label": "<script>bad()</script>"\r\n}\r\n';
  const result = { ...fixtures.compiled, request_json: authorityText(raw), record_json: authorityText(raw) };
  const envelope = JSON.parse(JSON.stringify({ ok: true, result }));
  const decoded = decodeResponse('/api/compile', envelope);
  assert.equal(decoded.request_json, raw);
  assert.equal(decoded.record_json, raw);
  assert.equal(Buffer.compare(Buffer.from(decoded.request_json), Buffer.from(raw)), 0);
  assert.throws(() => authorityText({}), /invalid Studio response/);
  assert.equal(decodeResponse('/api/construction/save', { ok: true, result: fixtures.saved }).build_json.endsWith('\r\n'), true);
});

test('malformed envelopes and rendered nested data fail before UI acceptance', () => {
  for (const envelope of [null, [], {}, { ok: 'true', result: fixtures.session }, { ok: true },
    { ok: true, result: { ...fixtures.session, token: null } }]) {
    assert.throws(() => decodeResponse('/api/session', envelope), /invalid Studio response/);
  }
  for (const mutate of [
    value => { value.summary.parts[0].start = 'zero'; },
    value => { value.summary.unresolved[0].description = {}; },
    value => { value.summary.alternatives[0].selected = 1; },
    value => { value.record_json = {}; },
    value => { value.summary.length_nt = Infinity; },
  ]) {
    const result = structuredClone(fixtures.compiled); mutate(result);
    assert.throws(() => decodeResponse('/api/compile', { ok: true, result }), /invalid Studio response/);
  }
  const result = structuredClone(fixtures.reviewed);
  result.review.evidence.sources[0].observations[0].requirement_id = null;
  assert.throws(() => decodeResponse('/api/construction/inspect', { ok: true, result }), /invalid Studio response/);
});

test('HTTP failures retain diagnostics and never become successful results', () => {
  let error;
  try { decodeResponse('/api/session', { ok: false, error: { message: 'Changed authority', code: 'stale', details: { field: 'request' } } }, 409); }
  catch (caught) { error = caught; }
  assert.deepEqual(errorInfo(error), { name: 'StudioError', message: 'Changed authority', code: 'stale', details: { field: 'request' } });
  assert.throws(() => decodeResponse('/api/session', { ok: true, result: fixtures.session }, 500), /HTTP 500/);
  for (const format of ['request', 'build', 'fasta']) assert.equal(exportFormat(format), format);
  assert.throws(() => exportFormat('../fasta'), /Unknown Studio export/);
});
