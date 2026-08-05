import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, relative, resolve } from 'node:path';
import { appRoutePaths } from './src/lib/routePaths';

export const SITE_URL = 'https://voteforjulia.com';

const PROJECT_ROOT = import.meta.dirname;
const ROUTES_MODULE = resolve(PROJECT_ROOT, 'src/lib/routes.ts');

/** One `<url>` in the sitemap. `lastmod` is omitted when it is not known. */
export interface SitemapEntry {
  path: string;
  lastmod?: string;
}

export function resolveSitemapRoutes(builtRoutePaths: string[]): string[] {
  return builtRoutePaths.length > 0 ? builtRoutePaths : [...appRoutePaths];
}

/**
 * Route path -> page component, read out of `src/lib/routes.ts` rather than
 * duplicated here. A second copy of this mapping would be one more thing to
 * keep in step when a page is added, and nothing would notice if it drifted;
 * `tests/unit/sitemap.spec.ts` asserts every route still resolves to a file
 * that exists.
 */
export function readPageComponents(routesModule = ROUTES_MODULE): Map<string, string> {
  const source = readFileSync(routesModule, 'utf8');
  const moduleDir = dirname(routesModule);
  const pattern = /(['"])(\/[^'"]*)\1\s*:\s*\(\)\s*=>\s*import\((['"])([^'"]+)\3\)/g;

  const components = new Map<string, string>();
  for (const [, , routePath, , importPath] of source.matchAll(pattern)) {
    components.set(routePath, resolve(moduleDir, importPath));
  }

  return components;
}

/**
 * The files whose content *is* the page, for the purpose of "when did this page
 * last change".
 *
 * The page component plus the components it renders directly — that is what
 * picks up e.g. `/volunteer` changing when the volunteer form's copy does,
 * since `JuliaVolunteer.vue` is mostly a wrapper around `JuliaContactForm.vue`.
 *
 * Deliberately *not* transitive, and deliberately excluding `src/lib` and
 * `src/composables`: a refactor of the fetch helper or a shared `<head>` tweak
 * is not a content change, and letting it move every page's `lastmod` would
 * put us back to the uniform timestamp this replaces.
 */
export function pageContentFiles(pageComponent: string): string[] {
  const source = readFileSync(pageComponent, 'utf8');
  const pattern = /from\s*(['"])([^'"]*\/components\/[^'"]+\.vue)\1/g;
  const pageDir = dirname(pageComponent);

  const files = [pageComponent];
  for (const [, , importPath] of source.matchAll(pattern)) {
    files.push(resolve(pageDir, importPath));
  }

  return files;
}

/**
 * How this module reaches git. Injectable for the same reason
 * `readPageComponents` takes its routes module as an argument: the dating logic
 * is otherwise only testable against whatever the working clone's history
 * happens to look like, which makes the tests hostage to it. One repo-wide
 * commit dates every page alike — a legitimate state that reads exactly like
 * the build-date defect `resolveSitemapEntries` exists to prevent.
 */
export type GitRunner = (args: string[]) => string;

const runGit: GitRunner = (args) =>
  execFileSync('git', args, { cwd: PROJECT_ROOT, encoding: 'utf8' }).trim();

/**
 * Whether git can answer "when did this file last change" truthfully here.
 *
 * In a shallow clone it cannot, and it fails in the worst possible way: `git
 * log -1 -- <file>` reports the *tip* commit for every path, because the
 * shallow boundary looks like the commit that introduced the whole tree. That
 * yields one identical timestamp for all eight pages — precisely the useless
 * uniform `lastmod` this exists to stop — while looking like real data. So the
 * check is explicit and the caller omits `lastmod` rather than emitting a date
 * it cannot stand behind. Deploy builds check out full history for this reason.
 */
export function canReadHistory(git: GitRunner = runGit): boolean {
  try {
    return git(['rev-parse', '--is-shallow-repository']) === 'false';
  } catch {
    return false;
  }
}

/** ISO-8601 date (no time) of the last commit touching any of `files`. */
function lastCommitDate(files: string[], git: GitRunner): string | undefined {
  const paths = files.map((file) => relative(PROJECT_ROOT, file));

  return git(['log', '-1', '--format=%cs', '--', ...paths]) || undefined;
}

/**
 * Sitemap entries for `routePaths`, dated from the history of the files that
 * render them.
 *
 * A route with no resolvable page component, or no commit touching it yet
 * (added but not committed), simply gets no `lastmod`. Omission is the honest
 * degradation: `lastmod` is optional in the sitemap protocol and crawlers
 * ignore an absent one, whereas a wrong one is worse than useless — a date that
 * moves on every deploy trains them to disregard the field entirely.
 */
export function resolveSitemapEntries(
  routePaths: string[],
  git: GitRunner = runGit
): SitemapEntry[] {
  if (!canReadHistory(git)) {
    console.warn(
      '[sitemap] Not a full git checkout — emitting the sitemap without <lastmod>. ' +
        'Deploy builds use fetch-depth: 0 so this does not affect the published site.'
    );

    return routePaths.map((path) => ({ path }));
  }

  const pageComponents = readPageComponents();

  return routePaths.map((path) => {
    const pageComponent = pageComponents.get(path);
    if (!pageComponent) {
      console.warn(`[sitemap] No page component found for "${path}"; omitting <lastmod>.`);

      return { path };
    }

    return { path, lastmod: lastCommitDate(pageContentFiles(pageComponent), git) };
  });
}

export function buildSitemapXml(entries: SitemapEntry[], siteUrl = SITE_URL): string {
  const urls = entries
    .map(({ path, lastmod }) => {
      const loc = path === '/' ? `${siteUrl}/` : `${siteUrl}${path}`;
      const priority = path === '/' ? '1.0' : '0.9';
      const lastmodLine = lastmod ? `\n    <lastmod>${lastmod}</lastmod>` : '';

      return `  <url>\n    <loc>${loc}</loc>${lastmodLine}\n    <changefreq>weekly</changefreq>\n    <priority>${priority}</priority>\n  </url>`;
    })
    .join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
}
