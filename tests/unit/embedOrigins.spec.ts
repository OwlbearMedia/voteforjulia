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

/** Opening `<iframe …>` tags, read past any `>` inside a quoted value. */
function openingTags(source: string): string[] {
  return [...source.matchAll(/<iframe\b(?:[^>"']|"[^"]*"|'[^']*')*>/gi)].map((match) => match[0]);
}

/** Every `<iframe …>` tag in the site source, opening tag only. */
function iframeTags(): { path: string; tag: string }[] {
  return SOURCES.flatMap(({ path, source }) =>
    openingTags(source).map((tag) => ({ path: relative(ROOT, path), tag }))
  );
}

/**
 * The `src` a tag carries as a literal, or undefined when anything may bind it:
 * a binding wins over a literal at runtime, so a tag with both is not static,
 * and a dynamic argument (`:[name]`) may name `src`. Case-insensitive, because
 * `:SRC` sets the same attribute on a native element.
 */
function staticSrc(tag: string): string | undefined {
  if (/\s(?::|v-bind:|\.)(?:src(?![\w-])|\[)|\sv-bind=/i.test(tag)) return undefined;
  return tag.match(/\ssrc="([^"]+)"/i)?.[1];
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
    ['<iframe src="a">', '<iframe src="a">'],
    ['<iframe src="a" :title="n > 1" :src="b">', '<iframe src="a" :title="n > 1" :src="b">'],
    ['<iframe src="a" :title=\'n > 1\' :src="b">', '<iframe src="a" :title=\'n > 1\' :src="b">'],
    ['<IFRAME src="a">', '<IFRAME src="a">'],
    ['<iframes src="a">', undefined]
  ])('scans %j as the tag %j', (source, expected) => {
    expect(openingTags(`<p>${source}</p>`)).toEqual(expected ? [expected] : []);
  });

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
    ['<iframe src="https://a.example" .src="x">', undefined],
    ['<iframe src="https://a.example" :[name]="x">', undefined],
    ['<iframe src="https://a.example" v-bind:[name]="x">', undefined],
    ['<iframe src="https://a.example" @[event]="x">', 'https://a.example'],
    ['<iframe src="https://a.example" :class="x">', 'https://a.example'],
    ['<iframe SRC="https://a.example">', 'https://a.example'],
    ['<iframe src="https://a.example" :SRC="x">', undefined],
    ['<iframe src="https://a.example" :Src="x">', undefined],
    ['<iframe src="https://a.example" V-BIND:src="x">', undefined],
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
        const srcs = wrapper.findAll('iframe').map((frame) => frame.attributes('src'));
        wrapper.unmount();
        if (srcs.length === 0 || srcs.includes(undefined)) {
          throw new Error(
            `${path} rendered an <iframe> without a src for ${JSON.stringify(probe)}`
          );
        }
        for (const src of srcs as string[]) {
          expect(allowed, `${path} with ${JSON.stringify(probe)} embeds ${src}`).toContain(
            new URL(src).origin
          );
        }
      }
    }
  );
});
