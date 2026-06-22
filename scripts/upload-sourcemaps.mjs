#!/usr/bin/env node
// Uploads hidden source maps produced by `vite-ssg build` to New Relic so that
// minified browser stack traces are symbolicated. Maps are NOT served publicly.
//
// Required env vars:
//   NEW_RELIC_API_KEY  - a New Relic User key (starts with "NRAK-")
//
// Optional env vars:
//   NEW_RELIC_APP_ID   - browser application ID (defaults to the prod app)
//   PUBLIC_BASE_URL    - public origin the JS is served from
//   DIST_DIR           - build output directory (defaults to ./dist)
//
// Usage: node scripts/upload-sourcemaps.mjs

import { readdir, readFile } from 'node:fs/promises';
import { join, relative, resolve } from 'node:path';

import { publishSourcemap } from '@newrelic/publish-sourcemap';

const API_KEY = process.env.NEW_RELIC_API_KEY;
const APPLICATION_ID = Number(process.env.NEW_RELIC_APP_ID ?? '653419329');
const PUBLIC_BASE_URL = (process.env.PUBLIC_BASE_URL ?? 'https://voteforjulia.com').replace(
  /\/$/,
  ''
);
const DIST_DIR = resolve(process.cwd(), process.env.DIST_DIR ?? 'dist');

if (!API_KEY) {
  console.error('Error: NEW_RELIC_API_KEY is not set. Skipping source map upload.');
  process.exit(1);
}

async function findSourceMaps(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const maps = [];

  for (const entry of entries) {
    const fullPath = join(dir, entry.name);

    if (entry.isDirectory()) {
      maps.push(...(await findSourceMaps(fullPath)));
    } else if (entry.isFile() && entry.name.endsWith('.js.map')) {
      maps.push(fullPath);
    }
  }

  return maps;
}

function publish(options) {
  return new Promise((resolvePromise, reject) => {
    publishSourcemap(options, (err) => (err ? reject(err) : resolvePromise()));
  });
}

const sourcemapPaths = await findSourceMaps(DIST_DIR);

if (sourcemapPaths.length === 0) {
  console.warn(`No .js.map files found in ${DIST_DIR}. Did you run the build first?`);
  process.exit(0);
}

let uploaded = 0;
let skipped = 0;

for (const sourcemapPath of sourcemapPaths) {
  // Map dist/assets/foo.js.map -> https://base/assets/foo.js
  const relPath = relative(DIST_DIR, sourcemapPath).split(/[\\/]/).join('/');
  const javascriptUrl = `${PUBLIC_BASE_URL}/${relPath.replace(/\.map$/, '')}`;

  // Skip maps whose JS bundle is missing (e.g. inlined SSG entry maps).
  const javascriptPath = sourcemapPath.replace(/\.map$/, '');
  try {
    await readFile(javascriptPath);
  } catch {
    console.warn(`Skipping ${relPath}: no matching JS file.`);
    continue;
  }

  try {
    await publish({
      sourcemapPath,
      javascriptUrl,
      applicationId: APPLICATION_ID,
      apiKey: API_KEY
    });
  } catch (error) {
    // New Relic returns 409 Conflict when a source map already exists for this
    // javascriptUrl. Because Vite emits content-hashed filenames, an existing
    // map for the same URL is identical content, so this is safe to ignore and
    // keeps re-runs (e.g. a re-triggered deploy for the same commit) idempotent.
    if (error?.status === 409) {
      skipped += 1;
      console.warn(`Skipping ${relPath}: source map already exists in New Relic (409 Conflict).`);
      continue;
    }
    throw error;
  }

  uploaded += 1;
  console.log(`Uploaded ${relPath} -> ${javascriptUrl}`);
}

console.log(
  `Done. Uploaded ${uploaded} source map(s)` +
    (skipped > 0 ? `, skipped ${skipped} already present` : '') +
    ` for New Relic app ${APPLICATION_ID}.`
);
