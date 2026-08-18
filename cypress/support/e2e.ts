// Cypress support file — runs before every spec file.
// Add global before/after hooks or custom commands here.

// The "Action Needed" primary-election modal fires on the first load of every
// page (mounted by App.vue, gated by a sessionStorage flag) and its
// full-viewport backdrop intercepts clicks on the forms under test. Seed the
// dismissed flag before the app mounts on every cy.visit so the modal never
// opens during e2e runs.
// Key mirrors PRIMARY_MODAL_KEY in src/components/JuliaPrimaryModal.vue.
const PRIMARY_MODAL_KEY = 'primaryModalDismissed';

Cypress.Commands.overwrite('visit', (originalFn, url, options) => {
  const usingOptionsObject = typeof url === 'object' && url !== null;
  const visitOptions = (
    usingOptionsObject ? url : (options ?? {})
  ) as Partial<Cypress.VisitOptions>;
  const userOnBeforeLoad = visitOptions.onBeforeLoad;

  visitOptions.onBeforeLoad = (win) => {
    win.sessionStorage.setItem(PRIMARY_MODAL_KEY, 'true');
    userOnBeforeLoad?.(win);
  };

  return usingOptionsObject
    ? originalFn(visitOptions as Partial<Cypress.VisitOptions> & { url: string })
    : originalFn(url as string, visitOptions);
});

// --- Failure diagnostics ---
//
// Intermittently, and so far only from the CI runner, every spec's first
// cy.visit loops: the same URL loads over and over until Cypress's
// redirectionLimit (20) trips with "The application redirected to <url> more
// than 20 times". It hits /donate, /volunteer and /yard-signs in the same run,
// clears on a plain re-run of the job against the same deployment, and cannot
// be reproduced locally against that same deployed site — so the suspect is
// what the runner is served, not the app (nothing in the bundle navigates or
// reloads).
//
// Cypress counts one "redirect" per window:load at an unchanged href, so the
// AUT really is loading 21 times. Record what each load actually was, plus any
// uncaught app exception; on a failed test it all goes to the terminal via the
// `log` task, which is the only channel `cypress run` puts in the CI log.
interface AutLoad {
  at: string;
  href: string;
  title: string;
  /** 'navigate' | 'reload' | 'back_forward' — says whether the page reloaded itself. */
  navigationType: string;
  htmlHead: string;
}

const autLoads: AutLoad[] = [];
const autErrors: string[] = [];

beforeEach(() => {
  autLoads.length = 0;
  autErrors.length = 0;
});

// Probe the API once per run, whether or not anything fails.
//
// This used to live only in the failure path, which meant a green run printed
// nothing — so there was no baseline to compare a failure against, and a run
// that was one flaky decision away from breaking looked identical to a healthy
// one. On 2026-08-14 an interception took out both form specs, the re-run
// passed, and neither run left any evidence of what had answered.
//
// The task de-duplicates across spec files, so this costs two requests per run
// rather than two per spec.
before(() => {
  const baseUrl = Cypress.config('baseUrl');
  cy.task(
    'probeApi',
    { origin: baseUrl ? new URL(baseUrl).origin : '', when: 'baseline, before any spec ran' },
    { log: false }
  );
});

// Record, but do not swallow: returning undefined leaves Cypress's default
// behaviour (an uncaught app error fails the test) alone.
Cypress.on('uncaught:exception', (err) => {
  autErrors.push(err.stack ?? `${err.name}: ${err.message}`);
});

Cypress.on('window:load', (win) => {
  const [navigation] = win.performance.getEntriesByType(
    'navigation'
  ) as PerformanceNavigationTiming[];

  autLoads.push({
    at: new Date().toISOString(),
    href: win.location.href,
    title: win.document.title,
    navigationType: navigation?.type ?? 'unknown',
    // Enough to tell the real page apart from a host error page or a bot
    // challenge, without dumping 40 kB of prerendered markup per load.
    htmlHead: win.document.documentElement.outerHTML.slice(0, 200).replace(/\s+/g, ' ')
  });
});

afterEach(function () {
  if (this.currentTest?.state !== 'failed') {
    return;
  }

  cy.task(
    'log',
    `[diagnostics] AUT fired ${autLoads.length} load(s) during "${this.currentTest.title}":\n` +
      autLoads.map((load, index) => `  ${index + 1}. ${JSON.stringify(load)}`).join('\n') +
      `\n[diagnostics] ${autErrors.length} uncaught exception(s) in the AUT:\n` +
      autErrors.map((stack, index) => `  ${index + 1}. ${stack}`).join('\n'),
    { log: false }
  );

  const url = autLoads.at(-1)?.href ?? Cypress.config('baseUrl');

  // Then the API origin. The page probe below only ever covers the host the
  // browser navigated to, and the form specs fail on a cross-origin POST to a
  // *different* host (ADR-0003) — where the browser reports nothing but
  // `Failed to fetch`. Without this the two are indistinguishable in the log:
  // a healthy site serving a page whose submit button quietly cannot reach the
  // API looks exactly like a site that is fine.
  // `force` because the baseline above has already run: an interception can
  // begin part-way through a run, so the reading taken at the moment of failure
  // is the one that matters most.
  cy.task(
    'probeApi',
    { origin: url ? new URL(url).origin : '', when: 'after a failure', force: true },
    { log: false }
  );

  // Ask for the same URL again, straight from the Cypress proxy, so the log
  // shows the status, headers and body the runner is being served right now.
  if (!url) {
    return;
  }

  cy.request({ url, failOnStatusCode: false, log: false }).then((response) => {
    // CSP and Permissions-Policy are long, static, and irrelevant here; the
    // rest of the headers are what would give away an error page, a challenge
    // or a proxy in between.
    const headers = Object.fromEntries(
      Object.entries(response.headers).filter(
        ([name]) => !['content-security-policy', 'permissions-policy'].includes(name.toLowerCase())
      )
    );

    cy.task(
      'log',
      `[diagnostics] GET ${url} -> ${response.status}\n` +
        `  headers: ${JSON.stringify(headers)}\n` +
        `  body: ${String(response.body).slice(0, 300).replace(/\s+/g, ' ')}`,
      { log: false }
    );
  });
});
