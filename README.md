# [voteforjulia.com](https://voteforjulia.com/)

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

- tests/unit/JuliaHeader.spec.ts
- tests/unit/JuliaFooter.spec.ts
- tests/unit/JuliaContactForm.spec.ts
- tests/unit/pages.spec.ts
- tests/unit/routes.spec.ts

### Python API Tests

Run backend API tests:

```bash
python -m unittest api/test_app.py api/test_models.py api/test_email_service.py
```

## CI and Deployment (GitHub Actions)

This repository uses a trunk-based workflow. All development happens on short-lived
feature branches that are merged directly to `main`. There are two workflow files:

- `.github/workflows/ci.yml`
- `.github/workflows/deploy-scp.yml`

### CI workflow (pull requests → main)

- Trigger: pull request events (`opened`, `synchronize`, `reopened`)
- File: `.github/workflows/ci.yml`
- Jobs (run in sequence):
  1. **Typecheck and tests** — frontend type-check, Prettier format check (`pnpm format:check`), Vitest with coverage, and Python API tests. The frontend coverage totals are posted to the workflow run's job summary (baseline visibility only — no enforced threshold yet).
  2. **Deploy test frontend** — builds with `VITE_API_BASE_URL=https://test-api.voteforjulia.com` and `SOURCEMAP_MODE=true`, injects noindex tags, and uploads to `./public_html_test`
  3. **Deploy test API** — runs Python tests and uploads to `./api_test`, restarts Passenger

The test site always reflects the current open PR. Deploy jobs only run if tests pass.

### Production deploy workflow

- Trigger: merged pull request into `main`
- File: `.github/workflows/deploy-scp.yml`
- Key steps:
  1.  Install dependencies
  2.  Run frontend and Python tests
  3.  Build site with `pnpm run build:deploy` and `VITE_API_BASE_URL=https://api.voteforjulia.com` (builds, uploads source maps to New Relic, then strips them from `dist`)
  4.  Upload `dist` to a clean `./public_html_next` staging directory, then atomically swap it into the live document root (`mv public_html public_html_prev && mv public_html_next public_html`)
  5.  Upload `api` to `./api`
  6.  Restart Passenger app

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

## Project Structure (Relevant)

- src/: Vue application source
- tests/unit/: Frontend Vitest specs
- api/: Flask API and Python tests
- dist/: Build output generated by pnpm run build
- .github/workflows/ci.yml: pull request validation + test environment deploy
- .github/workflows/deploy-scp.yml: production deploy on merged PR to `main`
