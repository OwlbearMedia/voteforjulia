import 'vite-ssg'
import { writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

const SITE_URL = 'https://voteforjulia.com'
const ROUTE_EXTENSIONS: Record<string, string> = {
  '/meet-julia': '.html',
  '/volunteer': '.html',
  '/secret-recipe': '.html',
  '/donate': '.html',
}

let builtRoutePaths: string[] = []

function toOutputPath(route: string): string {
  const extension = ROUTE_EXTENSIONS[route]
  if (!extension || route === '/') {
    return route
  }

  return `${route}${extension}`
}

function buildSitemapXml(routePaths: string[]): string {
  const today = new Date().toISOString().split('T')[0]
  const urls = routePaths
    .map((route) => {
      const outputPath = toOutputPath(route)
      const loc = outputPath === '/' ? `${SITE_URL}/` : `${SITE_URL}${outputPath}`
      const priority = outputPath === '/' ? '1.0' : '0.9'

      return `  <url>\n    <loc>${loc}</loc>\n    <lastmod>${today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>${priority}</priority>\n  </url>`
    })
    .join('\n')

  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
  ],
  ssgOptions: {
    includedRoutes(paths) {
      builtRoutePaths = [...paths]
      return paths
    },
    onPageRendered(_route, renderedHTML) {
      const linkRewrites = Object.entries(ROUTE_EXTENSIONS).map(([from, extension]) => {
        return [from, `${from}${extension}`] as const
      })

      return linkRewrites.reduce((html, [from, to]) => {
        return html.replaceAll(`href="${from}"`, `href="${to}"`)
      }, renderedHTML)
    },
    async onFinished() {
      const sitemapRoutes = builtRoutePaths.length > 0
        ? builtRoutePaths
        : ['/', ...Object.keys(ROUTE_EXTENSIONS)]
      const sitemapXml = buildSitemapXml(sitemapRoutes)

      await writeFile(resolve(process.cwd(), 'dist/sitemap.xml'), sitemapXml, 'utf8')
    },
  },
})
