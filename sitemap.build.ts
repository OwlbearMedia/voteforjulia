import { appRoutePaths } from './src/lib/routePaths';

export const SITE_URL = 'https://voteforjulia.com';

export function resolveSitemapRoutes(builtRoutePaths: string[]): string[] {
  return builtRoutePaths.length > 0 ? builtRoutePaths : [...appRoutePaths];
}

export function buildSitemapXml(routePaths: string[], siteUrl = SITE_URL): string {
  const today = new Date().toISOString().split('T')[0];
  const urls = routePaths
    .map((route) => {
      const loc = route === '/' ? `${siteUrl}/` : `${siteUrl}${route}`;
      const priority = route === '/' ? '1.0' : '0.9';

      return `  <url>\n    <loc>${loc}</loc>\n    <lastmod>${today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>${priority}</priority>\n  </url>`;
    })
    .join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
}
