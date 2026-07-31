# 0010. Keep security, caching, and URL policy in `.htaccess`

**Status:** Accepted
**Date:** 2026-07-31 (recorded; decided at project start)

## Context

The frontend is static files with no server-side code
([0002](0002-static-site-generation.md)), so there is no application layer that
could set a response header. There is also no CDN or reverse proxy in front of
the site to do it. What remains is the web server's own configuration, which on
shared hosting means [public/.htaccess](../../public/.htaccess).

Three separate concerns need to live somewhere:

- **Security headers** — CSP, Permissions-Policy, HSTS, frame options. The CSP
  matters more than usual because the donation flow pulls Donorbox, Stripe,
  FingerprintJS and jspm into _our_ document rather than an iframe
  ([0005](0005-outsource-donations.md)).
- **Caching** — the build emits content-hashed assets that should be cached
  forever and HTML that must never be, or a deploy would not be visible.
- **Clean URLs** — SSG emits flat `.html` files, but the canonical URLs, the
  sitemap, and every link are extensionless.

## Decision

All three live in `.htaccess`, which is copied verbatim into `dist/` and
uploaded as its own scp step. It is the single source of edge policy, and it is
version-controlled alongside the code it protects.

Caching is opt-in rather than blanket: a rewrite rule tags only genuinely
fingerprinted asset paths with `IS_VITE_ASSET`, and `immutable` caching applies
to that flag alone. HTML is `no-cache, must-revalidate`. `FileETag MTime Size`
keeps validators stable across deploys.

## Consequences

- **Policy is reviewable in a PR** and deploys atomically with the build that
  depends on it — a CSP change and the code that needs it land together.
- **Header changes cannot be signed off locally.** LiteSpeed's config parser is
  not Apache's and the differences are silent: `Header set X "a \"b\""` emits
  literal backslashes, which fails the structured-header parser and drops the
  entry. **Never use backslash escapes here**; delimit with single quotes. The
  only valid verification is `curl -sI` against the deployed test site.
- **The CSP is long and load-bearing.** Each third-party origin in it has a
  reason recorded in a comment, because a plausible-looking cleanup can silently
  disable express checkout on the donation page. `jspm.dev` cannot be
  path-scoped; `cdn.jsdelivr.net` is scoped to the FingerprintJS package so the
  entry cannot be used to load arbitrary npm packages.
- **`style-src` needs `'unsafe-inline'`**, because the build inlines all CSS into
  `<style>` blocks for first-paint performance. Accepted knowingly: CSS injection
  is a much smaller risk than script injection, and `script-src` carries no
  `'unsafe-inline'` at all.
- **Losing the file loses every protection at once**, silently — the site still
  serves. That is why it gets its own explicit upload step rather than relying on
  a glob that does not match dotfiles.
- **Cache correctness depends on the hash pattern matching Vite's output.** If
  Vite ever changed its filename format, the rule would stop matching and assets
  would quietly fall back to short-lived caching — a performance regression, not
  a correctness one, which is the right way round.

## Alternatives considered

- **Cloudflare (free tier) in front, with headers configured there.** A better
  place for edge policy, and it would also make the rate limiter's
  `CF-Connecting-IP` key real ([0009](0009-in-process-rate-limiting.md)). Not
  adopted yet — it adds a vendor and a second place to look when a header is
  wrong. The code is already written to accommodate it.
- **Headers from the Flask app.** Only covers API responses; the pages that need
  a CSP are static files the app never sees.
- **Meta-tag CSP in the HTML.** Would survive without `.htaccess`, but cannot
  express `frame-ancestors`, and would have to be injected into every prerendered
  page. Worse in every dimension except robustness to a missing file.
