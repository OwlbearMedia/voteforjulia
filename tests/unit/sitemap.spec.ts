import { describe, expect, it } from 'vitest';
import { appRoutePaths } from '../../src/lib/routePaths';
import {
  buildSitemapXml,
  resolveSitemapRoutes,
  SITE_URL
} from '../../sitemap.build';

describe('sitemap', () => {
  describe('resolveSitemapRoutes', () => {
    it('uses the SSG route list when present', () => {
      expect(resolveSitemapRoutes(['/', '/donate'])).toEqual(['/', '/donate']);
    });

    it('falls back to appRoutePaths when the SSG route list is empty', () => {
      expect(resolveSitemapRoutes([])).toEqual([...appRoutePaths]);
    });
  });

  describe('buildSitemapXml', () => {
    it('emits a url entry for each route', () => {
      const xml = buildSitemapXml(['/', '/events'], 'https://example.test');

      expect(xml).toContain('<loc>https://example.test/</loc>');
      expect(xml).toContain('<loc>https://example.test/events</loc>');
      expect(xml).toMatch(/^<\?xml version="1.0" encoding="UTF-8"\?>/);
      expect(xml).toContain('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">');
    });

    it('defaults to the production site URL', () => {
      const xml = buildSitemapXml(['/donate']);

      expect(xml).toContain(`<loc>${SITE_URL}/donate</loc>`);
    });
  });
});
