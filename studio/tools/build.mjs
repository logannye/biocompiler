/** Deterministic release assets; --check never repairs stale checked-in output. */
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync } from 'node:fs';
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const destination = path.resolve(root, '../src/biocompiler/studio/static');
const checking = process.argv.includes('--check');
if (process.argv.slice(2).some(value => value !== '--check')) throw new Error('Usage: build.mjs [--check]');
const config = JSON.parse(await readFile(path.join(root, 'package.json'), 'utf8'));
const installed = path.join(root, 'node_modules/typescript/bin/tsc');
const command = existsSync(installed) ? process.execPath : 'tsc';
const prefix = existsSync(installed) ? [installed] : [];
const compilerVersion = execFileSync(command, [...prefix, '--version'], { encoding: 'utf8' }).trim();
if (compilerVersion !== `Version ${config.devDependencies.typescript}`) {
  throw new Error(`Build requires TypeScript ${config.devDependencies.typescript}; found ${compilerVersion}.`);
}
const scratch = await mkdtemp(path.join(tmpdir(), 'biocompiler-studio-assets-'));
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
try {
  execFileSync(command, [...prefix, '--project', path.join(root, 'tsconfig.json'), '--outDir', scratch], { stdio: 'inherit' });
  const assets = (await readdir(scratch)).sort();
  if (assets.join(',') !== 'app.js,construction.js,transport.js') throw new Error('Unexpected emitted Studio asset inventory.');
  const sources = ['package.json', 'package-lock.json', 'tsconfig.json', 'tools/build.mjs',
    ...(await readdir(path.join(root, 'src'))).filter(name => name.endsWith('.ts')).map(name => `src/${name}`)].sort();
  const inputs = {};
  for (const name of sources) inputs[name] = sha256(await readFile(path.join(root, name)));
  const generated = new Map();
  for (const name of assets) {
    const content = await readFile(path.join(scratch, name), 'utf8');
    generated.set(name, Buffer.from('// Generated from studio/src; run npm --prefix studio run build. Do not edit.\n' + content));
  }
  const manifest = {
    schema_version: 'biocompiler.studio_assets.v0.1', typescript: config.devDependencies.typescript,
    inputs, assets: Object.fromEntries([...generated].map(([name, bytes]) => [name, sha256(bytes)])),
  };
  generated.set('studio-assets.json', Buffer.from(JSON.stringify(manifest, null, 2) + '\n'));
  const stale = [];
  for (const [name, bytes] of generated) {
    const target = path.join(destination, name);
    if (checking) {
      const current = await readFile(target).catch(error => {
        if (error.code === 'ENOENT') return null;
        throw error;
      });
      if (!current?.equals(bytes)) stale.push(name);
    } else await writeFile(target, bytes);
  }
  if (stale.length) throw new Error(`Studio release assets are stale: ${stale.join(', ')}. Run npm --prefix studio run build and review the source/output changes.`);
  console.log(`${checking ? 'Verified' : 'Wrote'} ${generated.size} deterministic Studio release files with ${compilerVersion}.`);
} finally {
  await rm(scratch, { recursive: true, force: true });
}
