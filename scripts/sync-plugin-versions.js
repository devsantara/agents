// Changesets versions each plugin through its package.json, but Claude Code
// reads the version from .claude-plugin/plugin.json. Copy it across after
// `changeset version` so the two never drift.
//
//   node scripts/sync-plugin-versions.js          write plugin.json versions
//   node scripts/sync-plugin-versions.js --check  fail if any are out of sync

import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const check = process.argv.includes('--check');
const pluginsDir = join(import.meta.dirname, '..', 'plugins');
const readJson = (path) => JSON.parse(readFileSync(path, 'utf8'));

let failed = false;

for (const entry of readdirSync(pluginsDir, { withFileTypes: true })) {
  if (!entry.isDirectory()) continue;

  const packagePath = join(pluginsDir, entry.name, 'package.json');
  const manifestPath = join(pluginsDir, entry.name, '.claude-plugin', 'plugin.json');

  if (!existsSync(packagePath) || !existsSync(manifestPath)) {
    console.error(`${entry.name}: needs both package.json and .claude-plugin/plugin.json`);
    failed = true;
    continue;
  }

  const pkg = readJson(packagePath);
  const manifest = readJson(manifestPath);

  if (pkg.name !== manifest.name) {
    console.error(`${entry.name}: package.json name "${pkg.name}" must match plugin.json name "${manifest.name}"`);
    failed = true;
    continue;
  }

  if (manifest.version === pkg.version) continue;

  if (check) {
    console.error(`${entry.name}: plugin.json is ${manifest.version}, package.json is ${pkg.version}`);
    failed = true;
    continue;
  }

  writeFileSync(manifestPath, `${JSON.stringify({ ...manifest, version: pkg.version }, null, 2)}\n`);
  console.log(`${entry.name}: ${manifest.version} -> ${pkg.version}`);
}

if (failed) process.exit(1);
