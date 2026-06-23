import 'vite-ssg';
import { writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { defineConfig, type Plugin } from 'vite';
import vue from '@vitejs/plugin-vue';

const SITE_URL = 'https://voteforjulia.com';

// Vite injects <script type="module"> before <link rel="stylesheet"> in the
// generated HTML. Lighthouse's preload scanner then sees the CSS as a level-3
// dependency (HTML → JS → CSS) instead of level-2. Moving the stylesheet link
// before the module script breaks that chain.
function cssBeforeJs(): Plugin {
  return {
    name: 'css-before-js',
    apply: 'build',
    transformIndexHtml: {
      order: 'post',
      handler(html) {
        const cssLinks: string[] = [];
        const stripped = html.replace(/<link[^>]+rel="stylesheet"[^>]*>/g, (match) => {
          cssLinks.push(match);
          return '';
        });
        if (cssLinks.length === 0) return html;
        return stripped.replace(/(<script type="module")/, `${cssLinks.join('\n')}\n$1`);
      }
    }
  };
}

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
  plugins: [vue(), cssBeforeJs()],
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
      const sitemapRoutes =
        builtRoutePaths.length > 0
          ? builtRoutePaths
          : ['/', '/meet-julia', '/volunteer', '/secret-recipe', '/donate'];
      const sitemapXml = buildSitemapXml(sitemapRoutes);

      await writeFile(resolve(process.cwd(), 'dist/sitemap.xml'), sitemapXml, 'utf8');
    }
  }
});
