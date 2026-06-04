import 'vite-ssg'
import { writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const SITE_URL = 'https://voteforjulia.com'

let builtRoutePaths: string[] = []

function buildSitemapXml(routePaths: string[]): string {
  const today = new Date().toISOString().split('T')[0]
  const urls = routePaths
    .map((route) => {
      const loc = route === '/' ? `${SITE_URL}/` : `${SITE_URL}${route}`
      const priority = route === '/' ? '1.0' : '0.9'

      return `  <url>\n    <loc>${loc}</loc>\n    <lastmod>${today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>${priority}</priority>\n  </url>`
    })
    .join('\n')

  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // Separate vendor dependencies to enable better caching and reduce main bundle
          if (id.includes('node_modules/vue') || 
              id.includes('node_modules/vue-router') ||
              id.includes('node_modules/@unhead') ||
              id.includes('node_modules/@imagekit')) {
            return 'vendor'
          }
          // Separate gtag into its own chunk since it's non-critical for initial render
          if (id.includes('node_modules/vue-gtag')) {
            return 'gtag'
          }
        }
      }
    }
  },
  ssgOptions: {
    // Generate route files as .html so `/meet-julia` is not treated as a directory URL.
    dirStyle: 'flat',
    includedRoutes(paths) {
      builtRoutePaths = [...paths]
      return paths
    },
    async onFinished() {
      const sitemapRoutes = builtRoutePaths.length > 0
        ? builtRoutePaths
        : ['/', '/meet-julia', '/volunteer', '/secret-recipe', '/donate']
      const sitemapXml = buildSitemapXml(sitemapRoutes)

      await writeFile(resolve(process.cwd(), 'dist/sitemap.xml'), sitemapXml, 'utf8')
    },
  },
})
