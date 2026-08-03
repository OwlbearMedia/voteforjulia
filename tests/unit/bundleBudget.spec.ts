import { describe, expect, it } from 'vitest';
import { gzipSync } from 'node:zlib';
// @ts-expect-error -- plain .mjs helper with no type declarations; see scripts/bundleBudget.mjs
import {
  evaluateBudgets,
  extractInitialAssets,
  formatSummary,
  gzipBytes,
  hasFailure,
  measureRoute
} from '../../scripts/bundleBudget.mjs';

/** Minimal stand-in for what vite-ssg emits: entry module + preloaded chunks. */
function documentWith(tags: string) {
  return `<!doctype html><html><head><style>.a{color:red}</style>${tags}</head><body></body></html>`;
}

const ENTRY = '<script type="module" crossorigin src="/assets/index-abc.js"></script>';
const PRELOAD = '<link rel="modulepreload" crossorigin href="/assets/vendor-def.js">';

describe('extractInitialAssets', () => {
  it('collects the entry module and every preloaded chunk', () => {
    const { local } = extractInitialAssets(documentWith(ENTRY + PRELOAD));
    expect(local).toEqual(['assets/index-abc.js', 'assets/vendor-def.js']);
  });

  it('strips the leading slash so paths resolve against dist/', () => {
    const { local } = extractInitialAssets(documentWith(ENTRY));
    expect(local[0].startsWith('/')).toBe(false);
  });

  it('does not double-count a chunk that is both preloaded and the entry', () => {
    const duplicate = '<link rel="modulepreload" href="/assets/index-abc.js">';
    const { local } = extractInitialAssets(documentWith(ENTRY + duplicate));
    expect(local).toEqual(['assets/index-abc.js']);
  });

  it('separates third-party scripts from files we build', () => {
    // /donate loads the Donorbox widget from their origin — real first-load
    // cost, but not a file in dist/, so it must not be looked up there.
    const donorbox = '<script type="module" src="https://donorbox.org/widgets.js"></script>';
    const { local, external } = extractInitialAssets(documentWith(ENTRY + donorbox));
    expect(local).toEqual(['assets/index-abc.js']);
    expect(external).toEqual(['https://donorbox.org/widgets.js']);
  });

  it('treats protocol-relative URLs as third-party', () => {
    const cdn = '<script type="module" src="//cdn.example.com/x.js"></script>';
    const { local, external } = extractInitialAssets(documentWith(cdn));
    expect(local).toEqual([]);
    expect(external).toEqual(['//cdn.example.com/x.js']);
  });

  it('ignores stylesheets, whose bytes are already inlined in the document', () => {
    const sheet = '<link rel="stylesheet" href="/assets/index-abc.css">';
    const { local, external } = extractInitialAssets(documentWith(sheet));
    expect(local).toEqual([]);
    expect(external).toEqual([]);
  });
});

describe('gzipBytes', () => {
  it('measures compressed size, not raw length', () => {
    const repetitive = 'a'.repeat(10_000);
    expect(gzipBytes(repetitive)).toBeLessThan(repetitive.length);
    expect(gzipBytes(repetitive)).toBe(gzipSync(repetitive, { level: 6 }).length);
  });
});

describe('measureRoute', () => {
  const assets: Record<string, string> = {
    'assets/index-abc.js': 'console.log("entry");'.repeat(50),
    'assets/vendor-def.js': 'console.log("vendor");'.repeat(50)
  };
  const readAsset = async (path: string) => assets[path] ?? null;

  it('sums the document and its initial JS', async () => {
    const html = documentWith(ENTRY + PRELOAD);
    const route = await measureRoute('index.html', html, readAsset);

    expect(route.documentBytes).toBe(gzipBytes(html));
    expect(route.javascriptBytes).toBe(
      gzipBytes(assets['assets/index-abc.js']) + gzipBytes(assets['assets/vendor-def.js'])
    );
    expect(route.firstLoadBytes).toBe(route.documentBytes + route.javascriptBytes);
    expect(route.missing).toEqual([]);
  });

  it('excludes third-party scripts from the measured weight', async () => {
    const donorbox = '<script type="module" src="https://donorbox.org/widgets.js"></script>';
    const withThirdParty = await measureRoute('donate.html', documentWith(ENTRY + donorbox), readAsset);
    const without = await measureRoute('donate.html', documentWith(ENTRY), readAsset);

    expect(withThirdParty.javascriptBytes).toBe(without.javascriptBytes);
    expect(withThirdParty.external).toEqual(['https://donorbox.org/widgets.js']);
    expect(withThirdParty.missing).toEqual([]);
  });

  it('reports a referenced chunk that is not in dist rather than throwing', async () => {
    const ghost = '<link rel="modulepreload" href="/assets/gone-000.js">';
    const route = await measureRoute('index.html', documentWith(ENTRY + ghost), readAsset);
    expect(route.missing).toEqual(['assets/gone-000.js']);
  });
});

