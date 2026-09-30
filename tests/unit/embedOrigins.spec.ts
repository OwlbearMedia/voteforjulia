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

/** Every `<iframe …>` tag in the site source, opening tag only. */
function iframeTags(): { path: string; tag: string }[] {
  return SOURCES.flatMap(({ path, source }) =>
    [...source.matchAll(/<iframe\b[^>]*>/gi)].map((match) => ({
      path: relative(ROOT, path),
      tag: match[0]
    }))
  );
}

/**
 * The `src` a tag carries as a literal, or undefined when anything binds it: a
 * binding wins over a literal at runtime, so a tag with both is not static.
 */
function staticSrc(tag: string): string | undefined {
  if (/\s(?::|v-bind:)src(?![\w-])|\sv-bind=/.test(tag)) return undefined;
  return tag.match(/\ssrc="([^"]+)"/)?.[1];
}

/**
 * Every component with an iframe `staticSrc` cannot read, and the props to
 * render it with. See docs/conventions.md, "Embedded iframes".
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
  it.each([
    ['<iframe src="https://a.example">', 'https://a.example'],
    ['<iframe\n  class="x"\n  src="https://a.example"\n>', 'https://a.example'],
    ['<iframe :srcdoc="x" src="https://a.example">', 'https://a.example'],
    ['<iframe :src="x">', undefined],
    ['<iframe\n  class="x"\n  :src="x"\n>', undefined],
    ['<iframe :src>', undefined],
    ['<iframe :src.attr="x">', undefined],
    ['<iframe v-bind:src="x">', undefined],
    ['<iframe v-bind="{ src }">', undefined],
    ['<iframe src="https://a.example" :src="x">', undefined],
    ['<iframe data-src="https://a.example">', undefined],
    ["<iframe src='https://a.example'>", undefined]
  ])('reads %j as static src %s', (tag, expected) => {
    expect(staticSrc(tag)).toBe(expected);
  });

  it('allows every static origin in frame-src', () => {
    const allowed = frameSrcAllowlist();

    for (const { path, tag } of iframeTags()) {
      const src = staticSrc(tag);
      if (src === undefined) continue;
      const origin = new URL(src).origin;
      expect(allowed, `${path} embeds ${origin}, which frame-src does not allow`).toContain(origin);
    }
  });

  it('registers every iframe without a static src, and nothing else', () => {
    // This is also the guard against a broken scan: it would find no frames.
    const unread = new Set(
      iframeTags()
        .filter(({ tag }) => staticSrc(tag) === undefined)
        .map(({ path }) => path)
    );
    expect(
      [...unread].sort(),
      'an iframe whose src is not a literal must be rendered, via BOUND_FRAMES'
    ).toEqual(Object.keys(BOUND_FRAMES).sort());
  });

  it.each(Object.entries(BOUND_FRAMES))(
    'allows every origin %s renders',
    (path, { component, props }) => {
      const allowed = frameSrcAllowlist();

      for (const probe of props) {
        const wrapper = mount(component, { props: probe });
        const src = wrapper.find('iframe').attributes('src');
        wrapper.unmount();
        if (!src) throw new Error(`${path} rendered no <iframe> src for ${JSON.stringify(probe)}`);
        expect(allowed, `${path} with ${JSON.stringify(probe)} embeds ${src}`).toContain(
          new URL(src).origin
        );
      }
    }
  );
});
