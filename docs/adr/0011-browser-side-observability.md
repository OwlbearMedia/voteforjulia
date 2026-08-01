# 0011. Observe the site from the browser, not the server

**Status:** Superseded by [0013](0013-server-side-apm.md)
**Date:** 2026-07-31 (recorded; decided at project start)

> The browser-side half of this decision still stands and is still in force —
> New Relic Browser, GA4, hidden source maps, and the PII redaction rules are
> unchanged. What [0013](0013-server-side-apm.md) reverses is the "and nothing on
> the server" half, after the outage this record's own consequences predicted.

## Context

Shared hosting gives no observability worth the name
([0001](0001-shared-hosting-over-aws.md)): there is no metrics endpoint, no log
aggregation, no alerting, and access to the Passenger log means an SSH session.
Installing a server-side APM agent into a cPanel virtualenv is possible but adds
weight to a single worker and gives visibility into two endpoints that mostly do
network I/O.

Meanwhile the interesting failures on a campaign site are all client-side. A
prerendered page cannot 500 — it is a file. What actually goes wrong is a broken
donation widget, a JavaScript error on a phone, a form that fails silently, or a
page that takes six seconds on a rural connection. None of that is visible from
the server, because none of it produces a request.

The campaign separately needs traffic numbers — which pages get read, where
visitors come from, whether the yard-sign push worked.

## Decision

Two browser-side tools, and nothing on the server beyond `logger` output:

- **New Relic Browser** for JavaScript errors, Core Web Vitals, and AJAX
  timings. Loaded lazily after `DOMContentLoaded`
  ([src/lib/newrelic.ts](../../src/lib/newrelic.ts)) so it stays off the
  critical render path, and bundled rather than injected via a `<script>` tag,
  which is what lets `script-src` avoid `'unsafe-inline'`.
- **Google Analytics 4** via `vue-gtag`, in its own chunk, for traffic and a
  handful of deliberate events (donate clicks, form outcomes, footer links).

Production builds emit hidden source maps, upload them to New Relic, then strip
them from `dist` — so stack traces are symbolicated in the dashboard while no
map is ever served publicly. The test deploy keeps linked maps for in-browser
debugging.

**PII is redacted before it leaves the browser.** `redactPii` in
[src/lib/analytics.ts](../../src/lib/analytics.ts) replaces every form value
with `[redacted]` except an explicit allowlist of non-identifying
multiple-choice fields, keeping empty values empty so a missing field stays
distinguishable from a redacted one. The API applies the same rule from the
other side, logging field names only ([0004](0004-no-database.md)).

## Consequences

- **Real-user monitoring for free**, including devices and networks that will
  never be reproduced locally.
- **Symbolicated production stack traces without shipping source maps.**
- **Source map upload is best-effort.** Failures are logged as `::warning::` and
  never fail the build — observability is not a deploy requirement.
- **Server-side visibility is thin.** When a form breaks, the sequence is: see
  it in New Relic or in a supporter's complaint, then SSH in and read the
  Passenger log. There is no alert. This is the accepted cost, and the mitigation
  is that failures dump the raw request body so submissions can be recovered.
- **`/health` is a liveness check and nothing more.** It deliberately does not
  exercise SMTP or Sheets, so it can be green while every form on the site
  fails — which is exactly what happened during the `$`-in-password incident
  ([../hosting.md](../hosting.md#app-env-vars-must-not-contain-)). Knowing what
  it does not cover is part of using it.
- **Two third-party origins on every page**, each needing `script-src` and
  `connect-src` entries, plus `worker-src blob:` for New Relic's workers.
- **New Relic's licence and application IDs are in client code.** They are
  public by design; the agent runs in the browser.

## Alternatives considered

- **A server-side APM agent in the Passenger app.** Real backend traces, at the
  cost of memory in a single shared-host worker, to observe two endpoints whose
  failures are already logged and whose latency is dominated by SMTP.
- **Log files only.** Free, and the honest baseline. Rejected because it makes
  client-side errors — the majority of what breaks — completely invisible.
- **Sentry instead of New Relic.** A strong fit for error tracking. New Relic
  was already in use and covers Core Web Vitals in the same agent.
- **A privacy-first analytics tool (Plausible, Fathom).** Lighter, no cookie
  banner question, and nicer to visitors. GA4 won on cost (free) and on the
  campaign's familiarity with it; the redaction rules exist to limit what either
  tool ever receives.
