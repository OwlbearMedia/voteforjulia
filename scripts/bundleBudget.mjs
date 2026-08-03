/**
 * Measures what a visitor actually downloads for a cold visit to each
 * prerendered route, and checks it against the budgets in perf-budgets.json.
 *
 * Everything here is pure and filesystem-free except `measureDist`, so the
 * interesting logic is unit-tested in tests/unit/bundleBudget.spec.ts.
 */

import { gzipSync } from 'node:zlib';
import { readdir, readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

/** Bytes per KiB. Budgets are written in KiB because that is how they get discussed. */
const KIB = 1024;

/**
 * Gzipped size in bytes. LiteSpeed compresses text responses on the wire
 * (public/.htaccess), so the raw byte count on disk is not what crosses the
 * network — comparing uncompressed sizes would make the budgets fiction.
 * Level 6 is the zlib default and close enough to what the host emits; the
 * absolute number matters less than it being computed the same way every run.
 */
export function gzipBytes(contents) {
  return gzipSync(contents, { level: 6 }).length;
}

/**
 * Scripts a document pulls in before it can hydrate: the entry module plus
 * every chunk Vite preloads alongside it, split into what we build and what we
 * don't.
 *
 * These two tags are the whole initial JS payload by construction — Vite emits
 * a <link rel="modulepreload"> for each statically-imported chunk of the entry,
 * and route chunks it does not preload are fetched later, on navigation. So
 * this measures first load, not the size of dist/.
 *
 * `external` exists because /donate loads Donorbox's widget from their origin
 * (docs/donate-integration.md). It is real first-load cost, but it is not a
 * file in dist/ and its size is theirs to change, so it is listed in the report
 * and left out of the budgeted total rather than counted as a missing asset.
 *
 * Stylesheets are deliberately not collected: vite.config.ts's onFinished hook
 * inlines all CSS into the document, so its cost is already inside the HTML
 * byte count and counting it again would double-charge it.
 */
export function extractInitialAssets(html) {
  const references = new Set();

  const scripts = html.matchAll(/<script[^>]+type="module"[^>]+src="([^"]+)"/g);
  for (const [, src] of scripts) references.add(src);

  const preloads = html.matchAll(/<link[^>]+rel="modulepreload"[^>]+href="([^"]+)"/g);
  for (const [, href] of preloads) references.add(href);

  const local = [];
  const external = [];
  for (const reference of references) {
    // Anything with a scheme, or protocol-relative, is served by someone else.
    if (/^(?:[a-z][a-z0-9+.-]*:)?\/\//i.test(reference)) {
      external.push(reference);
      continue;
    }
    // Emitted paths are root-absolute ("/assets/x.js"); callers resolve them
    // against dist/, so strip the leading slash here rather than in each caller.
    local.push(reference.replace(/^\//, ''));
  }

  return { local, external };
}

/**
 * First-load weight of one route: the document (CSS already inlined into it)
 * plus the JS the browser fetches before hydration, all gzipped.
 *
 * `readAsset` returns the bytes for a dist-relative path, or null when the path
 * is not in dist — a preload pointing at a missing file is a build bug, but it
 * should surface as a reported miss rather than as a crash mid-measurement.
 */
export async function measureRoute(name, html, readAsset) {
  const documentBytes = gzipBytes(html);
  const { local, external } = extractInitialAssets(html);

  let javascriptBytes = 0;
  const missing = [];
  for (const path of local) {
    const contents = await readAsset(path);
    if (contents === null) {
      missing.push(path);
      continue;
    }
    javascriptBytes += gzipBytes(contents);
  }

  return {
    name,
    documentBytes,
    javascriptBytes,
    firstLoadBytes: documentBytes + javascriptBytes,
    external,
    missing
  };
}

/** Reads dist/ and measures every prerendered document in it. */
export async function measureDist(distDir) {
  const entries = await readdir(distDir);
  const documents = entries.filter((file) => file.endsWith('.html')).sort();

  const readAsset = async (path) => {
    try {
      return await readFile(resolve(distDir, path));
    } catch {
      return null;
    }
  };

  const routes = [];
  for (const file of documents) {
    const html = await readFile(resolve(distDir, file), 'utf8');
    routes.push(await measureRoute(file, html, readAsset));
  }

  return routes;
}

/**
 * Compares measurements to budgets and returns one row per check.
 *
 * A route with no budget entry is a `missing-budget` failure rather than a pass.
 * Silently ignoring it would mean adding a page quietly opts that page out of
 * the budget — the exact regression this is meant to catch. Adding a page is
 * already a checklist (docs/conventions.md#adding-a-page); this makes the
 * budget part of it non-optional.
 */
export function evaluateBudgets(routes, budgets) {
  const results = routes.map((route) => {
    const budgetKb = budgets.routes?.[route.name];
    const actualKb = route.firstLoadBytes / KIB;

    if (route.missing.length > 0) {
      return {
        name: route.name,
        actualKb,
        budgetKb: budgetKb ?? null,
        status: 'missing-asset',
        detail: `referenced but not found in dist: ${route.missing.join(', ')}`
      };
    }

    if (budgetKb === undefined) {
      return {
        name: route.name,
        actualKb,
        budgetKb: null,
        status: 'missing-budget',
        detail: 'no entry in perf-budgets.json'
      };
    }

    return {
      name: route.name,
      actualKb,
      budgetKb,
      status: actualKb > budgetKb ? 'over' : 'ok',
      detail: ''
    };
  });

  // A budget for a route that no longer exists is stale, not harmless: it reads
  // as coverage that isn't there. Surface it so the file gets pruned.
  const measured = new Set(routes.map((route) => route.name));
  for (const name of Object.keys(budgets.routes ?? {})) {
    if (measured.has(name)) continue;
    results.push({
      name,
      actualKb: null,
      budgetKb: budgets.routes[name],
      status: 'stale-budget',
      detail: 'budgeted route is not in dist'
    });
  }

  return results;
}

const STATUS_LABEL = {
  ok: '✅',
  over: '❌ over budget',
  'missing-budget': '❌ no budget',
  'missing-asset': '❌ missing asset',
  'stale-budget': '❌ stale budget'
};

/** GitHub-flavoured markdown for the CI job summary. */
export function formatSummary(routes, results) {
  const kb = (bytes) => (bytes / KIB).toFixed(1);
  const lines = [
    '### Bundle size — first load, gzipped',
    '',
    '| Route | Document | Initial JS | First load | Budget | |',
    '| --- | ---: | ---: | ---: | ---: | --- |'
  ];

  const byName = new Map(routes.map((route) => [route.name, route]));
  for (const result of results) {
    const route = byName.get(result.name);
    lines.push(
      [
        '',
        result.name,
        route ? `${kb(route.documentBytes)} KiB` : '—',
        route ? `${kb(route.javascriptBytes)} KiB` : '—',
        route ? `${kb(route.firstLoadBytes)} KiB` : '—',
        result.budgetKb === null ? '—' : `${result.budgetKb.toFixed(1)} KiB`,
        `${STATUS_LABEL[result.status]}${result.detail ? ` — ${result.detail}` : ''}`,
        ''
      ].join(' | ')
    );
  }

  lines.push('');
  lines.push(
    'Document size includes the inlined CSS. Initial JS is the entry module plus',
    'its preloaded chunks — route chunks fetched on later navigation are not counted.'
  );

  const external = routes.filter((route) => route.external.length > 0);
  if (external.length > 0) {
    lines.push('');
    lines.push('Third-party scripts in the initial load, not counted against the budget:');
    lines.push('');
    for (const route of external) {
      lines.push(`- \`${route.name}\` — ${route.external.map((url) => `\`${url}\``).join(', ')}`);
    }
  }

  return lines.join('\n');
}

export const hasFailure = (results) => results.some((result) => result.status !== 'ok');
