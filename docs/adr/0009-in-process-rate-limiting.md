# 0009. Rate-limit in process memory, keyed per IP and endpoint

**Status:** Superseded by [0014](0014-do-not-trust-forwarding-headers.md)
**Date:** 2026-07-31 (recorded; decided at project start)

> The limiter itself — in process memory, per endpoint and per client — still
> stands. What [0014](0014-do-not-trust-forwarding-headers.md) replaces is the
> client-identification rule below: trusting `CF-Connecting-IP` and
> `X-Forwarded-For` unconditionally made the limiter bypassable by anyone who
> sent either header, because nothing sits in front of the API to overwrite
> them. Do not implement the "Two details are deliberate" section as written.

## Context

The API is publicly reachable ([0003](0003-separate-api-subdomain.md)) and every
successful POST does expensive, externally-visible work: two SMTP sends and a
Google Sheets write. Left open, a trivial script could exhaust the mail server's
sending quota, fill the campaign's inbox, and push junk rows into the sheet the
volunteers work from.

The usual answer is a shared store — Redis, or a database table — so limits hold
across processes. The shared host offers neither Redis nor a reason to add one:
there is a single Passenger app, and in practice a single long-lived worker.

There is also no CAPTCHA on the forms. A volunteer sign-up is a conversion that
matters, and a CAPTCHA on it costs real submissions from exactly the people the
campaign wants.

## Decision

A fixed-window limiter in process memory: `_RATE_LIMIT_BUCKETS` in
[api/app.py](../../api/app.py), default 5 requests per 60 seconds, configurable
via `RATE_LIMIT_MAX_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS`. Exceeding it
returns 429 with a `Retry-After` header.

Two details are deliberate:

- **Buckets are keyed `{endpoint}:{client}`**, so the contact form and the
  yard-sign form are limited separately — one does not lock out the other.
- **The client key prefers `CF-Connecting-IP`, falls back to the _last_ hop of
  `X-Forwarded-For`, then `remote_addr`.** The last hop, never the first:
  proxies append the connecting address to whatever the client sent, so the
  first entry is attacker-controlled and would let a caller mint a fresh bucket
  per request.

Every bucket is pruned on each request, not just the current key's, so one-off
addresses cannot leave empty deques behind forever in a process that runs for
weeks.

## Consequences

- **No new infrastructure**, and no dependency that can be down. The limiter
  cannot fail in a way that takes the API with it.
- **Limits are per process and reset on restart** — including on every deploy.
  For casual abuse of a campaign form this is adequate; against a determined
  distributed attacker it is not, and neither would Redis be.
- **The IP key is only as trustworthy as the front end.** The site does not
  currently sit behind Cloudflare, so today the effective key is `remote_addr`;
  `CF-Connecting-IP` is there so that putting Cloudflare in front is a DNS
  change rather than a code change.
- **Shared NAT shares a bucket.** Five submissions a minute from one office or
  campus network is generous enough that this has never mattered.
- **Testing it needs care.** A test asserting "these two requests share a bucket"
  passes even if the header is ignored entirely, because both then fall back to
  the same `remote_addr` — the original version of this test stayed green with
  the whole `X-Forwarded-For` branch deleted. Any keyed-behaviour test needs the
  matching negative case ([../conventions.md](../conventions.md#testing)).

## Alternatives considered

- **Redis or a database-backed limiter.** Correct across processes, and
  unavailable here without adding a service to a shared host to defend two form
  endpoints.
- **`flask-limiter`.** A better implementation of the same idea, but its
  in-memory backend has the same per-process caveat, so the dependency buys
  configuration syntax rather than correctness.
- **CAPTCHA / hCaptcha / Turnstile.** Stronger against automation, at a
  measurable cost in volunteer sign-ups and a third-party script on every form
  page. Reconsider if spam actually arrives; it has not.
- **Nothing at all.** Two exposed endpoints that send mail through the
  campaign's own SMTP account is how a domain ends up on a blocklist.
