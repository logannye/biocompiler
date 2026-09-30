/* Real-browser acceptance of the installed, loopback-only compiler workspace. */
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

async function main() {
  const output = path.resolve(process.env.STUDIO_TEST_OUTPUT || 'generated/studio-browser-ci');
  await fs.mkdir(output, { recursive: true });
  const outside = await fs.mkdtemp(path.join(os.tmpdir(), 'biocompiler-studio-test-'));
  const server = spawn(process.env.STUDIO_TEST_PYTHON || 'python3',
    ['-u', '-m', 'biocompiler', 'studio', '--port', '0', '--no-open'],
    { cwd: outside, env: process.env, stdio: ['ignore', 'pipe', 'pipe'] });
  let log = '';
  let browser;
  let page;
  const deadline = setTimeout(() => {
    server.kill('SIGTERM');
    console.error('Studio browser acceptance exceeded its 120-second limit.');
    process.exit(1);
  }, 120000);
  const evidence = { cases: [], layout: [] };
  try {
    const url = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Studio did not start: ' + log)), 15000);
      server.once('error', error => { clearTimeout(timeout); reject(error); });
      server.once('exit', code => { clearTimeout(timeout); reject(new Error('Studio exited ' + code + ': ' + log)); });
      server.stderr.on('data', chunk => { log += chunk; });
      server.stdout.on('data', chunk => {
        log += chunk;
        const match = log.match(/http:\/\/127\.0\.0\.1:\d+\//);
        if (match) { clearTimeout(timeout); resolve(match[0]); }
      });
    });
    browser = await chromium.launch({ headless: true });
    page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, acceptDownloads: true });
    const errors = [];
    const policyErrors = [];
    page.on('pageerror', error => errors.push(String(error)));
    page.on('console', message => {
      if (message.type() === 'error' && /Content Security Policy|Refused to|violates.*directive/i.test(message.text())) policyErrors.push(message.text());
    });
    await page.goto(url);
    await page.waitForFunction(() => !document.getElementById('compile-button').disabled);
    await page.screenshot({ path: path.join(output, 'first-run.png'), fullPage: true });

    async function compile(expectedSequence) {
      const response = page.waitForResponse(r => r.url().endsWith('/api/compile') && r.request().method() === 'POST');
      await page.locator('#compile-button').click();
      const body = await (await response).json();
      assert.equal(body.ok, true, JSON.stringify(body));
      await page.waitForFunction(() => !document.getElementById('result-content').hidden);
      if (expectedSequence !== null) {
        await page.waitForFunction(expected => document.getElementById('sequence').textContent.replace(/\s/g, '') === expected, expectedSequence);
      }
      assert.equal(body.result.summary.sequence, expectedSequence);
      assert.equal(body.result.summary.therapeutic_implementation, 'partial');
      assert.equal(body.result.summary.human_therapeutic_admission, 'not_admitted');
      return body.result;
    }
    async function exported(format) {
      const downloadEvent = page.waitForEvent('download');
      await page.locator('button[data-export="' + format + '"]').click();
      const download = await downloadEvent;
      const destination = path.join(output, download.suggestedFilename());
      await download.saveAs(destination);
      return await fs.readFile(destination, 'utf8');
    }

    const baseline = await compile('GGAUGGCUUAACCAAAA');
    evidence.cases.push({ case: 'guided baseline', fingerprint: baseline.summary.build_fingerprint });
    assert.equal(baseline.summary.unresolved.length, 22);
    await page.screenshot({ path: path.join(output, 'compiled-desktop.png'), fullPage: true });
    const requestText = await exported('request');
    assert.deepEqual(JSON.parse(requestText), baseline.request);
    const buildText = await exported('build');
    assert.deepEqual(JSON.parse(buildText), baseline.record);
    const fasta = await exported('fasta');
    assert.match(fasta, /therapeutic_implementation=partial/);
    assert.equal(fasta.split('\n').slice(1).join('').trim(), 'GGAUGGCUUAACCAAAA');

    await page.locator('input[name="product"][value="alternative_product"]').check();
    assert.equal(await page.locator('#result-content').isVisible(), false);
    assert.equal(await page.locator('button[data-export="fasta"]').isDisabled(), true);
    const alternate = await compile('GGAUGUUUUAACCAAAA');
    assert.notEqual(alternate.summary.build_fingerprint, baseline.summary.build_fingerprint);
    assert.equal(alternate.summary.protein, 'MF*');
    evidence.cases.push({ case: 'source edit changes coding sequence', fingerprint: alternate.summary.build_fingerprint });

    await page.locator('input[name="product"][value="declared_product"]').check();
    await page.locator('input[name="architecture"][value="extended"]').check();
    const extended = await compile('GGGGAUGGCUUAACCAAAA');
    assert.equal(extended.summary.architecture, 'extended');
    assert(extended.summary.alternatives.some(a => a.rejections.some(r => r.code === 'architecture_not_allowed')));
    evidence.cases.push({ case: 'architecture constraint changes layout', fingerprint: extended.summary.build_fingerprint });

    await page.locator('#max-length').fill('1');
    const exhausted = await compile(null);
    assert.equal(exhausted.summary.status, 'no_candidate_found');
    assert.equal(await page.locator('#no-candidate-help').isVisible(), true);
    assert.equal(await page.locator('#sequence-section').isVisible(), false);
    assert.equal(await page.locator('button[data-export="fasta"]').isDisabled(), true);
    assert.equal(exhausted.summary.alternatives.length, 2);
    await exported('build');
    evidence.cases.push({ case: 'valid empty search retains reasons and record', status: exhausted.summary.status });

    await page.locator('#max-length').fill('-1');
    await page.locator('#compile-button').click();
    await page.locator('#error-panel').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#result-content').isVisible(), false);
    evidence.cases.push({ case: 'invalid length has actionable error', status: 'pass' });

    await page.locator('#max-length').fill('');
    await page.locator('input[name="architecture"][value="auto"]').check();
    let releaseOld;
    let entered;
    const held = new Promise(resolve => { entered = resolve; });
    const gate = new Promise(resolve => { releaseOld = resolve; });
    await page.route('**/api/compile', async route => {
      const response = await route.fetch();
      entered();
      await gate;
      await route.fulfill({ response }).catch(() => {});
    });
    await page.locator('#compile-button').click();
    await held;
    await page.locator('input[name="product"][value="alternative_product"]').check();
    releaseOld();
    await page.unrouteAll({ behavior: 'wait' });
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await page.locator('#result-content').isVisible(), false);
    assert.equal(await page.locator('button[data-export="fasta"]').isDisabled(), true);
    await compile('GGAUGUUUUAACCAAAA');
    evidence.cases.push({ case: 'late compile cannot replace edited inputs', status: 'pass' });

    let releaseExport;
    let exportEntered;
    const exportHeld = new Promise(resolve => { exportEntered = resolve; });
    const exportGate = new Promise(resolve => { releaseExport = resolve; });
    const lateDownloads = [];
    const trackDownload = d => lateDownloads.push(d.suggestedFilename());
    page.on('download', trackDownload);
    await page.route('**/api/export', async route => {
      const response = await route.fetch();
      exportEntered();
      await exportGate;
      await route.fulfill({ response }).catch(() => {});
    });
    await page.locator('button[data-export="fasta"]').click();
    await exportHeld;
    await page.locator('input[name="product"][value="declared_product"]').check();
    releaseExport();
    await page.unrouteAll({ behavior: 'wait' });
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    page.off('download', trackDownload);
    assert.deepEqual(lateDownloads, []);
    evidence.cases.push({ case: 'late export cannot download an obsolete design', status: 'pass' });

    await page.locator('#import-panel > summary').click();
    await page.locator('#request-json').fill('{"broken":');
    await page.locator('#import-button').click();
    await page.locator('#error-panel').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#result-content').isVisible(), false);
    await page.locator('#request-file').setInputFiles({ name: 'original.request.json', mimeType: 'application/json', buffer: Buffer.from(requestText) });
    await page.locator('#import-button').click();
    await page.waitForFunction(() => document.getElementById('mode-badge').textContent.toLowerCase().includes('import'));
    const imported = await compile('GGAUGGCUUAACCAAAA');
    assert.deepEqual(imported.request, baseline.request);
    assert.equal(imported.summary.build_fingerprint, baseline.summary.build_fingerprint);
    assert.equal(await page.locator('#imported-constraints').isVisible(), true);
    evidence.cases.push({ case: 'file import preserves exact authority and result', status: 'pass' });

    const hostile = JSON.parse(requestText);
    hostile.library.id = '<img src=x onerror="window.studioInjected=true">';
    await page.locator('#request-json').fill(JSON.stringify(hostile));
    await page.locator('#import-button').click();
    await page.waitForFunction(() => document.getElementById('library-label').textContent.includes('<img'));
    assert.equal(await page.evaluate(() => !!window.studioInjected || !!document.querySelector('#library-label img')), false);
    await compile('GGAUGGCUUAACCAAAA');
    evidence.cases.push({ case: 'imported labels remain literal text', status: 'pass' });

    for (const width of [1440, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      const layout = await page.evaluate(() => ({
        width: innerWidth,
        bodyWidth: document.documentElement.scrollWidth,
        visibleControls: [...document.querySelectorAll('button,input,select,textarea')].filter(e => e.getClientRects().length).filter(e => { const r=e.getBoundingClientRect();return r.left < -1 || r.right > innerWidth+1; }).map(e => e.id || e.name),
      }));
      assert(layout.bodyWidth <= width + 1, JSON.stringify(layout));
      assert.deepEqual(layout.visibleControls, []);
      evidence.layout.push(layout);
    }
    await page.screenshot({ path: path.join(output, 'compiled-mobile.png'), fullPage: true });
    await page.locator('#example-button').click();
    assert.equal(await page.locator('#result-content').isVisible(), false);
    evidence.cases.push({ case: 'return to guided example clears imported result', status: 'pass' });
    assert.deepEqual(errors, []);
    assert.deepEqual(policyErrors, []);
    evidence.runtimeErrors = errors;
    evidence.contentPolicyErrors = policyErrors;
    await fs.writeFile(path.join(output, 'browser-evidence.json'), JSON.stringify(evidence, null, 2) + '\n');
    console.log(JSON.stringify(evidence, null, 2));
  } catch (error) {
    if (page) await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }).catch(() => {});
    throw error;
  } finally {
    clearTimeout(deadline);
    if (browser) await browser.close();
    server.kill('SIGTERM');
    await fs.writeFile(path.join(output, 'server.log'), log);
    await fs.rm(outside, { recursive: true, force: true });
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
