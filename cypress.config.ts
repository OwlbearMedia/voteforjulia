import { readFileSync } from 'fs';
import { defineConfig } from 'cypress';
import { google } from 'googleapis';

type CypressEnv = Record<string, unknown>;

function getCredentials(env: CypressEnv): object {
  const json = env.GOOGLE_SERVICE_ACCOUNT_JSON ?? process.env.GOOGLE_SERVICE_ACCOUNT_JSON;
  if (json) {
    if (typeof json === 'object') return json;
    if (typeof json === 'string') return JSON.parse(json) as object;
  }

  const file =
    (env.GOOGLE_SERVICE_ACCOUNT_FILE as string | undefined) ??
    process.env.GOOGLE_SERVICE_ACCOUNT_FILE;
  if (file) return JSON.parse(readFileSync(file, 'utf8')) as object;

  throw new Error(
    'Google Sheets credentials not configured. ' +
      'Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE in cypress.env.json or as an env var.'
  );
}

function getSpreadsheetId(env: CypressEnv): string {
  const id = env.GOOGLE_SHEETS_SPREADSHEET_ID ?? process.env.GOOGLE_SHEETS_SPREADSHEET_ID;
  if (!id || typeof id !== 'string')
    throw new Error(
      'GOOGLE_SHEETS_SPREADSHEET_ID is not set in cypress.env.json or as an env var.'
    );
  return id;
}

function buildSheetsClient(env: CypressEnv) {
  const auth = new google.auth.GoogleAuth({
    credentials: getCredentials(env),
    scopes: ['https://www.googleapis.com/auth/spreadsheets']
  });
  return google.sheets({ version: 'v4', auth });
}

// A1 ranges require a sheet title to be single-quoted whenever it contains
// anything other than letters, digits, or underscores (e.g. the "Yard Signs"
// worksheet's space) — mirrors api/services/sheets_service.py's
// _quote_sheet_title so both sides build the same range syntax.
function quoteSheetTitle(title: string): string {
  if (/^[A-Za-z0-9_]+$/.test(title)) {
    return title;
  }

  return `'${title.replace(/'/g, "''")}'`;
}

// The origin the forms actually post to. Declared rather than derived from
// `baseUrl`, because the relationship between the two is a hosting decision
// (ADR-0003), not a naming rule — and a wrong guess here would misreport the
// one thing this is meant to diagnose.
const DEFAULT_API_BASE_URL = 'https://test-api.voteforjulia.com';

function resolveApiBaseUrl(env: CypressEnv): string {
  const configured =
    (env.apiBaseUrl as string | undefined) ?? process.env.CYPRESS_API_BASE_URL ?? undefined;

  return (configured ?? DEFAULT_API_BASE_URL).replace(/\/+$/, '');
}

/** What the API returns when the API is what answered. */
interface ProbeExpectation {
  status: number;
  bodyIncludes?: string;
}

/**
 * Name the thing in front of the origin, when it can be named.
 *
 * Best-effort and deliberately allowed to say "unknown". Attribution is not
 * what the caller acts on — `servedByApp` is — and a confident wrong name costs
 * more than no name, which is how a run on 2026-08-14 came to blame Imunify360
 * for a hostname that was by then behind Cloudflare too.
 */
function identifyInterceptor(headers: Headers, body: string): string {
  const cookies = headers.get('set-cookie') ?? '';

  // Imunify360's WebShield: its splash sets this cookie, and the page reads
  // "One moment, please..." (docs/hosting.md#imunify360-waf-disabled).
  if (/wssplashchk/i.test(cookies) || /One moment, please/i.test(body)) {
    return 'Imunify360 WebShield (wssplashchk cookie / splash body)';
  }

  // Cloudflare's own challenge. `cf-mitigated` is set when it acts on a
  // request; the body markers cover the interstitial itself.
  if (headers.has('cf-mitigated') || /challenge-platform|__cf_chl|Just a moment/i.test(body)) {
    return 'Cloudflare challenge (cf-mitigated / challenge-platform)';
  }

  return 'unknown — check Cloudflare Security Events and probe the origin directly';
}

