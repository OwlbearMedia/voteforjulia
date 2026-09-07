# 0014. Trust a forwarding header only when one is configured

**Status:** Accepted
**Date:** 2026-08-01

Supersedes [0009](0009-in-process-rate-limiting.md).

## Context

[0009](0009-in-process-rate-limiting.md) chose an in-process rate limiter keyed
per client and per endpoint, and recorded two deliberate details about how the
client is identified: prefer `CF-Connecting-IP`, because "Cloudflare overwrites
it on proxied requests, so the client can't forge it"; fall back to the **last**
hop of `X-Forwarded-For`, because "proxies append the connecting address to
whatever list the client sent, so the first entry is attacker-controlled".

Both statements are true. Both are also conditional on a proxy actually sitting
between the caller and the app — and the same ADR records that none does: "The
site does not currently sit behind Cloudflare, so today the effective key is
`remote_addr`; `CF-Connecting-IP` is there so that putting Cloudflare in front
is a DNS change rather than a code change."

That last sentence describes the intent. It was not what the code did. With
nothing in front of the API ([0003](0003-separate-api-subdomain.md)), both
headers were accepted from anyone who sent them, so a caller could vary either
one and mint a fresh bucket per request. Measured against the shipped limit of
five per sixty seconds:

```
baseline (no headers)        12 requests ->  7 blocked
forged CF-Connecting-IP      12 requests ->  0 blocked
forged X-Forwarded-For       12 requests ->  0 blocked
forged XFF, multi-hop        12 requests ->  0 blocked
```

The limiter was off for anyone who sent one header, which means every outcome
0009 lists as the reason to have one — the mail server's sending quota, the
campaign's inbox, junk rows in the volunteers' sheet — was unprotected.

The test suite did not catch it. It asserted the _precedence_ rules (first hop
ignored, `CF-Connecting-IP` winning over `X-Forwarded-For`), and both tests were
correct given a trusted proxy. Neither asked whether the header should be
believed at all. 0009's own closing note warned that keyed-behaviour tests need
their negative case; the gap was one level above where it was looking.

Two consequences of the forgeable key made it worse. The bucket dictionary was
swept in full on every request, so per-request cost scaled with the number of
live keys — and the attacker controlled that number as well as the request rate
(0.23ms at 1,000 buckets, 3.06ms at 20,000). And the rate-limit settings were
parsed with a bare `int()` at import, so a typo in cPanel failed module import
and took every form on the site down rather than falling back.

## Decision

**No forwarding header is trusted unless `TRUSTED_CLIENT_IP_HEADER` names one.**
Unset by default, so the key is `request.remote_addr` — the only value in the
request the caller cannot choose. When it does name a header, that header's last
hop is used, and no other header is consulted.

This keeps 0009's stated goal intact: putting Cloudflare in front remains a
configuration change (set the variable to `CF-Connecting-IP`), not a code
change. It just stops the app from pretending the proxy is already there.

Four supporting changes, all in [api/app.py](../../api/app.py):

- **The full bucket sweep runs at most once per window**, not per request, with
  each key pruned inline so its own count stays exact. Memory is bounded the
  same way — nothing survives more than a window past expiry — at O(1)
  amortised instead of O(live keys).
- **`RATE_LIMIT_MAX_BUCKETS` caps how many keys are tracked** (10,000 default),
  evicting least-recently-active keys down to a low-water mark when crossed.
  Renamed `RATE_LIMIT_MAX_TRACKED_KEYS` by
  [0024](0024-count-every-rate-limit-tier-in-sqlite.md), which left the cap and
  the low-water mark alone and changed what is being counted.
- **`Retry-After` rounds up.** Truncating it advertised a wait still inside the
  window, so a client that honoured the header exactly earned a second 429 for
  doing the right thing.
- **Limit settings fall back to their defaults and log** instead of raising, so
  a mistyped value degrades the limiter rather than failing module import.

## Consequences

- **The rate limiter now does what 0009 says it does.** Everything else in 0009
  still holds: in process memory, per endpoint and per client, no new
  infrastructure, per-worker limits that reset on deploy. _Two of those stopped
  being true later — the sustained tier moved to SQLite in
  [0016](0016-second-tier-rate-limiting-and-honeypot.md) and the burst tier
  followed it in [0024](0024-count-every-rate-limit-tier-in-sqlite.md), which is
  what makes the limits shared and durable rather than per-worker._
- **Shared NAT now genuinely shares a bucket.** 0009 listed this as a
  consequence, but it was not actually reachable while any caller could opt out
  by sending a header. Five submissions a minute from one office or campus
  network is still generous; this is the first point at which it is real.
- **Turning on Cloudflare needs the variable set, or every visitor collapses
  into one bucket** — the proxy's address becomes the socket address. That
  failure is loud and immediate rather than silent, which is the right way
  round, but it is a step that cannot be skipped.
- **Eviction fails open.** Dropping a bucket resets that client's allowance, so
  under genuine key pressure the limiter gets more permissive rather than
  refusing real submissions or growing until the worker is killed. For a
  campaign form that is the correct trade; it is also now much harder to reach,
  because the key space is no longer caller-controlled.
- **Sweeping on a schedule means expired buckets can linger up to a window past
  expiry.** Memory is bounded by roughly two windows of keys rather than one.

## Alternatives considered

- **Werkzeug's `ProxyFix`.** The standard answer, and it encodes the same
  insight: you must declare how many proxies to trust. Rejected only because it
  rewrites `remote_addr` for the whole request — including the access log and
  anything else that reads it — to solve a problem that exists in one function
  here. Worth revisiting if anything else starts needing the client address.
- **Verifying the peer against Cloudflare's published IP ranges.** Correct, and
  self-maintaining in the sense that a forged header from a non-Cloudflare peer
  is rejected outright. It needs the range list fetched and kept current, which
  is a scheduled job and a failure mode, to protect two form endpoints behind a
  proxy that is not deployed yet.
- **Keeping the headers and accepting the bypass.** Defensible only if the
  limiter is decorative. 0009 argued convincingly that it is not.
