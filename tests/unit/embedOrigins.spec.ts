import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * An `<iframe>` whose origin is missing from the CSP is the one defect the rest
 * of the suite cannot see: the dev server sends no CSP, so the embed works on
 * every machine and is blocked in production only. See docs/conventions.md,
 * "Embedded iframes".
 */
// A path rather than a file URL: the suite runs under jsdom, where
// `import.meta.url` is not a `file:` URL and `readFileSync` rejects it.
const ROOT = process.cwd();
const HTACCESS = readFileSync(resolve(ROOT, 'public/.htaccess'), 'utf8');

function vueFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return vueFiles(path);
    return entry.name.endsWith('.vue') ? [path] : [];
  });
}

const SOURCES = vueFiles(resolve(ROOT, 'src')).map((path) => ({
  path,
  source: readFileSync(path, 'utf8')
}));

/** Every `<iframe …>` tag in the site source, opening tag only. */
function iframeTags(): { path: string; tag: string }[] {
  return SOURCES.flatMap(({ path, source }) =>
    [...source.matchAll(/<iframe\b[^>]*>/g)].map((match) => ({ path, tag: match[0] }))
  );
}

function frameSrcAllowlist(): string[] {
  // The header is one line-continued string, so the directive runs to its `;`.
  const match = HTACCESS.match(/frame-src ([^;]+);/);
  if (!match) throw new Error('public/.htaccess declares no frame-src directive');
  return match[1].trim().split(/\s+/);
}

describe('iframe origins are covered by the CSP', () => {
  it('finds the embeds it claims to check', () => {
    // Without this the whole file passes vacuously if the scan ever breaks.
    expect(iframeTags().length).toBeGreaterThanOrEqual(2);
  });

  it('allows every embedded origin in frame-src', () => {
    const allowed = frameSrcAllowlist();

    const origins = iframeTags().map(({ path, tag }) => {
      const src = tag.match(/\ssrc="([^"]+)"/);
      if (!src) throw new Error(`${path}: <iframe> has no static src`);
      return { path, origin: new URL(src[1]).origin };
    });

    for (const { path, origin } of origins) {
      expect(allowed, `${path} embeds ${origin}, which frame-src does not allow`).toContain(origin);
    }
  });

  it('has no iframe whose src is bound, since this check cannot follow one', () => {
    // A `:src` or `v-bind:src` resolves at runtime, so the assertion above would
    // skip it silently. Adding one means checking its origin by hand and saying
    // so here.
    const bound = iframeTags().filter(({ tag }) => /\s(?::|v-bind:)src=/.test(tag));
    expect(bound.map(({ path }) => path)).toEqual([]);
  });
});
