/* Hosted inspection/review suites; artificial software fixtures only. */
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

async function main() {
  const suite = process.env.CONSTRUCTION_BROWSER_SUITE || 'inspection';
  assert(['inspection', 'review'].includes(suite), 'Unknown construction browser suite: ' + suite);
  const artifactPrefix = suite === 'inspection' ? 'construction' : 'construction-review';
  const output = path.resolve(process.env.STUDIO_TEST_OUTPUT || 'generated/studio-browser-ci');
  const fixtures = path.resolve(process.env.CIRCUIT_INFRASTRUCTURE_OUTPUT || 'generated/circuit-infrastructure-ci');
  // CRLF catches browser textarea normalization; save must retain original bytes.
  const build = (await fs.readFile(path.join(fixtures, 'build.json'), 'utf8')).replaceAll('\n', '\r\n');
  const visibleBuild = build.replaceAll('\r\n', '\n');
  const authority = await fs.readFile(path.join(fixtures, 'request.json'), 'utf8');
  await fs.mkdir(output, { recursive: true });
  const outside = await fs.mkdtemp(path.join(os.tmpdir(), 'biocompiler-inspection-test-'));
  const server = spawn(process.env.STUDIO_TEST_PYTHON || 'python3',
    ['-u', '-m', 'biocompiler', 'studio', '--port', '0', '--no-open'],
    { cwd: outside, env: process.env, stdio: ['ignore', 'pipe', 'pipe'] });
  let log = '', browser, page;
  const evidence = { scope: 'artificial_software_contracts_only', suite, cases: [], layout: [] };
  const started = Date.now();
  const mark = name => { evidence.cases.push(name); console.log(Math.round((Date.now() - started) / 1000) + 's: ' + name); };
  const deadline = setTimeout(async () => {
    console.error('Construction ' + suite + ' browser acceptance exceeded 300 seconds.', evidence.cases);
    if (page) await page.screenshot({ path: path.join(output, artifactPrefix + '-timeout.png'), fullPage: true, timeout: 5000 }).catch(() => {});
    await fs.writeFile(path.join(output, artifactPrefix + '-timeout.json'), JSON.stringify(evidence, null, 2));
    server.kill('SIGTERM'); process.exit(1);
  }, 300000);
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
    page.setDefaultTimeout(45000);
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    page.on('console', message => {
      if (message.type() === 'error' && /Content Security Policy|Refused to|violates.*directive/i.test(message.text())) errors.push(message.text());
    });
    await page.goto(url + 'construction');
    await page.waitForFunction(() => !document.getElementById('inspect').disabled);
    if (suite === 'inspection') {
      assert.equal(await page.locator('#empty').isVisible(), true);
      assert.equal(await page.locator('#save').isDisabled(), true);
      await page.keyboard.press('Tab');
      assert.equal(await page.locator('.skip-link').evaluate(e => e === document.activeElement), true);
      await page.keyboard.press('Enter');
      assert.equal(await page.locator('label[for="build-json"]').count(), 1);
      await page.screenshot({ path: path.join(output, artifactPrefix + '-empty.png'), fullPage: true });
    }

    // File input exercises the intended path for large retained artifacts.
    // Prior CI timed out filling a 250 KiB #build-json outside any details.
    // The log did not establish why actionability stalled. Assert control state
    // explicitly, and keep real keyboard edits separate from large fixture setup.
    async function load(name, text) {
      assert.equal(await page.locator('#' + name + '-json').isVisible(), true, name + ' textarea must be visible');
      assert.equal(await page.locator('#' + name + '-json').isEnabled(), true, name + ' textarea must be enabled');
      await page.locator('#' + name + '-file').setInputFiles({ name: name + '.json', mimeType: 'application/json', buffer: Buffer.from(text) });
      await page.waitForFunction(({name, text}) => document.getElementById(name + '-json').value === text.replaceAll('\r\n', '\n') && !document.getElementById('inspect').disabled, {name, text});
    }
    async function inspect() {
      const response = page.waitForResponse(r => r.url().endsWith('/api/construction/inspect') && r.request().method() === 'POST');
      await page.locator('#inspect').click();
      const body = await (await response).json();
      assert.equal(body.ok, true, JSON.stringify(body));
      await page.locator('#result').waitFor({ state: 'visible' });
      assert.equal(body.result.claims.human_therapeutic_admission, 'not_admitted');
      return body.result;
    }
    if (suite === 'inspection') {
      await page.locator('#build-json').fill('{broken');
      await page.locator('#inspect').click();
      await page.locator('#error').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#save').isDisabled(), true);
      mark('invalid imports have an accessible error and cannot be saved');

      await page.locator('#build-file').setInputFiles({ name: 'invalid-utf8.json', mimeType: 'application/json', buffer: Buffer.from([0xff]) });
      await page.locator('#error').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#save').isDisabled(), true);
      mark('invalid UTF-8 is rejected without silent replacement');

      await page.evaluate(() => {
        window.originalFileReader = File.prototype.arrayBuffer;
        File.prototype.arrayBuffer = async function() {
          window.fileReadEntered = true;
          await new Promise(resolve => { window.releaseFileRead = resolve; });
          return window.originalFileReader.call(this);
        };
      });
      await page.locator('#build-file').setInputFiles({ name: 'slow.json', mimeType: 'application/json', buffer: Buffer.from(build) });
      await page.waitForFunction(() => window.fileReadEntered);
      assert.equal(await page.locator('#inspect').isDisabled(), true);
      assert.equal(await page.locator('#build-json').inputValue(), '');
      await page.locator('#build-json').fill('{edited while reading');
      await page.evaluate(() => { window.releaseFileRead(); File.prototype.arrayBuffer = window.originalFileReader; });
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.equal(await page.locator('#build-json').inputValue(), '{edited while reading');
      mark('pending file reads block old inspection and cannot replace later edits');

      await page.locator('#build-file').setInputFiles({ name: 'build.json', mimeType: 'application/json', buffer: Buffer.from(build) });
      await page.waitForFunction(expected => document.getElementById('build-json').value === expected, visibleBuild);
      const historical = await inspect();
      assert.equal(historical.freshness.status, 'not_replayed');
      assert.match(await page.locator('#stored-outcome').textContent(), /historical/);
      assert.equal(await page.locator('#current-outcome').textContent(), 'Not assessed');
      mark('stored PASS remains historical without external authority');

      await page.locator('#construction-authority > summary').click();
      await page.locator('#authority-file').setInputFiles({ name: 'request.json', mimeType: 'application/json', buffer: Buffer.from(authority) });
      await page.waitForFunction(expected => document.getElementById('authority-json').value === expected, authority);
      assert.equal(await page.locator('#result').isVisible(), false);
      const replay = await inspect();
      assert.equal(replay.freshness.status, 'replayed_external_authority');
      assert.equal(replay.freshness.assessment.outcome, 'pass');
      mark('fresh independent replay remains structural only');

      const downloadEvent = page.waitForEvent('download');
      await page.locator('#save').click();
      const download = await downloadEvent;
      const saved = path.join(output, 'construction.saved.json');
      await download.saveAs(saved);
      assert.equal(await fs.readFile(saved, 'utf8'), build);
      await page.locator('#build-file').setInputFiles(saved);
      await page.waitForFunction(expected => document.getElementById('build-json').value === expected, visibleBuild);
      assert.equal((await inspect()).build_fingerprint, replay.build_fingerprint);
      mark('save and reopen preserve original bytes and identity');

      async function rejectLate(routeName, button, saving) {
        let release, entered;
        const held = new Promise(resolve => { entered = resolve; });
        const gate = new Promise(resolve => { release = resolve; });
        const downloads = [];
        const listener = d => downloads.push(d.suggestedFilename());
        page.on('download', listener);
        await page.route('**/api/construction/' + routeName, async route => {
          const response = await route.fetch(); entered(); await gate;
          await route.fulfill({ response }).catch(() => {});
        });
        await page.locator(button).click(); await held;
        if (!saving) assert.equal(await page.locator('#inspection').getAttribute('aria-busy'), 'true');
        await page.locator('#authority-json').press('ControlOrMeta+End');
        await page.locator('#authority-json').press('Enter');
        release(); await page.unrouteAll({ behavior: 'wait' });
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        assert.equal(await page.locator('#result').isVisible(), false);
        assert.equal(await page.locator('#save').isDisabled(), true);
        assert.deepEqual(downloads, []);
        page.off('download', listener);
        await load('authority', authority);
        await inspect();
      }
      await rejectLate('inspect', '#inspect', false);
      await rejectLate('save', '#save', true);
      mark('late inspection and save responses cannot publish edited inputs');

      // Adversarial labels are transported as literal text even inside historical artifacts.
      const hostile = await fs.readFile(path.join(fixtures, 'hostile-label.build.json'), 'utf8');
      await page.locator('#authority-json').fill('');
      await load('build', hostile);
      await inspect();
      assert.match(await page.locator('#authority-view').textContent(), /<img src=x/);
      assert.equal(await page.evaluate(() => !!window.injected || !!document.querySelector('#result img')), false);
      await load('build', build);
      await load('authority', authority);
      await inspect();
      mark('adversarial altered imports cannot inject HTML');
    }

    if (suite === 'review') {
      const sourceFixtures = path.resolve(process.env.CIRCUIT_SOURCES_OUTPUT || 'generated/circuit-sources-ci');
      const sourceInventory = await fs.readFile(path.join(sourceFixtures, 'inventory.json'), 'utf8');
      const bindingRequest = await fs.readFile(path.join(fixtures, 'binding-request.json'), 'utf8');
      const evidenceRequest = await fs.readFile(path.join(fixtures, 'evidence-request.json'), 'utf8');
      const evidenceReceipt = await fs.readFile(path.join(fixtures, 'evidence-receipt.json'), 'utf8');
      const correctedEvidence = await fs.readFile(path.join(fixtures, 'corrected-evidence-request.json'), 'utf8');
      await load('build', build);
      await page.locator('#construction-authority > summary').click();
      await load('authority', authority);
      await page.locator('#review-inputs > summary').click();
      for (const name of ['source-inventory', 'binding-request', 'evidence-request', 'evidence-receipt']) {
        assert.equal(await page.locator('label[for="' + name + '-json"]').count(), 1);
      }
      await load('source-inventory', sourceInventory);
      await load('binding-request', bindingRequest);
      await load('evidence-request', evidenceRequest);
      await load('evidence-receipt', evidenceReceipt);
      const reviewed = await inspect();
      assert.equal(reviewed.review.sources.readiness.metadata_consistency, 'pass');
      assert.equal(await page.locator('#source-gaps tr').count(), 9);
      assert.equal(reviewed.review.sources.build_correspondence, 'not_established');
      assert.match(await page.locator('#reference-track').textContent(), /Not established/);
      assert.match(await page.locator('#human-track').textContent(), /not granted/);
      assert.equal(reviewed.review.bindings.assessment.outcome, 'pass');
      assert.equal(reviewed.review.evidence.status, 'current');
      assert.match(await page.locator('#evidence-sources').textContent(), /reference_only/);
      assert.equal(await page.locator('#prediction-track').textContent(), 'Unsupported');
      mark('source gaps, nominal bindings and evidence are separate current software checks');

      await load('evidence-request', correctedEvidence);
      assert.equal(await page.locator('#result').isVisible(), false);
      assert.equal(await page.locator('#save').isDisabled(), true);
      assert.equal((await inspect()).review.evidence.status, 'stale');
      assert.match(await page.locator('#evidence-dependencies').textContent(), /stale/);
      await page.locator('#evidence-receipt-json').fill('');
      assert.equal((await inspect()).review.evidence.status, 'missing_receipt');
      assert.match(await page.locator('#evidence-status').textContent(), /receipt is missing/);
      await load('evidence-request', evidenceRequest);
      await load('evidence-receipt', evidenceReceipt);
      mark('metadata edits invalidate prior review and missing evidence remains explicit');

      const missingBindings = JSON.parse(bindingRequest);
      missingBindings.bindings = [];
      await load('binding-request', JSON.stringify(missingBindings));
      assert.equal((await inspect()).review.bindings.assessment.outcome, 'fail');
      assert.match(await page.locator('#binding-diagnostics').textContent(), /missing_/);
      await load('binding-request', bindingRequest);
      const mismatchedBindings = JSON.parse(bindingRequest);
      mismatchedBindings.construction.mode = 'diagnostic';
      await load('binding-request', JSON.stringify(mismatchedBindings));
      await page.locator('#inspect').click();
      await page.locator('#error').waitFor({ state: 'visible' });
      assert.match(await page.locator('#error').textContent(), /independent complete authority/);
      assert.equal(await page.locator('#save').isDisabled(), true);
      await load('binding-request', bindingRequest);
      await inspect();
      mark('missing bindings fail nominal checks and disagreeing construction authority is rejected');

      // Any auxiliary record edit must invalidate a save already in flight.
      let releaseReviewSave, enteredReviewSave;
      const saveEntered = new Promise(resolve => { enteredReviewSave = resolve; });
      const saveGate = new Promise(resolve => { releaseReviewSave = resolve; });
      const lateDownloads = [];
      const onLateDownload = download => lateDownloads.push(download.suggestedFilename());
      page.on('download', onLateDownload);
      await page.route('**/api/construction/save', async route => {
        const response = await route.fetch(); enteredReviewSave(); await saveGate;
        await route.fulfill({response}).catch(() => {});
      });
      await page.locator('#save').click(); await saveEntered;
      await page.locator('#source-inventory-json').press('ControlOrMeta+End');
      await page.locator('#source-inventory-json').press('Enter');
      releaseReviewSave(); await page.unrouteAll({behavior: 'wait'});
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.equal(await page.locator('#result').isVisible(), false);
      assert.equal(await page.locator('#save').isDisabled(), true);
      assert.deepEqual(lateDownloads, []);
      page.off('download', onLateDownload);
      await load('source-inventory', sourceInventory);
      await inspect();
      mark('review authority edits reject late save results');
    }

    for (const width of [1440, 1024, 768, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      const layout = await page.evaluate(() => ({ width: innerWidth, bodyWidth: document.documentElement.scrollWidth,
        clippedControls: [...document.querySelectorAll('button,input,textarea')].filter(e => e.getClientRects().length).filter(e => { const r = e.getBoundingClientRect(); return r.left < -1 || r.right > innerWidth + 1; }).map(e => e.id) }));
      assert(layout.bodyWidth <= width + 1, JSON.stringify(layout));
      assert.deepEqual(layout.clippedControls, []);
      if (suite === 'review') {
        const tables = await page.locator('.review-section .table-scroll').evaluateAll(regions => regions.map(region => ({
          label: region.getAttribute('aria-label'),
          width: region.clientWidth,
          scrollWidth: region.scrollWidth,
          tableWidth: region.querySelector('table').getBoundingClientRect().width,
          left: region.getBoundingClientRect().left,
          right: region.getBoundingClientRect().right,
          cellWidths: [...region.querySelectorAll('tbody tr:first-child td')].map(cell => cell.getBoundingClientRect().width),
        })));
        for (const table of tables) {
          assert(table.left >= -1 && table.right <= width + 1, JSON.stringify(table));
          if (table.cellWidths.length > 2) {
            assert(table.tableWidth >= 639, JSON.stringify(table));
            assert(table.cellWidths.every(cellWidth => cellWidth >= 159), JSON.stringify(table));
          }
          if (width === 1440) assert(table.scrollWidth <= table.width + 1, JSON.stringify(table));
          if (width === 320 && table.cellWidths.length > 2) assert(table.scrollWidth > table.width, JSON.stringify(table));
          if (width === 320 && table.cellWidths.length === 2) assert(table.scrollWidth <= table.width + 1, JSON.stringify(table));
        }
        layout.reviewTables = tables;
        if (width === 320) {
          const region = page.getByRole('region', {name: 'Source gap table', exact: true});
          assert.equal(await page.locator('#review-table-help').isVisible(), true);
          assert.equal(await region.getAttribute('aria-describedby'), 'review-table-help');
          await region.press('ArrowRight');
          await page.waitForFunction(() => document.querySelector('#source-review .table-scroll').scrollLeft > 0);
          const position = await region.evaluate(element => ({focused: document.activeElement === element, left: element.scrollLeft}));
          assert.equal(position.focused, true);
          assert(position.left > 0, JSON.stringify(position));
          layout.keyboardScroll = position;
          await region.press('ArrowLeft');
          await page.waitForFunction(() => document.querySelector('#source-review .table-scroll').scrollLeft === 0);
          mark('mobile review tables retain readable columns and keyboard horizontal scrolling');
        }
      }
      evidence.layout.push(layout);
      if ([1440, 320].includes(width)) await page.screenshot({ path: path.join(output, artifactPrefix + '-' + width + '.png'), fullPage: true });
    }
    // Verify the shared muted token against the surfaces identified by the design hook.
    evidence.contrast = await page.evaluate(() => {
      const tokens = getComputedStyle(document.documentElement);
      const luminance = value => { const rgb = value.trim().slice(1).match(/../g).map(h => parseInt(h, 16) / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4); return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722; };
      const foreground = luminance(tokens.getPropertyValue('--muted'));
      return ['--ground', '--paper', '--pale'].map(name => ({ surface: name, ratio: (luminance(tokens.getPropertyValue(name)) + .05) / (foreground + .05) }));
    });
    for (const pair of evidence.contrast) assert(pair.ratio >= 4.5, JSON.stringify(pair));
    assert.deepEqual(errors, []);
    evidence.runtimeErrors = errors;
    await fs.writeFile(path.join(output, artifactPrefix + '-browser-evidence.json'), JSON.stringify(evidence, null, 2) + '\n');
    console.log(JSON.stringify(evidence, null, 2));
  } catch (error) {
    if (page) await page.screenshot({ path: path.join(output, artifactPrefix + '-failure.png'), fullPage: true }).catch(() => {});
    throw error;
  } finally {
    clearTimeout(deadline);
    if (browser) await browser.close();
    server.kill('SIGTERM');
    await fs.writeFile(path.join(output, artifactPrefix + '-server.log'), log);
    await fs.rm(outside, { recursive: true, force: true });
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
