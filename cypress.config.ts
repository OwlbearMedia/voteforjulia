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

/** One line per signal that distinguishes a real response from a WAF challenge. */
function summarizeProbe(label: string, status: number, headers: Headers, body: string): string {
  const server = headers.get('server') ?? '(none)';
  const allowOrigin = headers.get('access-control-allow-origin') ?? '(none)';
  // The tells are documented in docs/hosting.md#imunify360-waf-disabled: the
  // challenge answers 200 from openresty with a ~12 kB splash, so neither the
  // status code nor `server: LiteSpeed` on a good day proves anything.
  const challenged = /openresty/i.test(server) || /One moment, please/i.test(body);

  return [
    `  ${label} -> ${status}`,
    `    server: ${server}`,
    `    access-control-allow-origin: ${allowOrigin}`,
    `    WAF challenge: ${challenged ? 'YES — see docs/hosting.md#imunify360-waf-disabled' : 'no'}`
  ].join('\n');
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

          const probes: { label: string; url: string; init: RequestInit }[] = [
            {
              label: 'GET /health',
              url: `${apiBaseUrl}/health`,
              // Origin is sent even though a health check does not need it:
              // `add_cors_headers` only emits Access-Control-Allow-Origin when
              // it is present, so without it every probe would report the
              // header as missing and the one line that matters would be noise.
              init: { method: 'GET', headers: { Origin: origin } }
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
              }
            }
          ];

          for (const { label, url, init } of probes) {
            try {
              const response = await fetch(url, { ...init, redirect: 'manual' });
              const body = await response.text().catch(() => '');
              lines.push(summarizeProbe(label, response.status, response.headers, body));
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
