# [voteforjulia.com](https://voteforjulia.com/)

[![CI](https://github.com/OwlbearMedia/voteforjulia/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/OwlbearMedia/voteforjulia/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/OwlbearMedia/voteforjulia/graph/badge.svg)](https://codecov.io/gh/OwlbearMedia/voteforjulia)

![image](https://raw.githubusercontent.com/OwlbearMedia/voteforjulia/refs/heads/main/public/julia-social-banner.avif)

The official campaign website for Julia Hamann, candidate for Mayor of Mankato.

## Tech Stack

- Frontend: Vue 3 + Vite + Vite SSG
- Styling: Tailwind CSS v4 (CSS-first config, theme tokens in `src/style.css`; no `tailwind.config.js`). Class attributes are sorted by `prettier-plugin-tailwindcss`, so `pnpm format` decides their order
- Backend API: Flask (Python)
- Monitoring: New Relic Browser Agent + Google Analytics (via `gtag`)
- Frontend tests: Vitest + @vue/test-utils + jsdom
- E2E tests: Cypress
- CI/CD: GitHub Actions + SCP deploy

## Documentation

This README covers getting the site running. The `docs/` directory covers the
things the source can't tell you — read the relevant one before working in that
area:

- **[docs/architecture.md](docs/architecture.md)** — the system map: what runs
  where, how a form submission flows through the API to email and Google Sheets,
  the two environments, and an index of the architecture decision records in
  **[docs/adr/](docs/adr/)** explaining why the site is built this way (shared
  hosting rather than AWS, prerendering, no database, and so on). Start here if
  you're new to the project.
- **[docs/conventions.md](docs/conventions.md)** — how this codebase does things:
  the multi-file checklist for adding a page, `buildPageHead` for `<head>`/SEO,
  the Tailwind theme (the default palette is switched off, so `bg-red-500` does
  nothing), hand-rolled icons, declaring third-party custom elements, and the
  testing conventions.
- **[docs/hosting.md](docs/hosting.md)** — the runtime environment and both deploy
  pipelines: LiteSpeed rather than Apache (its `.htaccess` parser differs from
  Apache's in silent ways), the atomic production swap and rollback, and how
  deploys install Python dependencies into the host's cPanel virtualenv.
- **[docs/performance.md](docs/performance.md)** — the performance budgets CI
  enforces on every build: what "first load" is measured as, why Lighthouse runs
  against `dist/` rather than a dev server, and the rule for raising a threshold
  (same commit as the change, with a reason). Read it before a size increase
  turns CI red.
- **[docs/monitoring.md](docs/monitoring.md)** — what watches the site, which
  alerts will fire, and how to tell a genuine outage from a WAF false positive.
  The New Relic dashboard and alert definitions are version-controlled in
  [monitoring/](monitoring/), since New Relic has no export-to-git story.
- **[docs/donate-integration.md](docs/donate-integration.md)** — how the Donorbox
  widget and Stripe actually load on `/donate`, and which Content-Security-Policy
  and `Permissions-Policy` entries exist solely because of it.

The Flask API also has an OpenAPI 3.1 spec at
[api/openapi.yaml](api/openapi.yaml), kept in sync with the code by
[api/test_openapi_spec.py](api/test_openapi_spec.py).

## Prerequisites

- Node.js 22+
- pnpm 11+
- Python **3.11** for the API — not "3.11 or newer". It must match the interpreter
  in the host's cPanel virtualenv, which is what deploys install into. The version
  is declared once in [`.python-version`](.python-version); CI reads that same file.
  See [docs/hosting.md](docs/hosting.md#mind-the-interpreter-floor).

## Install Dependencies

Install frontend dependencies:

```bash
pnpm install
```

Install Python API dependencies into a project-local virtualenv:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r api/requirements-dev.txt
```

`api/requirements-dev.txt` includes `requirements.txt`, so this installs the
runtime pins production uses plus the dev-only tooling (pytest, ruff). Keep the
two files separate: deploys install with `--requirements-file requirements.txt`,
so only that file's pins reach the host — never add tooling to it.

VS Code picks up `.venv` at the repo root automatically. If the status bar
doesn't show `3.11.x ('.venv')`, run **Python: Select Interpreter** and choose
`./.venv/bin/python`. Workspace settings (interpreter, pytest, ruff-on-save) are
in `.vscode/settings.json`; install the recommended extensions when prompted.

Optional environment variable for local frontend API target:

```bash
export VITE_API_BASE_URL=http://localhost:5000
```

## Development

Start the local frontend dev server:

```bash
pnpm run dev
```

Preview a production build locally:

```bash
pnpm run build
pnpm run preview
```

### API docs (local only)

Browse the Flask API's OpenAPI spec in Swagger UI:

```bash
pnpm run docs:api
```

This opens `/api-docs.html` on the dev server, rendering
[api/openapi.yaml](api/openapi.yaml) directly — there is no second copy to keep
in sync. The page is a standalone Vite entry (`api-docs.html` at the repo root,
mounted by [src/dev/apiDocs.ts](src/dev/apiDocs.ts)), not a route in the Vue
app: it has no `appRoutePaths` entry, is never prerendered, never appears in the
sitemap, and is never emitted to `dist`, so it does not ship to the live site.

"Try it out" works, but every request is rewritten to `http://localhost:5000`
regardless of which server the dropdown shows — a real submission against
production would email the campaign and append a Google Sheet row. Start the
backend first or the calls will fail to connect:

```bash
.venv/bin/python -m api.app
```

## Build

Create the production static output in dist:

```bash
pnpm run build
```

Build details:

- Runs type-checking via vue-tsc.
- Generates static pages with Vite SSG.
- Produces deployable assets in dist.
- Emits hidden source maps by default (`build.sourcemap: 'hidden'`): `.js.map`
  files are generated without a `//# sourceMappingURL=` comment, so browsers
  never fetch or advertise them. Override with the `SOURCEMAP_MODE` env var
  (`true` for linked maps, `false` to disable).

Run type-check only:

```bash
pnpm exec vue-tsc -b
```

### Source Maps

In production, source maps are generated in `hidden` mode, uploaded to New Relic
for symbolicated stack traces, then stripped from `dist` so they are never
served publicly. The test deploy instead builds with `SOURCEMAP_MODE=true` and
keeps the linked maps on the server for in-browser debugging.

The source map mode is controlled by the `SOURCEMAP_MODE` env var (read in
`vite.config.ts`):

- unset (default) — `hidden`: maps emitted without a `sourceMappingURL` comment.
- `true` — linked maps that browser devtools load automatically.
- `false` — no source maps.

Relevant scripts:

- `pnpm run upload-sourcemaps` — uploads `dist/**/*.js.map` to the New Relic
  browser app (see `scripts/upload-sourcemaps.mjs`).
- `pnpm run strip-sourcemaps` — deletes `*.js.map` from `dist`.
- `pnpm run build:deploy` — builds, uploads source maps, then strips them. This
  is what the production deploy runs.

Upload manually:

```bash
pnpm run build
NEW_RELIC_API_KEY=NRAK-xxxxxxxx pnpm run upload-sourcemaps
```

Environment variables read by the upload script:

- `NEW_RELIC_API_KEY` (required) — a New Relic User key (`NRAK-…`).
- `NEW_RELIC_APP_ID` (optional) — browser application ID; defaults to the prod app.
- `PUBLIC_BASE_URL` (optional) — public origin the JS is served from; defaults to `https://voteforjulia.com`.
- `DIST_DIR` (optional) — build output directory; defaults to `dist`.

Upload failures (missing API key, a New Relic rejection, network errors, etc.)
are logged as warnings and do not fail the script or the build — sourcemap
upload is best-effort observability, not a build requirement. Check the deploy
logs for `::warning::` lines to see whether any maps failed to upload.

## Testing

### Frontend Unit Tests (Vitest)

Run all frontend unit tests:

```bash
pnpm test
```

Run in watch mode:

```bash
pnpm run test:watch
```

Tests are organized in a dedicated directory:

- tests/unit/App.spec.ts — pageHeaderTitle computed per route
- tests/unit/JuliaHeader.spec.ts
- tests/unit/JuliaFooter.spec.ts
- tests/unit/JuliaContactForm.spec.ts
- tests/unit/JuliaYardSignForm.spec.ts
- tests/unit/pages.spec.ts — render + SEO metadata for all page components (Home, About, Events, Volunteer, Donate, Secret Recipe, Yard Sign)
- tests/unit/routes.spec.ts — route paths and no `.html` aliases
- tests/unit/sitemap.spec.ts — sitemap fallback routes and XML generation
- tests/unit/useContactForm.spec.ts
- tests/unit/useYardSignForm.spec.ts
- tests/unit/analytics.spec.ts
- tests/unit/api.spec.ts
- tests/unit/newrelic.spec.ts
- tests/unit/bundleBudget.spec.ts — first-load measurement and budget evaluation (see [Performance Checks](#performance-checks))

### E2E Tests (Cypress)

Runs the volunteer form and yard sign form end-to-end against the staging site, submits a real form for each, verifies the entry was written to the corresponding Google Sheets tab, and deletes it.

Required environment variables (add to `cypress.env.json` locally, or set as environment variables):

- `GOOGLE_SHEETS_SPREADSHEET_ID` — the spreadsheet ID from the sheet URL
- `GOOGLE_SERVICE_ACCOUNT_JSON` — full JSON contents of the service account key file
- `GOOGLE_SHEETS_WORKSHEET` (optional) — worksheet name used by the volunteer/contact form test, defaults to `Sheet1`

The yard sign form test (`cypress/e2e/yard-sign-form.cy.ts`) targets the `Yard Signs` worksheet directly, matching the API's default `GOOGLE_SHEETS_YARDSIGN_WORKSHEET`.

Run in headless mode against the staging site:

```bash
pnpm test:e2e
```

Open the Cypress app for interactive debugging:

```bash
pnpm test:e2e:open
```

To run against a local dev server instead:

```bash
CYPRESS_BASE_URL=http://localhost:5173 pnpm test:e2e
```

### Python API Tests

Run backend API tests, lint, and format checks (the same three steps CI runs):

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

`pytest` discovers every `api/test_*.py` — configuration lives in
[`pytest.ini`](pytest.ini), so run it from the repo root. Use `ruff format .`
(without `--check`) to apply formatting; see [`ruff.toml`](ruff.toml) for the
enabled rules.

To see coverage locally (CI does this and uploads the result to Codecov):

```bash
.venv/bin/python -m pytest --cov --cov-report=term-missing
```

Coverage is opt-in rather than part of the default `pytest` run, so the everyday
suite stays fast — the same split as `pnpm test` versus `pnpm test:coverage`.
What gets measured is set by [`.coveragerc`](.coveragerc).

Older test files are `unittest.TestCase` classes and newer ones are plain pytest
functions; pytest collects both.

## Performance Checks

CI enforces two performance budgets on every build, and both can fail it. Run
them locally the same way CI does — build first, since neither command builds
for you:

```bash
pnpm build
pnpm perf                 # both checks
```

Or individually:

```bash
pnpm perf:budget          # bundle sizes — seconds
pnpm perf:lighthouse      # Lighthouse over dist/ — a few minutes
```

`pnpm perf:budget` checks the gzipped weight of a cold visit to each route —
the prerendered HTML (which has the CSS inlined into it) plus the JavaScript
needed before hydration — against the per-route numbers in
[`perf-budgets.json`](perf-budgets.json). A route with no entry in that file
fails the check, so adding a page means adding its budget.

`pnpm perf:lighthouse` runs Lighthouse three times per route against the built
`dist/`, asserting the thresholds in [`lighthouserc.cjs`](lighthouserc.cjs). It
needs a Chrome installation to drive. Only the assertions that proved stable in
CI fail the run — accessibility, SEO, best practices and CLS; the timing metrics
warn, because they swing far too widely on a shared runner to gate on.

To see where the bytes actually are, build with the bundle analyzer and open the
treemap:

```bash
pnpm analyze
open bundle-analysis/stats.html
```

Enforced thresholds are deliberately set just above what `main` currently
measures, so they fail on regressions rather than on the status quo — which also
means they need raising in the same commit as any change that legitimately needs
more room. **[docs/performance.md](docs/performance.md) covers the rules, which
checks are enforced versus advisory and why, and the measured CI spreads behind
that split.**

## CI and Deployment (GitHub Actions)

This repository uses a trunk-based workflow. All development happens on short-lived
feature branches that are merged directly to `main`. There are three workflow files:

- `.github/workflows/ci.yml`
- `.github/workflows/deploy-test.yml`
- `.github/workflows/deploy-production.yml`

### CI workflow

- Triggers: pull request events (`opened`, `synchronize`, `reopened`) and pushes to `main`. Runs tests only in both cases — deploys are handled by separate workflows triggered via `workflow_run`.
- File: `.github/workflows/ci.yml`
- Jobs — **Typecheck and frontend tests**, **Frontend performance budgets**, and **Python API lint and tests** run in parallel:
  - **Typecheck and frontend tests** — type-check, Prettier format check (`pnpm format:check`), ESLint, Vitest with coverage. The frontend coverage totals are posted to the workflow run's job summary, and the full report is uploaded to [Codecov](https://codecov.io/gh/OwlbearMedia/voteforjulia) under the `frontend` flag. Codecov uploads are skipped for Dependabot PRs, which do not have access to repository secrets, and never fail the build.
  - **Frontend performance budgets** — builds the site with the bundle analyzer, checks per-route first-load size against [`perf-budgets.json`](perf-budgets.json), then runs Lighthouse over `dist/` against the thresholds in [`lighthouserc.cjs`](lighthouserc.cjs). The size table is posted to the job summary; the treemap and Lighthouse reports are uploaded as the `performance-reports` artifact, including on failure. **The bundle budget and the accessibility, SEO, best-practices and CLS assertions fail the build**, so a size or accessibility regression blocks the production deploy until it is fixed or the budget is raised deliberately. The timing metrics (performance score, FCP, LCP, TBT) only warn — they vary too much on a shared CI runner to gate on. [docs/performance.md](docs/performance.md) has the measured spreads and the reasoning.
  - **Python API lint and tests** — `ruff check`, `ruff format --check`, then `pytest` across every `api/test_*.py` with coverage. Totals are posted to the job summary and the report is uploaded to Codecov under the `backend` flag. The interpreter comes from [`.python-version`](.python-version) so it can't drift from the host's.

The CI badge and Codecov coverage reflect the latest run on `main`.

### Test environment deploy workflow

- Trigger: CI workflow completes successfully on a pull request branch (not main). Dependabot PRs are skipped as they lack deploy secrets.
- File: `.github/workflows/deploy-test.yml`
- Jobs — a `gate` job checks the commit is still the branch HEAD and has an open PR, then **frontend** and **API** deploy chains run in parallel, each split into discrete jobs linked with `needs:` so a failure downstream doesn't force re-running the expensive steps upstream:
  - **Build test frontend → Deploy test frontend** — the build job builds with `VITE_API_BASE_URL=https://test-api.voteforjulia.com` and `SOURCEMAP_MODE=true`, injects noindex/nofollow tags, and uploads the `dist` output as a build artifact; the deploy job downloads that artifact and uploads it to `./public_html_test`. Rerunning just the deploy job (e.g. after a flaky SCP upload) reuses the existing build instead of rebuilding.
  - **Deploy test API** — uploads to `./api_test` and restarts Passenger
  - **Cypress e2e tests** — runs against the test site once both deploy jobs succeed

The test site always reflects the latest PR that passed CI. Since there is one test environment, concurrent PR deploys are serialized by a concurrency group — the most recently passing PR wins.

### Production deploy workflow

- Trigger: CI workflow completes successfully on `main`. This fires after every merged PR — CI is the single test gate, so tests are not re-run here.
- File: `.github/workflows/deploy-production.yml`
- Jobs — the frontend and API deploy chains run in parallel, each split into discrete jobs linked with `needs:` so a failed verification step can be rerun on its own instead of rebuilding and re-uploading everything:
  - **Build frontend → Deploy frontend → Verify frontend** — the build job checks out the exact commit CI verified and builds with `pnpm run build:deploy` and `VITE_API_BASE_URL=https://api.voteforjulia.com` (builds, uploads source maps to New Relic, then strips them from `dist`), uploading `dist` as a build artifact. The deploy job downloads that artifact, uploads it to a clean `./public_html_next` staging directory, and atomically swaps it into the live document root (`mv public_html public_html_prev && mv public_html_next public_html`). The verify job then checks the site is responding — if only this step fails (e.g. a transient network blip), rerunning it alone re-checks the already-deployed site without rebuilding or re-uploading anything.
  - **Deploy Python API → Verify Python API** — the deploy job checks out the same commit, uploads `api` to `./api`, and restarts Passenger; the verify job then checks the API is responding, independently rerunnable for the same reason as above.

The frontend swap is atomic: the new build is staged in full before a sub-second
directory rename promotes it, so visitors never see a mix of old and new files, and
files removed in the new build no longer linger. The previous build is retained at
`./public_html_prev` for one-command rollback (`mv public_html public_html_broken && mv public_html_prev public_html`).

If tests fail in either workflow, the job stops before any deployment steps. When a
downstream job (e.g. a verify job) fails, use GitHub Actions' "Re-run failed jobs" to
retry only that job and its dependents, rather than "Re-run all jobs".

### Required GitHub Secrets

- SSH_HOST
- SSH_USERNAME
- SSH_PRIVATE_KEY
- SSH_PASSPHRASE
- SSH_PORT
- NEW_RELIC_API_KEY (New Relic User key, `NRAK-…`, for uploading source maps in the production deploy)
- CODECOV_TOKEN (repository upload token from [codecov.io](https://codecov.io); enables the coverage upload and the README coverage badge)

### Test coverage (Codecov)

Both halves of the repo report coverage, uploaded from their own CI job under a
separate Codecov **flag**:

| Flag       | Job                       | Tool        | Report               | Covers |
| ---------- | ------------------------- | ----------- | -------------------- | ------ |
| `frontend` | Typecheck and frontend    | Vitest (V8) | `coverage/lcov.info` | `src/` |
| `backend`  | Python API lint and tests | pytest-cov  | `coverage-api.xml`   | `api/` |

The status and coverage badges at the top of this README reflect the latest run
on `main`.

Codecov posts four statuses: `project` (whole repo), `project/frontend`,
`project/backend`, and `patch` (only the lines a PR changed). All four use the
same 80% target, configured in [codecov.yml](codecov.yml). Whether a failing
status blocks a merge is a GitHub branch-protection setting, not something that
file controls.

Coverage exclusions are defined in three places that must be kept in step:
`coverage.exclude` in `vitest.config.ts`, `omit` in [.coveragerc](.coveragerc),
and the `ignore` list in `codecov.yml`.

**Editing `codecov.yml` does not affect the PR that edits it.** Codecov reads its
configuration from the default branch, so changes take effect only once merged to
`main`. A repo-level YAML in Codecov's web UI merges on top of the file.

One-time setup:

1. Sign in to [codecov.io](https://codecov.io) with GitHub and enable the
   `OwlbearMedia/voteforjulia` repository.
2. Add the repository upload token as a `CODECOV_TOKEN` GitHub Actions secret
   (Settings → Secrets and variables → Actions).

Until the first upload completes, the coverage badge reads `unknown`.

## Project Structure (Relevant)

- src/: Vue application source
- src/components/: Shared Vue components (header, footer, contact form)
- src/components/icons/: Inline SVG icon components (Instagram, Facebook, Envelope, Spinner)
- src/pages/: Page-level Vue components, lazy-loaded by the router
- src/composables/: Reusable Vue composables
- src/lib/: Framework-agnostic utilities (routing, analytics, API client, route paths)
- tests/unit/: Frontend Vitest specs
- api/: Flask API and Python tests
- docs/: Conventions, hosting/deploys, performance budgets, and the donate integration
- scripts/: Build-adjacent Node tooling (source map upload, bundle budget check)
- dist/: Build output generated by pnpm run build
- perf-budgets.json / lighthouserc.cjs: Performance thresholds enforced by CI
- .github/workflows/ci.yml: typecheck, lint, tests, and performance budgets — runs on PRs and pushes to `main`
- .github/workflows/deploy-test.yml: test environment deploy, triggered when CI passes on a PR
- .github/workflows/deploy-production.yml: production deploy, triggered when CI passes on `main`
