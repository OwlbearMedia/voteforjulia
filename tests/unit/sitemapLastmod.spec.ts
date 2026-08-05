import { describe, expect, it } from 'vitest';
import { resolveSitemapEntries, type GitRunner } from '../../sitemap.build';
import { appRoutePaths } from '../../src/lib/routePaths';

/**
 * Stand-in for `git`, answering from `datesByFile` — keyed on a filename
 * fragment, so a test can date one page differently from the rest without
 * caring which other components that page happens to render.
 */
function fakeGit(datesByFile: Record<string, string>, fallback = '2020-01-01'): GitRunner {
  return (args) => {
    if (args[0] === 'rev-parse') return 'false';

    const paths = args.slice(args.indexOf('--') + 1);
    const match = Object.keys(datesByFile).find((fragment) =>
      paths.some((path) => path.includes(fragment))
    );

    return match ? datesByFile[match] : fallback;
  };
}

describe('sitemap lastmod', () => {
  // The defect this guards: every page carried the *build* date, so all eight
  // claimed to change on every deploy. sitemap.spec.ts used to catch that by
  // asserting the live repo produced more than one distinct date, which fails
  // for a legitimate reason — one repo-wide commit (a formatting pass, a
  // codemod) touching every page really does date them all alike, and the
  // sitemap that results is correct. Worse, that check never ran in CI at all:
  // ci.yml checks out with fetch-depth: 1, and a shallow clone makes
  // resolveSitemapEntries bail before dating anything. Feeding git known dates
  // tests the property directly and runs everywhere.
  it('dates each route from its own history, not from the clock', () => {
    const entries = resolveSitemapEntries(
      [...appRoutePaths],
      fakeGit({ JuliaHome: '2021-03-04', JuliaDonate: '2022-07-08' })
    );
    const dated = Object.fromEntries(entries.map((entry) => [entry.path, entry.lastmod]));

    expect(dated['/']).toBe('2021-03-04');
    expect(dated['/donate']).toBe('2022-07-08');

    // Everything else falls through to the fake's default. Every date here is
    // in the past, so a build-date stamp could not have produced any of them.
    expect(dated['/events']).toBe('2020-01-01');
    expect(new Date().toISOString().slice(0, 10)).not.toBe('2020-01-01');
  });

  // The state the repo is in after a repo-wide reformat, and the one the old
  // live-history assertion could not tell apart from the defect above.
  it('is happy for every route to share a date when one commit touched them all', () => {
    const entries = resolveSitemapEntries([...appRoutePaths], fakeGit({}, '2026-08-04'));

    expect(entries).toHaveLength(appRoutePaths.length);
    expect(entries.every((entry) => entry.lastmod === '2026-08-04')).toBe(true);
  });

  it('omits lastmod entirely rather than guessing when the clone is shallow', () => {
    const shallow: GitRunner = (args) => (args[0] === 'rev-parse' ? 'true' : '2021-03-04');

    const entries = resolveSitemapEntries([...appRoutePaths], shallow);

    expect(entries.every((entry) => entry.lastmod === undefined)).toBe(true);
  });

  it('omits lastmod for a page git has no commit for yet', () => {
    expect(resolveSitemapEntries(['/'], fakeGit({}, '')).at(0)).toEqual({ path: '/' });
  });
});
