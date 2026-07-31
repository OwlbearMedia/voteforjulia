# 0007. One shared test environment, deployed by whichever PR last passed CI

**Status:** Accepted
**Date:** 2026-07-31 (recorded; decided at project start)

## Context

Some things about this site can only be verified on the host. LiteSpeed's
`.htaccess` parser is not Apache's, and the differences are silent — a
mis-parsed directive yields a malformed header rather than an error, so a local
Apache run confirms the _intended_ value and nothing about the served one. The
same goes for the cPanel virtualenv, Passenger's environment, and the CSP that
the Donorbox widget depends on.

So a real, host-based pre-production environment is not optional. The question
was how many.

Per-PR ephemeral environments are the modern answer, but on a shared cPanel host
each environment is a hand-created app: a subdomain, a document root, a
CloudLinux virtualenv, and a set of environment variables entered in a web UI.
None of it is scriptable from CI in any way worth maintaining. And the repo has
one developer, so the number of PRs in flight at once is usually one.

## Decision

One test environment — `test.voteforjulia.com` and `test-api.voteforjulia.com`,
backed by `./public_html_test` and `./api_test` — redeployed whenever CI passes
on a PR branch. It always reflects the most recently passing PR; concurrent
deploys are serialized by a GitHub Actions concurrency group.

A `gate` job refuses to deploy when the run is stale (the commit is no longer
branch HEAD), the PR has been closed, the branch is Dependabot's, or the PR
comes from an external fork. The Cypress e2e suite then runs against the
deployed site.

## Consequences

- **Header, CSP, and hosting changes get verified against LiteSpeed before they
  reach production**, which is the entire justification for the environment. The
  loop is: edit `.htaccess`, open a PR, `curl -sI` the test site, then merge.
- **The e2e suite tests something real** — a deployed static site talking to a
  deployed API, submitting genuine form data that lands in a test worksheet and
  is then deleted.
- **Two PRs in flight will fight over it.** The later one wins and the earlier
  one's test site silently becomes someone else's build. With one developer this
  is a non-issue; with two it would be the first thing to hurt, and the fix
  would be a second environment rather than a smarter gate.
- **The test environment must never be indexed.** The deploy overwrites
  `robots.txt` and injects `noindex`/`nofollow` — a duplicate of the whole
  campaign site in search results would be actively harmful.
- **It is not a perfect mirror.** It builds with linked source maps and keeps
  them on the server, and it points at a different API and different sheets. It
  is the same host and the same web server, which is what matters.
- **It shares a machine with production.** A pathological test run competes for
  the same CPU and the same mail server; the rate limiter applies to both.

## Alternatives considered

- **Per-PR ephemeral environments.** The right answer on infrastructure that can
  create environments programmatically. On cPanel each one is manual clicking,
  and the host has finite subdomains and disk.
- **No test environment; verify in production after merge.** Tempting for a site
  this small, and rejected on exactly one case: `/donate` is the page that takes
  money, and its CSP and Permissions-Policy entries are precisely the things
  that cannot be verified anywhere else. Breaking it in production to find out is
  too expensive.
- **A local Apache container as the pre-production check.** Kept as a syntax
  check, but it cannot answer the question that matters, because it is not
  LiteSpeed. See
  [../hosting.md](../hosting.md#the-web-server-is-litespeed-not-apache).