describe('evaluateBudgets', () => {
  const route = (name: string, firstLoadBytes: number) => ({
    name,
    documentBytes: 1024,
    javascriptBytes: firstLoadBytes - 1024,
    firstLoadBytes,
    external: [],
    missing: []
  });

  it('passes a route under its budget', () => {
    const results = evaluateBudgets([route('index.html', 40 * 1024)], {
      routes: { 'index.html': 50 }
    });
    expect(results).toHaveLength(1);
    expect(results[0].status).toBe('ok');
    expect(hasFailure(results)).toBe(false);
  });

  it('fails a route over its budget', () => {
    const results = evaluateBudgets([route('index.html', 60 * 1024)], {
      routes: { 'index.html': 50 }
    });
    expect(results[0].status).toBe('over');
    expect(hasFailure(results)).toBe(true);
  });

  it('treats exactly-at-budget as passing', () => {
    const results = evaluateBudgets([route('index.html', 50 * 1024)], {
      routes: { 'index.html': 50 }
    });
    expect(results[0].status).toBe('ok');
  });

  // The regression this exists to prevent: adding a page must not silently
  // opt that page out of the budget by simply having no entry.
  it('fails a route with no budget entry instead of skipping it', () => {
    const results = evaluateBudgets([route('new-page.html', 10 * 1024)], { routes: {} });
    expect(results[0].status).toBe('missing-budget');
    expect(hasFailure(results)).toBe(true);
  });

  it('fails a budget for a route that no longer exists', () => {
    const results = evaluateBudgets([route('index.html', 10 * 1024)], {
      routes: { 'index.html': 50, 'deleted.html': 50 }
    });
    expect(results.find((r) => r.name === 'deleted.html')?.status).toBe('stale-budget');
    expect(hasFailure(results)).toBe(true);
  });

  it('reports a missing asset ahead of the size comparison', () => {
    const broken = { ...route('index.html', 10 * 1024), missing: ['assets/gone.js'] };
    const results = evaluateBudgets([broken], { routes: { 'index.html': 50 } });
    expect(results[0].status).toBe('missing-asset');
    expect(hasFailure(results)).toBe(true);
  });
});

describe('formatSummary', () => {
  const routes = [
    {
      name: 'donate.html',
      documentBytes: 10 * 1024,
      javascriptBytes: 60 * 1024,
      firstLoadBytes: 70 * 1024,
      external: ['https://donorbox.org/widgets.js'],
      missing: []
    }
  ];

  it('renders a markdown table row per result', () => {
    const results = evaluateBudgets(routes, { routes: { 'donate.html': 78 } });
    const summary = formatSummary(routes, results);
    expect(summary).toContain('| donate.html |');
    expect(summary).toContain('70.0 KiB');
    expect(summary).toContain('78.0 KiB');
  });

  it('lists third-party scripts so their cost stays visible', () => {
    const results = evaluateBudgets(routes, { routes: { 'donate.html': 78 } });
    expect(formatSummary(routes, results)).toContain('https://donorbox.org/widgets.js');
  });

  it('omits the third-party section when there is nothing to list', () => {
    const plain = [{ ...routes[0], external: [] }];
    const results = evaluateBudgets(plain, { routes: { 'donate.html': 78 } });
    expect(formatSummary(plain, results)).not.toContain('Third-party');
  });
});
