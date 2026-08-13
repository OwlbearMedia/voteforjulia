# 0017. Refuse cross-site submissions, and cache the deep health probe

**Status:** Accepted
**Date:** 2026-08-12

Amends [0009](0009-in-process-rate-limiting.md) and
[0016](0016-second-tier-rate-limiting-and-honeypot.md). Both remain in force:
this record does not change how a client is identified or counted, it adds a
control for the case where counting per client is the wrong unit entirely.

## Context

Both findings below came out of an adversarial review of the repo and the live
site on 2026-08-12, and both are properties of endpoints that were working as
designed.

### CORS never protected the form endpoints

[0003](0003-separate-api-subdomain.md) put the API on its own subdomain, which
made every submission cross-origin and made an explicit allowlist necessary.
That allowlist is real and correct, and it was quietly load-bearing in a way it
cannot support: **CORS governs who may read a response, not who may send a
request.**

A POST with `Content-Type: application/x-www-form-urlencoded` is a CORS _simple
request_. The browser sends it with no preflight, so nothing consults the
allowlist before the submission arrives, is validated, and produces two emails
and a sheet row. Confirmed against production during the review:

```
POST https://api.voteforjulia.com/send-email
Origin: https://evil.example
Content-Type: application/x-www-form-urlencoded
→ 400 {"error":"First name and email are required."}
```

The 400 is a validation error. The request was accepted, parsed and answered on
its merits; only a deliberately empty payload kept it from sending mail.

So any page on the internet can auto-submit these forms from its visitors'
browsers. The consequence that matters is what it does to the controls 0009 and
0016 built:

- **Per-IP rate limiting counts one request per victim.** Both tiers key on the
  client address. A page with 200 visitors produces 200 addresses, each one
  submission below every limit. The limiter cannot see the attack because from
  its point of view there is no repeat caller.
- **The honeypot is published.** `referralCode` is in the HTML of every page
  that renders a form and in a public repo. It stops software that fills every
  input it finds; it does not stop anyone who looked.

0016 already recorded the shape of the loss: each accepted submission is a
notification email, **a confirmation email to whatever address the submitter
supplied**, and a row in the sheet volunteers work from. Domain reputation is
the real exposure, and a campaign that cannot send email cannot organise.

### `/health/deep` is an unauthenticated amplifier

One GET runs a real SMTP `LOGIN` against the campaign's mail account and a
Google Sheets metadata read. 0016 gave the endpoint its own hourly allowance
(30/hour) so a monitor would not be treated as a spammer — which bounds how
often _one_ address may ask, and says nothing about what the answer costs.

Spread across addresses, that is one cheap request buying two expensive ones
against the two dependencies every form on the site needs. The plausible
outcome is not this endpoint failing; it is the mail host throttling or blocking
the account, which takes down sending. The repeated authentication failures such
an attack produces are exactly the pattern mail providers act on.

## Decision

**1. Refuse a POST whose `Origin` is present and not on the allowlist**, with
`403`, before the rate limiter and before any I/O. `ORIGIN_ENFORCED=false`
disables enforcement while still logging.

Three properties make this the right shape:

- **Browsers always send it.** `Origin` is on every browser POST, including the
  no-JS `<form action>` navigation the site falls back to. `voteforjulia.com`
  posting to `api.voteforjulia.com` is same-site, so a legitimate submission
  always carries an origin already on the allowlist. Nothing about the
  progressive-enhancement path changes.
- **Absent is allowed, deliberately.** curl, a monitor and anything server-side
  send no `Origin`. Those are precisely the callers per-IP limiting _does_
  bound, so refusing them would trade a control that works for one that breaks
  every scripted client. This closes the distributed-browser vector and only
  that one.
- **Ahead of the limiter.** A cross-site flood arrives on its victims'
  addresses. Charging it to their buckets would spend the allowance of the
  people whose browsers were conscripted, so a supporter who then submitted the
  form themselves would be refused by a limit they never approached. The check
  is a header read and a set lookup — cheaper than the bucket it would consume.