/**
 * One line per signal that distinguishes our API's response from anything else.
 *
 * **Asserts what the app returns rather than what a challenge looks like.** The
 * previous version keyed on `server: openresty`, which stopped working the day
 * the hostname went behind Cloudflare: the proxy rewrites `server` to
 * `cloudflare` on every response, so the tell could never fire again and the
 * check silently lost half its sensitivity. Splash pages also vary per vendor,
 * and there is no reason to keep a catalogue of them.
 *
 * What does not vary is our own response, so that is what gets checked. `server`
 * is still printed because it is useful once you know it is not proof.
 *
 * Returns the verdict alongside the text so the caller can act on it without
 * re-deriving it or, worse, grepping its own output.
 */
function summarizeProbe(
  label: string,
  status: number,
  headers: Headers,
  body: string,
  expected: ProbeExpectation
): { text: string; intercepted: boolean } {
  const server = headers.get('server') ?? '(none)';
  const allowOrigin = headers.get('access-control-allow-origin') ?? '(none)';

  const statusMatches = status === expected.status;
  const bodyMatches = !expected.bodyIncludes || body.includes(expected.bodyIncludes);
  const servedByApp = statusMatches && bodyMatches;

  const lines = [
    `  ${label} -> ${status}${statusMatches ? '' : ` (expected ${expected.status})`}`,
    `    server: ${server}`,
    `    access-control-allow-origin: ${allowOrigin}`,
    `    answered by our API: ${servedByApp ? 'yes' : 'NO — something else replied'}`
  ];

  if (!servedByApp) {
    lines.push(`    likely source: ${identifyInterceptor(headers, body)}`);
    lines.push(`    body (first 200 chars): ${body.slice(0, 200).replace(/\s+/g, ' ')}`);
  }

  return { text: lines.join('\n'), intercepted: !servedByApp };
}

/**
 * Raise the WAF verdict from spec output to a run-summary annotation.
 *
 * The diagnosis was already being printed correctly on 2026-08-07 and still
 * cost an hour, because it sat inside a failing spec's output where nobody
 * looks first — the run summary said only "Cypress tests: 2 failed". A
 * `::warning::` on stdout is how a Node task puts a line next to that result.
 *
 * Only in Actions: the syntax means nothing to a local `pnpm test:e2e`, where
 * it would just be a confusing extra line under a readable report.
 */
function annotateInterception(apiBaseUrl: string, source: string): void {
  if (process.env.GITHUB_ACTIONS !== 'true') return;

  // Must stay on one line — GitHub ends the command at the first newline.
  console.log(
    `::warning title=Form posts are being intercepted before they reach the API::` +
      `A request to ${apiBaseUrl} was answered by something other than Flask, and the reply carried no CORS headers. ` +
      `Every form post therefore fails in the browser as "Failed to fetch" with nothing reaching the app, so the API logs ` +
      `will be empty. This is not the site or the tests. Likely source: ${source}. ` +
      `Two things can do this now: the host's Imunify360 WebShield (disabled site-wide 2026-08-01, so its return means the ` +
      `disable no longer covers this hostname — docs/hosting.md#imunify360-waf-disabled) and Cloudflare, which has fronted ` +
      `these hostnames since 2026-08-14 (docs/hosting.md#migrating-dns-to-cloudflare). ` +
      `Attribute it before acting: Cloudflare rewrites "server" to cloudflare on every response, so that header no longer ` +
      `distinguishes them. Check Cloudflare Security Events for this timestamp, and probe the origin directly with ` +
      `--resolve ${apiBaseUrl.replace('https://', '')}:443:208.115.234.114 to see what the host alone returns. ` +
      `Re-running may pass by drawing a different runner IP, but only if the challenge is keyed to the runner — behind ` +
      `Cloudflare the origin sees Cloudflare's addresses, not GitHub's, so do not assume it.`
  );
}

