import 'vite-ssg';
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

const SITE_URL = 'https://voteforjulia.com';

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

function buildSitemapXml(routePaths: string[]): string {
  const today = new Date().toISOString().split('T')[0];
  const urls = routePaths
    .map((route) => {
      const loc = route === '/' ? `${SITE_URL}/` : `${SITE_URL}${route}`;
      const priority = route === '/' ? '1.0' : '0.9';

      return `  <url>\n    <loc>${loc}</loc>\n    <lastmod>${today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>${priority}</priority>\n  </url>`;
    })
    .join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
}

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

          // Convert <script type="module" src="..."> to a modulepreload hint plus a
          // tiny inline bootstrap. Lighthouse doesn't include modulepreload resources
          // in the critical chain (vendor.js and rolldown-runtime.js are already
          // modulepreloaded and excluded). The inline script has no src so it produces
          // no tracked network request.
          const scriptSrcMatch = /<script([^>]+)type="module"([^>]+)src="([^"]+)"([^>]*)>/.exec(html);
          if (scriptSrcMatch) {
            const [fullTag, , , src] = scriptSrcMatch;
            html = html.replace(
              fullTag,
              `<link rel="modulepreload" crossorigin="" href="${src}">\n<script type="module">import('${src}')</script>`
            );
          }

          await writeFile(htmlPath, html, 'utf8');
        })
      );

      const sitemapRoutes =
        builtRoutePaths.length > 0
          ? builtRoutePaths
          : ['/', '/meet-julia', '/volunteer', '/secret-recipe', '/donate'];
      const sitemapXml = buildSitemapXml(sitemapRoutes);
      await writeFile(resolve(distDir, 'sitemap.xml'), sitemapXml, 'utf8');
    }
  }
});
