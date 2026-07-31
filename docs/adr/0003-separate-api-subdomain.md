# 0003. Run the API on its own subdomain, cross-origin

**Status:** Accepted
**Date:** 2026-07-31 (recorded; decided at project start)

## Context

The frontend is static files in a document root; the API is a Passenger app.
Both live on the same host, so they could share an origin — cPanel can mount a
Python app under a path like `voteforjulia.com/api`, and `.htaccess` could
proxy. Sharing an origin would remove CORS from the picture entirely.

Against that:

- **Path-mounted Passenger apps are fiddly under cPanel**, and the mount point
  is host configuration, not repo configuration. A same-origin `/api` prefix
  would work until someone re-created the app in the cPanel UI.
- **A path mount blurs the deploy boundary.** The frontend deploy replaces the
  entire document root by renaming a directory
  ([0006](0006-scp-deploy-with-atomic-swap.md)). An API mounted inside that root
  would be replaced along with it, or would have to be carefully excluded.
- **The two halves have genuinely different lifecycles** — different test
  suites, different runtimes, different deploy chains that run in parallel.
- **The test environment needs the same split**, and doing it with subdomains
  gives four independent cPanel apps with four independent sets of environment
  variables.

## Decision

Four hostnames, four cPanel apps:

|            | Frontend                | API                         |
| ---------- | ----------------------- | --------------------------- |
| Production | `voteforjulia.com`      | `api.voteforjulia.com`      |
| Test       | `test.voteforjulia.com` | `test-api.voteforjulia.com` |

The frontend learns its API base URL at build time from `VITE_API_BASE_URL`,
defaulting to production in [src/lib/api.ts](../../src/lib/api.ts). The API
allowlists the four origins plus `http://localhost:5173` in `add_cors_headers`
([api/app.py](../../api/app.py)).

## Consequences

- **Every form post is a cross-origin request**, so CORS is a permanent part of
  the API's contract rather than an afterthought. `Vary: Origin` is set on
  _every_ response, not just allowed ones — otherwise a shared cache could serve
  a disallowed origin's header-less response to an allowed origin. Both
  endpoints answer `OPTIONS` with a 204.
- **A new deploy target means a new allowlist entry.** Forgetting one produces a
  browser-only failure that no server-side test catches; the origin list is a
  deploy-time concern, overridable via `CORS_ALLOWED_ORIGINS`.
- **`connect-src` in the CSP must name both API origins** — the production page
  can only reach the production API, and that is enforced by the browser.
- **The two halves can be deployed, restarted, and rolled back independently**,
  which the workflows take advantage of: the frontend and API chains run in
  parallel and a failed API verify does not touch the deployed site.
- **The API is directly reachable**, not hidden behind the site's origin. It is
  a public endpoint that anyone can post to, which is why rate limiting
  ([0009](0009-in-process-rate-limiting.md)) is not optional.

## Alternatives considered

- **Same-origin `/api` path mount.** Would eliminate CORS and the allowlist.
  Rejected because the mount is host UI state rather than repo state, and
  because it entangles the API with the frontend's whole-directory swap.
- **A rewrite proxy in `.htaccess` from `/api` to the Passenger app.** Same
  benefit, plus a second copy of the routing rules to keep correct in a file
  whose parser has already surprised us
  ([../hosting.md](../hosting.md#the-web-server-is-litespeed-not-apache)).
- **One shared API for both environments.** Half the apps to manage. Rejected
  outright: the e2e suite submits real forms, so the test environment must write
  to a test worksheet and mailbox, and that separation is enforced by having
  separate env vars on separate apps.
