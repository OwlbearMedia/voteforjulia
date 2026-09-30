import { readdirSync, readFileSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import type { Component } from 'vue';
import JuliaVideo from '../../src/components/JuliaVideo.vue';

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

const BOUND_SRC = /\s(?::|v-bind:)src=/;

/** Every `<iframe …>` tag in the site source, opening tag only. */
function iframeTags(): { path: string; tag: string }[] {
  return SOURCES.flatMap(({ path, source }) =>
    [...source.matchAll(/<iframe\b[^>]*>/g)].map((match) => ({ path, tag: match[0] }))
  );
}

/**
 * Every component whose `<iframe>` binds its `src`, with the props to render it.
 * A bound source is resolved by rendering, so the props must include inputs that
 * try to move the frame to another origin, not only the ones the pages pass.
 */
const BOUND_FRAMES: Record<string, { component: Component; props: Record<string, unknown>[] }> = {
  'src/components/JuliaVideo.vue': {
    component: JuliaVideo,
    props: [
      'bc4dvZpAa-A',
      '//evil.example/x',
      'https://evil.example/x',
      '@evil.example',
      '../../../../evil.example'
    ].map((videoId) => ({ videoId, title: 'Probe' }))
  }
};

function frameSrcAllowlist(): string[] {
  // The header is one line-continued string, so the directive runs to its `;`.
  const match = HTACCESS.match(/frame-src ([^;]+);/);
  if (!match) throw new Error('public/.htaccess declares no frame-src directive');
  return match[1].trim().split(/\s+/);
}

describe('iframe origins are covered by the CSP', () => {
  it('finds the embeds it claims to check', () => {
    // Without this the whole file passes vacuously if the scan ever breaks.
    expect(iframeTags().length).toBeGreaterThanOrEqual(1);
  });

  it('allows every embedded origin in frame-src', () => {
    const allowed = frameSrcAllowlist();

    const origins = iframeTags()
      .filter(({ tag }) => !BOUND_SRC.test(tag))
      .map(({ path, tag }) => {
        const src = tag.match(/\ssrc="([^"]+)"/);
        if (!src) throw new Error(`${path}: <iframe> has no static src`);
        return { path, origin: new URL(src[1]).origin };
      });

    for (const { path, origin } of origins) {
      expect(allowed, `${path} embeds ${origin}, which frame-src does not allow`).toContain(origin);
    }
  });

  it('registers every iframe whose src is bound, and nothing else', () => {
    // A `:src` or `v-bind:src` resolves at runtime, so the static check above
    // cannot see where it points; an unregistered one is unchecked, not exempt.
    const bound = iframeTags()
      .filter(({ tag }) => BOUND_SRC.test(tag))
      .map(({ path }) => relative(ROOT, path));
    expect(bound.sort()).toEqual(Object.keys(BOUND_FRAMES).sort());
  });

  it.each(Object.entries(BOUND_FRAMES))(
    'allows every origin %s renders',
    (path, { component, props }) => {
      const allowed = frameSrcAllowlist();

      for (const probe of props) {
        const src = mount(component, { props: probe }).find('iframe').attributes('src');
        if (!src) throw new Error(`${path} rendered no <iframe> src for ${JSON.stringify(probe)}`);
        expect(allowed, `${path} with ${JSON.stringify(probe)} embeds ${src}`).toContain(
          new URL(src).origin
        );
      }
    }
  );
});
