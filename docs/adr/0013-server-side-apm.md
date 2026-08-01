# 0013. Instrument the API server-side, and alert on it

**Status:** Accepted
**Date:** 2026-07-31

Supersedes [0011](0011-browser-side-observability.md).

## Context

[0011](0011-browser-side-observability.md) chose browser-only observability and
listed a server-side APM agent among the alternatives it rejected: real backend
traces were not worth agent memory in a single shared-host worker, to watch two
endpoints that "mostly do network I/O" and whose failures are already logged.

The reasoning held on its own terms. What it under-weighted was that **nothing
was watching**. 0011 recorded this honestly in its own consequences — "there is
no alert", and `/health` "can be green while every form on the site fails" — and
then that exact scenario happened. On 2026-07-30 a rotated `EMAIL_PASSWORD`
containing a `$` reached the app truncated ([../hosting.md](../hosting.md#app-env-vars-must-not-contain-)).
Every submission failed with `SMTPAuthenticationError`. `/health` stayed green,
because it does not exercise SMTP. No browser error fired, because the API
returned a well-formed 502. The outage ended when a human noticed.

The account state confirmed the gap: zero synthetic monitors, and a single empty
default alert policy. The site had telemetry and no supervision.

The specific failure mode of a campaign site sharpens this. Traffic is spiky and
deadline-bound — a yard-sign push, a debate, the days before an election. A
silent form outage during one of those windows loses volunteers who do not come
back, and there is no second chance at the date.

## Decision

Run the New Relic Python agent in the Passenger app, add a health check that
exercises the dependencies, and alert on both.

- **The agent** is initialised in
  [api/passenger_wsgi.py](../../api/passenger_wsgi.py) before app.py is imported,
  because it instruments Flask, `smtplib` and `googleapiclient` through import
  hooks. Configuration is environment-only (`NEW_RELIC_LICENSE_KEY`,
  `NEW_RELIC_APP_NAME`), set per app in cPanel — there is no `newrelic.ini` and
  no key in the repo.
- **The bootstrap swallows every exception.** A missing package, a rejected key
  or an unwritable log path degrades to an un-instrumented app rather than a
  failed boot. This module is the entry point for the whole API; monitoring may
  never be the thing that takes the forms down.
- **`/health/deep`** authenticates against SMTP (connect, `LOGIN`, no mail sent)
  and reads spreadsheet metadata, returning 503 if either fails. It is rate
  limited under its own scope, and reports `fail` rather than exception text,
  which quotes credentials.
- **`/health` is untouched.** Both deploy pipelines verify against it, and a
  mail-server blip must not fail a deploy.
- **Browser and API traces are joined.** The API allows the `newrelic`,
  `traceparent` and `tracestate` headers through CORS, and the browser agent
  lists both API origins in `distributed_tracing.allowed_origins`. Neither half
  works alone.
- **A synthetic monitor watches `/health/deep`** from outside, with alerts on
  synthetic failure and on APM error rate.

## Consequences

- **Silent dependency failures now page instead of waiting to be noticed.** This
  is the whole point; the 2026-07-30 outage would have alerted in minutes.
- **Agent memory now sits in every Passenger worker** — roughly 35–60MB RSS.
  This is the cost 0011 declined to pay, and it is real on a shared host under a
  CloudLinux LVE cap. Deploy to `api_test` and measure with
  `ps -o rss,cmd -C lswsgi` before production. If workers approach the cap, this
  decision is the one to revisit.
- **The deploy path gains a compiled dependency.** `newrelic` ships `cp311`
  manylinux wheels so the host installs a wheel, but the cPanel venv has no
  toolchain — a future version without a matching wheel breaks deploys, so check
  before bumping.
- **`/health/deep` is unauthenticated and does real network I/O**, so it is rate
  limited and returns no diagnostic detail. Anyone can learn whether the mail
  server is up; nobody can learn why not.
- **An SMTP `LOGIN` runs on every probe.** Cheap, but not free — a mail host that
  throttles authentication attempts would need the monitor interval widened.
- **The browser agent's `allowed_origins` is now coupled to the API's CORS
  header.** Changing one without the other silently unlinks traces: nothing
  fails, the correlation just stops.

## Alternatives considered

- **Synthetics and alerting only, no agent.** Would have caught the 2026-07-30
  outage at zero memory cost, and keeps 0011 intact. Rejected because it detects
  that something broke without saying where — no latency breakdown across SMTP
  and Sheets, no server-side stack traces, and no way to tell a slow dependency
  from a slow handler.
- **Extending `/health` rather than adding `/health/deep`.** One endpoint is
  simpler, but both deploy workflows curl `/health` as their verify step, so a
  transient mail failure would start failing deploys.
- **Log forwarding instead of an agent.** Lighter, and Passenger already writes
  logs. Rejected because it inherits the log's blind spots: a request that never
  errors — the truncated-password 502s were logged as ordinary failures — reads
  as normal.
- **Keeping 0011 and accepting manual detection.** Defensible for a site with no
  deadline. Not for one where the failure window and the election calendar
  overlap.
