import { existsSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { appRoutePaths } from '../../src/lib/routePaths';
import {
  buildSitemapXml,
  canReadHistory,
  pageContentFiles,
  readPageComponents,
  resolveSitemapEntries,
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

  describe('readPageComponents', () => {
    // The route -> component map is parsed out of routes.ts rather than kept as
    // a second copy here. That only stays correct while the parse keeps working,
    // so assert it covers every route and lands on files that exist — adding a
    // page, or restyling routes.ts past what the pattern matches, fails here
    // instead of silently dropping that page's lastmod.
    it('resolves every app route to a page component that exists', () => {
      const components = readPageComponents();

      for (const routePath of appRoutePaths) {
        const component = components.get(routePath);
        expect(component, `no page component parsed for ${routePath}`).toBeDefined();
        expect(existsSync(component!), `${component} does not exist`).toBe(true);
      }
    });
  });

  describe('pageContentFiles', () => {
    it('includes the components a page renders directly', () => {
      const volunteerPage = readPageComponents().get('/volunteer')!;

      const files = pageContentFiles(volunteerPage);

      expect(files).toContain(volunteerPage);
      expect(files.some((file) => file.endsWith('JuliaContactForm.vue'))).toBe(true);
    });

    it('excludes shared logic, so a lib refactor is not a content change', () => {
      const yardSignPage = readPageComponents().get('/yard-signs')!;

      const files = pageContentFiles(yardSignPage);

      expect(files.some((file) => file.includes('/lib/'))).toBe(false);
      expect(files.some((file) => file.includes('/composables/'))).toBe(false);
    });
  });

  describe('resolveSitemapEntries', () => {
    it('dates each route independently rather than stamping them all alike', () => {
      // The defect this replaces: every page carried the build date, so all
      // eight claimed to change on every deploy. Distinct dates are the point.
      const entries = resolveSitemapEntries([...appRoutePaths]);

      expect(entries).toHaveLength(appRoutePaths.length);

      if (!canReadHistory()) return; // shallow checkout: nothing to assert

      const dates = entries.map((entry) => entry.lastmod);
      expect(dates.every((date) => date && /^\d{4}-\d{2}-\d{2}$/.test(date))).toBe(true);
      expect(new Set(dates).size).toBeGreaterThan(1);
    });

    it('omits lastmod for a route with no page component', () => {
      expect(resolveSitemapEntries(['/not-a-route'])).toEqual([{ path: '/not-a-route' }]);
    });
  });

  describe('buildSitemapXml', () => {
    it('emits a url entry for each route', () => {
      const xml = buildSitemapXml([{ path: '/' }, { path: '/events' }], 'https://example.test');

      expect(xml).toContain('<loc>https://example.test/</loc>');
      expect(xml).toContain('<loc>https://example.test/events</loc>');
      expect(xml).toMatch(/^<\?xml version="1.0" encoding="UTF-8"\?>/);
      expect(xml).toContain('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">');
    });

    it('defaults to the production site URL', () => {
      const xml = buildSitemapXml([{ path: '/donate' }]);

      expect(xml).toContain(`<loc>${SITE_URL}/donate</loc>`);
    });

    it('emits the entry lastmod when one is known', () => {
      const xml = buildSitemapXml([{ path: '/events', lastmod: '2026-07-29' }]);

      expect(xml).toContain('<lastmod>2026-07-29</lastmod>');
    });

    it('omits the lastmod element entirely when the date is unknown', () => {
      // An absent lastmod is ignored by crawlers; a wrong one teaches them to
      // distrust the field. Never emit a date we cannot stand behind.
      const xml = buildSitemapXml([{ path: '/events' }]);

      expect(xml).not.toContain('<lastmod>');
      expect(xml).toContain('<loc>');
    });
  });
});