export default defineConfig({
  e2e: {
    // Default to the staging site. Override with CYPRESS_BASE_URL for local dev:
    //   CYPRESS_BASE_URL=http://localhost:5173 pnpm test:e2e
    baseUrl: 'https://test.voteforjulia.com',
    allowCypressEnv: false,
    defaultCommandTimeout: 10000,
    // Chrome's autofill/password-manager heuristics can transiently disable
    // the first field of a fresh form (our fields use autocomplete="given-name"
    // etc.) in a clean CI profile, failing cy.type() with "targeted a disabled
    // element" even though the app never disables that input. A single retry
    // in run mode absorbs that class of infra flake without masking real
    // failures (which fail consistently, not once).
    retries: {
      runMode: 1,
      openMode: 0
    },
    setupNodeEvents(on, config) {
      const env = config.env as CypressEnv;

      on('before:browser:launch', (browser, launchOptions) => {
        if (browser.family === 'chromium' && browser.name !== 'electron') {
          launchOptions.args.push(
            '--disable-features=Autofill,AutofillServerCommunication,PasswordManagerOnboarding,AutofillAssistant'
          );
        }

        return launchOptions;
      });

      on('task', {
        // Browser-side console output never reaches `cypress run`'s stdout, so
        // the support file's failure diagnostics come back through here.
        log(message: string): null {
          console.log(message);

          return null;
        },

        /**
         * On a failed test, report what the *API* origin returns to this runner.
         *
         * The existing diagnostics re-probe the page URL, which is the wrong
         * host: both form specs submit cross-origin to the API (ADR-0003), so a
         * failure there shows up in the browser only as `Failed to fetch` — a
         * bare TypeError with no status, no headers and no body. Diagnosing one
         * previously meant pulling the screenshot artifact and reading the red
         * text under the submit button.
         *
         * Runs in Node, not as `cy.request`, for two reasons. Node does not
         * enforce CORS, so the preflight's response headers can be *inspected*
         * rather than acted on — the browser's whole problem is that a missing
         * `Access-Control-Allow-Origin` is unreadable from script. And a
         * rejected fetch is caught here, whereas a `cy.request` network error
         * would fail the afterEach hook and bury the failure it came to explain.
         *
         * Same process as the browser, so same source IP — which is what makes
         * this able to see an IP-reputation challenge at all.
         */
        async probeApi({ origin }: { origin: string }): Promise<null> {
          const apiBaseUrl = resolveApiBaseUrl(env);
          const lines = [`[diagnostics] API origin ${apiBaseUrl}, probed from the runner:`];

          // `expected` is what the API itself returns, and is the whole basis of
          // the verdict — see summarizeProbe. Keep these in step with app.py:
          // `/health` returns 200 with `"status": "ok"`, and the OPTIONS
          // short-circuit returns 204 with an empty body.
          const probes: {
            label: string;
            url: string;
            init: RequestInit;
            expected: ProbeExpectation;
          }[] = [
            {
              label: 'GET /health',
              url: `${apiBaseUrl}/health`,
              // Origin is sent even though a health check does not need it:
              // `add_cors_headers` only emits Access-Control-Allow-Origin when
              // it is present, so without it every probe would report the
              // header as missing and the one line that matters would be noise.
              init: { method: 'GET', headers: { Origin: origin } },
              // No space after the colon: Flask's `jsonify` emits compact JSON,
              // and a string copied from pretty-printed output never matches.
              // The same trap is documented for the synthetic monitor's
              // validation string in docs/monitoring.md.
              expected: { status: 200, bodyIncludes: '"status":"ok"' }
            },
            {
              // The preflight is the request that actually breaks: the browser
              // sends it before any JSON POST, and a challenge or a missing
              // allowlist entry stops the submission before it is ever made.
              label: `OPTIONS /send-email (preflight for Origin: ${origin})`,
              url: `${apiBaseUrl}/send-email`,
              init: {
                method: 'OPTIONS',
                headers: {
                  Origin: origin,
                  'Access-Control-Request-Method': 'POST',
                  'Access-Control-Request-Headers': 'content-type'
                }
              },
              expected: { status: 204 }
            }
          ];

          let intercepted = false;
          let interceptor = 'unknown';

          for (const { label, url, init, expected } of probes) {
            try {
              const response = await fetch(url, { ...init, redirect: 'manual' });
              const body = await response.text().catch(() => '');
              const probe = summarizeProbe(
                label,
                response.status,
                response.headers,
                body,
                expected
              );
              if (probe.intercepted && !intercepted) {
                interceptor = identifyInterceptor(response.headers, body);
              }
              intercepted = intercepted || probe.intercepted;
              lines.push(probe.text);
            } catch (error) {
              // A rejection here is the interesting case, not an error to raise:
              // it means the runner cannot reach the API at all, which is the
              // same thing the browser reports as `Failed to fetch`.
              //
              // The cause is unwrapped because Node's own message is always the
              // useless "fetch failed"; the reason that tells a DNS failure from
              // a refused connection from a TLS error is one level down.
              const { message, cause } = error as Error & { cause?: Error };
              const reason = cause?.message ? `${message} (${cause.message})` : message;
              lines.push(`  ${label} -> request failed: ${reason}`);
            }
          }

          console.log(lines.join('\n'));

          if (intercepted) {
            annotateInterception(apiBaseUrl, interceptor);
          }

          return null;
        },

        async findSheetRow({
          email,
          worksheet: worksheetOverride
        }: {
          email: string;
          worksheet?: string;
        }): Promise<{
          rowIndex: number;
          row: string[];
          totalRows: number;
        } | null> {
          const spreadsheetId = getSpreadsheetId(env);
          const worksheet =
            worksheetOverride ??
            (env.GOOGLE_SHEETS_WORKSHEET as string | undefined) ??
            process.env.GOOGLE_SHEETS_WORKSHEET;
          const sheets = buildSheetsClient(env);

          const response = await sheets.spreadsheets.values.get({
            spreadsheetId,
            range: worksheet ? `${quoteSheetTitle(worksheet)}!A:G` : 'A:G'
          });

          const rows = response.data.values ?? [];
          // Column layout (contact form): [timestamp, firstName, lastName, email, phone, helpWays, message]
          // Column layout (yard sign): [timestamp, firstName, lastName, email, phone, address, preferredPayment]
          const rowIndex = rows.findIndex((row) => row[3] === email);
          if (rowIndex < 0) return null;

          // `totalRows` is what lets the specs check *where* the row landed, not
          // just that it exists. values.get trims trailing empty rows, so this
          // is the height of the real data — a correctly appended submission is
          // the last of them. Searching every row for the email, which is all
          // this task used to do, passes just as happily on a row stranded 900
          // rows below the data as on one in the right place; that is precisely
          // how the August 2026 outage got through CI for four days.
          return { rowIndex, row: rows[rowIndex] as string[], totalRows: rows.length };
        },

        async deleteSheetRow({
          rowIndex,
          worksheet: worksheetOverride
        }: {
          rowIndex: number;
          worksheet?: string;
        }): Promise<true> {
          const spreadsheetId = getSpreadsheetId(env);
          const worksheet =
            worksheetOverride ??
            (env.GOOGLE_SHEETS_WORKSHEET as string | undefined) ??
            process.env.GOOGLE_SHEETS_WORKSHEET;
          const sheets = buildSheetsClient(env);

          // Resolve the numeric sheetId for the named worksheet.
          const spreadsheet = await sheets.spreadsheets.get({ spreadsheetId });
          const sheet = spreadsheet.data.sheets?.find((s) => s.properties?.title === worksheet);
          const sheetId = sheet?.properties?.sheetId ?? 0;

          await sheets.spreadsheets.batchUpdate({
            spreadsheetId,
            requestBody: {
              requests: [
                {
                  deleteDimension: {
                    range: {
                      sheetId,
                      dimension: 'ROWS',
                      startIndex: rowIndex,
                      endIndex: rowIndex + 1
                    }
                  }
                }
              ]
            }
          });

          return true;
        }
      });
    }
  }
});