It reuses the honeypot's response message. Neither control can be corrected by
editing the form, so the only useful advice is the same in both cases, and a
shared message does not tell a caller which one fired. The status differs
(`403`, not `400`) because the body was never the problem.

Unlike the honeypot, a rejection does **not** log the request body. Nothing
rate-limits this path — that is the whole point of running it first — so a body
dump per request would be a way to fill the disk. The origin alone is logged,
truncated, and that is what makes the kill switch usable as evidence.

**2. Cache the `/health/deep` result for 60 seconds**
(`HEALTH_DEEP_CACHE_SECONDS`), successes and failures alike, and report `Age`.

The ceiling stops scaling with the caller's address count and starts scaling
with our own worker count: at most one probe per worker per TTL, however many
addresses ask. 60 seconds sits well under the monitor's 15-minute period, so
every scheduled poll still does real work and the cache only ever collapses a
flood.

Failures are cached too. Caching only successes would restore the full amplifier
at exactly the moment a dependency is already in trouble, which is when
hammering it is least affordable.

## Consequences

- **A stale window exists, and is the price.** For up to one TTL, `/health/deep`
  can report a dependency as healthy after it has broken. Against a 15-minute
  poll a 60-second window cannot hide an outage from even one poll, and `Age`
  makes any answer's freshness checkable. The expiry test in
  [../../api/test_app.py](../../api/test_app.py) asserts both halves — that the
  stale window exists, and that it ends.
- **The cache is per worker, not global.** Passenger reaps idle workers
  ([../hosting.md](../hosting.md#watch-worker-memory)), so there is nothing
  longer-lived to hold it in, exactly as with the burst rate-limit tier. The
  bound is worker count × TTL rather than one probe per TTL. That is enough:
  the property being bought is that the ceiling no longer depends on the
  attacker.
- **A browser that suppresses `Origin` would be refused.** No mainstream browser
  does on POST, and the kill switch is a cPanel restart rather than a release —
  the same bargain `HONEYPOT_ENFORCED` makes, and for the same reason: the cost
  of a false positive is a supporter who wanted to help and could not.
- **This does not stop a scripted attacker.** A client that sends no `Origin` is
  unaffected, which includes the 2026-08-10 caller. That attack is the rate
  limiter's job and 0016 is still what answers it. Adding a control that
  addresses a different case is the point; conflating the two would be the
  mistake.
- **The CORS allowlist now has two jobs.** It decides who may read a response
  _and_, via the same set, who may send a submission. Adding an origin to
  `CORS_ALLOWED_ORIGINS` now grants both. That is the intended reading — the
  origins the campaign controls are the ones that may submit — but it is worth
  knowing before the set is next edited.

## Alternatives considered

- **Reject form-encoded bodies and require `application/json`.** This is the
  textbook fix: a JSON content type is not a simple request, so it forces a
  preflight and CORS becomes the control it appeared to be. It would break the
  no-JS submission path, which posts form-encoded by construction. That path is
  a deliberate accessibility property of the site, not a legacy accident, and
  trading it for a boundary `Origin` already provides is a bad trade.
- **`Sec-Fetch-Site: cross-site`.** Equivalent coverage on browsers that send
  it, but it is a second source of truth that can disagree with `Origin`, and
  the fallback when it is absent has to be an `Origin` check anyway. One
  discriminator is easier to reason about than two.
- **A shared secret header on `/health/deep`.** Bounds the amplifier completely
  rather than by a factor. Rejected because the monitor definitions in
  [../../monitoring/](../../monitoring/) drift silently against the live
  account — nothing syncs them — so the secret would live in a place where a
  mismatch surfaces as a 3am page. The cache needs no coordination with anything
  outside the app.
- **CAPTCHA / Turnstile.** Declined by 0009 on conversion grounds and by 0016
  again. Still declined, and now on stronger evidence: the gap was never that
  submissions lacked a proof of humanity, it was that a request from a page the
  campaign does not control was indistinguishable from one that came from its
  own form. That is answered by a header the browser already sends, at no cost
  to a supporter.
