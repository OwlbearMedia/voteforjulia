# [voteforjulia.com](https://voteforjulia.com/)

[![CI](https://github.com/OwlbearMedia/voteforjulia/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/OwlbearMedia/voteforjulia/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/OwlbearMedia/voteforjulia/graph/badge.svg)](https://codecov.io/gh/OwlbearMedia/voteforjulia)

![image](https://raw.githubusercontent.com/OwlbearMedia/voteforjulia/refs/heads/main/public/julia-social-banner.avif)

The official campaign website for Julia Hamann, candidate for Mayor of Mankato.

## Tech Stack

- Frontend: Vue 3 + Vite + Vite SSG
- Styling: custom CSS
- Backend API: Flask (Python)
- Monitoring: New Relic Browser Agent + Google Analytics (via `gtag`)
- Frontend tests: Vitest + @vue/test-utils + jsdom
- CI/CD: GitHub Actions + SCP deploy

## Prerequisites

- Node.js 22+
- pnpm 11+
- Python 3.11+ (for API tests)

## Install Dependencies

Install frontend dependencies:

```bash
pnpm install
```

Install Python API dependencies:

```bash
python -m pip install -r api/requirements.txt
```

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

- tests/unit/App.spec.ts
- tests/unit/JuliaHeader.spec.ts
- tests/unit/JuliaFooter.spec.ts
- tests/unit/JuliaContactForm.spec.ts
- tests/unit/pages.spec.ts
- tests/unit/routes.spec.ts
- tests/unit/useContactForm.spec.ts
- tests/unit/analytics.spec.ts
- tests/unit/api.spec.ts
- tests/unit/newrelic.spec.ts

### Python API Tests

Run backend API tests:

```bash
python -m unittest api/test_app.py api/test_models.py api/test_email_service.py
```

## CI and Deployment (GitHub Actions)

This repository uses a trunk-based workflow. All development happens on short-lived
feature branches that are merged directly to `main`. There are two workflow files:

- `.github/workflows/ci.yml`
- `.github/workflows/deploy-test.yml`
- `.github/workflows/deploy-production.yml`

### CI workflow

- Triggers:
  - Pull request events (`opened`, `synchronize`, `reopened`) — runs all jobs including test-environment deploys.
  - Push to `main` — runs test jobs only (no deploys). This keeps the CI badge and Codecov coverage current for the main branch after each merge, and is what triggers the production deploy workflow.
- File: `.github/workflows/ci.yml`
- Jobs:
  - **Typecheck and frontend tests** and **Python API tests** run in parallel:
    - **Typecheck and frontend tests** — type-check, Prettier format check (`pnpm format:check`), ESLint, Vitest with coverage. The frontend coverage totals are posted to the workflow run's job summary, and the full report is uploaded to [Codecov](https://codecov.io/gh/OwlbearMedia/voteforjulia) (baseline visibility only — no enforced threshold yet). The Codecov upload is skipped for Dependabot PRs, which do not have access to repository secrets.
    - **Python API tests** — runs all three test files (`test_app.py`, `test_models.py`, `test_email_service.py`)
The CI badge and Codecov coverage reflect the latest run on `main`.

### Test environment deploy workflow

- Trigger: CI workflow completes successfully on a pull request branch (not main). Dependabot PRs are skipped as they lack deploy secrets.
- File: `.github/workflows/deploy-test.yml`
- Jobs — **Deploy test frontend** and **Deploy test API** run in parallel, both checking out the exact commit CI verified:
  - **Deploy test frontend** — builds with `VITE_API_BASE_URL=https://test-api.voteforjulia.com` and `SOURCEMAP_MODE=true`, injects noindex/nofollow tags, and uploads to `./public_html_test`
  - **Deploy test API** — uploads to `./api_test` and restarts Passenger

The test site always reflects the latest PR that passed CI. Since there is one test environment, concurrent PR deploys are serialized by a concurrency group — the most recently passing PR wins.

### Production deploy workflow

- Trigger: CI workflow completes successfully on `main`. This fires after every merged PR — CI is the single test gate, so tests are not re-run here.
- File: `.github/workflows/deploy-production.yml`
- Jobs — **Deploy frontend** and **Deploy Python API** run in parallel:
  - **Deploy frontend** — checks out the exact commit CI verified, builds with `pnpm run build:deploy` and `VITE_API_BASE_URL=https://api.voteforjulia.com` (builds, uploads source maps to New Relic, then strips them from `dist`), uploads `dist` to a clean `./public_html_next` staging directory, atomically swaps it into the live document root (`mv public_html public_html_prev && mv public_html_next public_html`), then verifies the site is responding.
  - **Deploy Python API** — checks out the same commit, uploads `api` to `./api`, restarts Passenger, then verifies the API is responding.

The frontend swap is atomic: the new build is staged in full before a sub-second
directory rename promotes it, so visitors never see a mix of old and new files, and
files removed in the new build no longer linger. The previous build is retained at
`./public_html_prev` for one-command rollback (`mv public_html public_html_broken && mv public_html_prev public_html`).

If tests fail in either workflow, the job stops before any deployment steps.

### Required GitHub Secrets

- SSH_HOST
- SSH_USERNAME
- SSH_PRIVATE_KEY
- SSH_PASSPHRASE
- SSH_PORT
- NEW_RELIC_API_KEY (New Relic User key, `NRAK-…`, for uploading source maps in the production deploy)
- CODECOV_TOKEN (repository upload token from [codecov.io](https://codecov.io); enables the coverage upload and the README coverage badge)

### Test coverage (Codecov)

The CI workflow runs Vitest with V8 coverage and uploads the `lcov` report to
Codecov. The status and coverage badges at the top of this README reflect the
latest run on `main`.

One-time setup:

1. Sign in to [codecov.io](https://codecov.io) with GitHub and enable the
   `OwlbearMedia/voteforjulia` repository.
2. Add the repository upload token as a `CODECOV_TOKEN` GitHub Actions secret
   (Settings → Secrets and variables → Actions).

Until the first upload completes, the coverage badge reads `unknown`. There is no
enforced coverage threshold yet — coverage is tracked for visibility only.

## Project Structure (Relevant)

- src/: Vue application source
- src/components/: Shared Vue components (header, footer, contact form)
- src/components/icons/: Inline SVG icon components (Instagram, Facebook, Envelope, Spinner)
- src/pages/: Page-level Vue components, lazy-loaded by the router
- src/composables/: Reusable Vue composables
- src/lib/: Framework-agnostic utilities (routing, analytics, API client)
- tests/unit/: Frontend Vitest specs
- api/: Flask API and Python tests
- dist/: Build output generated by pnpm run build
- .github/workflows/ci.yml: pull request validation + test environment deploy
- .github/workflows/deploy-production.yml: production deploy on merged PR to `main`
