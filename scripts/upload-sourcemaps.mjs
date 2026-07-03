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

import { readdir, readFile, writeFile } from 'node:fs/promises';
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
  console.warn('NEW_RELIC_API_KEY is not set. Skipping source map upload.');
  process.exit(0);
}

// Minimal Base64-VLQ codec needed to remap source indices after deduplication.
const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
const B64_IDX = Object.fromEntries([...B64].map((c, i) => [c, i]));

function vlqDecode(str) {
  const out = [];
  let i = 0;
  while (i < str.length) {
    let value = 0,
      shift = 0,
      cont;
    do {
      const d = B64_IDX[str[i++]];
      cont = d & 32;
      value |= (d & 31) << shift;
      shift += 5;
    } while (cont);
    out.push(value & 1 ? -(value >>> 1) : value >>> 1);
  }
  return out;
}

function vlqEncode(values) {
  return values
    .map((v) => {
      let n = v < 0 ? (-v << 1) | 1 : v << 1;
      let s = '';
      do {
        let d = n & 31;
        n >>>= 5;
        if (n > 0) d |= 32;
        s += B64[d];
      } while (n > 0);
      return s;
    })
    .join('');
}

// Rollup can emit source maps where the same source path appears more than once
// in the `sources` array. New Relic rejects these with 400. This function
// deduplicates `sources` and remaps the VLQ `mappings` field accordingly.
// Returns the fixed source map object, or null if no duplicates were found.
function deduplicateSourcemap(data) {
  const { sources, sourcesContent, mappings } = data;
  if (!sources || !mappings) return null;

  const seen = new Map();
  const reindex = [];
  const newSources = [];
  const newContent = sourcesContent ? [] : null;

  for (let i = 0; i < sources.length; i++) {
    const s = sources[i];
    if (seen.has(s)) {
      reindex.push(seen.get(s));
    } else {
      seen.set(s, newSources.length);
      reindex.push(newSources.length);
      newSources.push(s);
      if (newContent) newContent.push(sourcesContent[i]);
    }
  }

  if (newSources.length === sources.length) return null;

  // Source index is accumulated across all segments (not reset per line), so
  // we track old and new absolute positions outside the line loop.
  let prevOld = 0;
  let prevNew = 0;
  const newMappings = mappings
    .split(';')
    .map((line) =>
      line
        .split(',')
        .map((seg) => {
          if (!seg) return seg;
          const vals = vlqDecode(seg);
          if (vals.length >= 2) {
            const absOld = prevOld + vals[1];
            const absNew = reindex[absOld] ?? absOld;
            vals[1] = absNew - prevNew;
            prevOld = absOld;
            prevNew = absNew;
          }
          return vlqEncode(vals);
        })
        .join(',')
    )
    .join(';');

  return {
    ...data,
    sources: newSources,
    mappings: newMappings,
    ...(newContent && { sourcesContent: newContent })
  };
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
let failed = 0;

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

  // Deduplicate sources in place before uploading. Rollup can emit the same
  // source path more than once in a chunk's source map, which New Relic rejects.
  const raw = await readFile(sourcemapPath, 'utf8');
  const data = JSON.parse(raw);
  const fixed = deduplicateSourcemap(data);
  if (fixed) {
    console.log(
      `Fixed duplicate sources in ${relPath} (${fixed.sources.length} unique of ${data.sources.length} total).`
    );
    await writeFile(sourcemapPath, JSON.stringify(fixed), 'utf8');
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
    // Sourcemap upload is best-effort observability tooling, not a build
    // requirement — log a concise reason and move on instead of failing
    // the whole build over a New Relic-side issue (e.g. permissions).
    failed += 1;
    const nrMessage = error?.response?.body?.message ?? error?.response?.text;
    const reason = nrMessage
      ? `New Relic rejected ${relPath} (${error?.status}): ${nrMessage}`
      : `Failed to upload ${relPath}: ${error?.message ?? String(error)}`;
    console.error(`::warning::${reason}`);
    continue;
  }

  uploaded += 1;
  console.log(`Uploaded ${relPath} -> ${javascriptUrl}`);
}

console.log(
  `Done. Uploaded ${uploaded} source map(s)` +
    (skipped > 0 ? `, skipped ${skipped} already present` : '') +
    (failed > 0 ? `, failed to upload ${failed}` : '') +
    ` for New Relic app ${APPLICATION_ID}.`
);

if (failed > 0) {
  console.warn(
    `::warning::${failed} source map(s) failed to upload to New Relic — affected stack traces won't be symbolicated, but the build is not blocked.`
  );
}
