import 'vite-ssg';
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { buildSitemapXml, resolveSitemapRoutes } from './sitemap.build';

// Source map mode. Defaults to 'hidden': maps are generated without a
// sourceMappingURL comment (prod uploads them to New Relic, then strips them).
// Set SOURCEMAP_MODE=true for the test deploy to emit linked maps that browser
// devtools load automatically.
function resolveSourcemapMode(): 'hidden' | boolean {
  switch (process.env.SOURCEMAP_MODE) {
    case 'true':
      return true;
    case 'false':
      return false;
    default:
      return 'hidden';
  }
}

const SOURCEMAP_MODE = resolveSourcemapMode();

let builtRoutePaths: string[] = [];

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  build: {
    // Generate source maps but omit the sourceMappingURL comment so browsers
    // don't advertise/fetch them. Maps are uploaded to New Relic for
    // symbolicated stack traces (see scripts/upload-sourcemaps.mjs).
    // Override via SOURCEMAP_MODE (e.g. the test deploy uses linked maps).
    sourcemap: SOURCEMAP_MODE,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // Separate vendor dependencies to enable better caching and reduce main bundle
          if (
            id.includes('node_modules/vue') ||
            id.includes('node_modules/vue-router') ||
            id.includes('node_modules/@unhead') ||
            id.includes('node_modules/@imagekit')
          ) {
            return 'vendor';
          }
          // Separate gtag into its own chunk since it's non-critical for initial render
          if (id.includes('node_modules/vue-gtag')) {
            return 'gtag';
          }
        }
      }
    }
  },
  ssgOptions: {
    // Generate route files as .html so `/meet-julia` is not treated as a directory URL.
    dirStyle: 'flat',
    includedRoutes(paths) {
      builtRoutePaths = [...paths];
      return paths;
    },
    async onFinished() {
      const distDir = resolve(process.cwd(), 'dist');
      const assetsDir = resolve(distDir, 'assets');

      // Collect all emitted CSS to inline. Vite's <link rel="stylesheet crossorigin="">
      // causes Chrome to attribute the CSS request to the JS module context rather than
      // the HTML parser, creating a critical-chain dependency. Inlining eliminates
      // the request entirely.
      let cssContent = '';
      const assetFiles = await readdir(assetsDir);
      for (const file of assetFiles) {
        if (file.endsWith('.css') && !file.endsWith('.css.map')) {
          cssContent += await readFile(resolve(assetsDir, file), 'utf8');
        }
      }

      const htmlFiles = (await readdir(distDir)).filter((f) => f.endsWith('.html'));
      await Promise.all(
        htmlFiles.map(async (file) => {
          const htmlPath = resolve(distDir, file);
          let html = await readFile(htmlPath, 'utf8');

          // Inline the CSS so the browser doesn't need a separate request for it.
          // Vite's <link rel="stylesheet" crossorigin=""> causes Chrome to attribute
          // the CSS fetch to the JS module context, creating a critical chain.
          if (cssContent) {
            html = html.replace(/<link[^>]+rel="stylesheet"[^>]*>/g, '');
            html = html.replace('</head>', `<style>${cssContent}</style></head>`);
          }

          await writeFile(htmlPath, html, 'utf8');
        })
      );

      const sitemapXml = buildSitemapXml(resolveSitemapRoutes(builtRoutePaths));
      await writeFile(resolve(distDir, 'sitemap.xml'), sitemapXml, 'utf8');
    }
  }
});
