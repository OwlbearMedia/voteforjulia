# 0024. Count every rate-limit tier in SQLite, and keep only refusals in memory

**Status:** Accepted
**Date:** 2026-08-26

Supersedes the storage half of [0009](0009-in-process-rate-limiting.md) and
amends [0016](0016-second-tier-rate-limiting-and-honeypot.md). What 0009 decided
about _identifying_ a client is unchanged and still governed by
[0014](0014-do-not-trust-forwarding-headers.md); what 0016 decided about the
hour-long tier, the honeypot and failing open is unchanged. What changes is the
one thing both records left in process memory: the burst window.

## Context

The burst tier is documented everywhere as 5 requests per 60 seconds. It has
never held that limit in production.

`_RATE_LIMIT_BUCKETS` was a module-level dict in [../../api/app.py](../../api/app.py),
so every Passenger worker counted on its own and a burst spread across N live
workers was allowed roughly `5 x N` requests before anything was refused.
Measured against production on 2026-08-20
([#158](https://github.com/OwlbearMedia/voteforjulia/issues/158)):

| Observation                                         | Under a shared 5/60s counter |
| --------------------------------------------------- | ---------------------------- |
| Seven rapid requests to `/health/deep` → seven 200s | the sixth must be refused    |
| First refusal at roughly the fifteenth request      | consistent with ~3 workers   |

That issue rules out the three alternative explanations — the variable is unset
in production so the default of 5 applies, `cf-cache-status: DYNAMIC` says every
request reached the origin, and `/health` echoed the caller's own address, so
all seven shared one bucket key.

**0016 caught the premise and drew too narrow a conclusion from it.** It already
knew Passenger reaps workers here, and answered:

> A 60-second window survives that, because repeat traffic inside a minute tends
> to reach a warm worker.

That is a claim about one caller sequentially finding their own bucket again,
and it is true. It says nothing about workers alive _concurrently_, each holding
an independent count. The window survived; the limit did not.

Two things make this worth fixing now rather than documenting as-is.

**The cost argument for keeping it in memory does not survive being checked.**
0016 put the cheap in-memory check in front so a burst is short-circuited
"before anything touches the disk". But the hourly tier is consulted on every
request the burst tier _allows_, and it writes a row for each one. Every allowed
request already paid for a connection, a transaction and an insert. The
in-memory tier was only ever saving disk on the refusal path.

**And what it saved was paid for in the defect.** The old tier did shield the
disk: each worker allowed five, and every request that worker took after that
was refused before the hourly tier's insert. But it could only do that by being
a counter, and a counter in process memory is the whole reason the limit was
`5 x N` rather than 5. The shielding and the defect were the same mechanism, so
the question is not whether to keep the shield — it is whether the shield has to
be a counter. It does not: a cache of the refusals the shared tiers issue shields
the same path without holding a limit of its own.

An earlier draft of this record argued the shield never worked at all, on the
reasoning that only five requests are ever allowed so no worker reaches its own
count. That describes the system this record _builds_, not the one it replaces,
and it is left corrected rather than deleted because getting the superseded
design wrong is the easiest way to justify a change for the wrong reason.

## Decision

**Every tier counts in SQLite, in one transaction over one set of rows. Process
memory keeps only the refusals that store has already issued.**

**1. `consume` takes a list of tiers rather than one window.** One
`BEGIN IMMEDIATE`, one prune, one `COUNT` per tier, and — if every tier passes —
one insert.

**Every tier is evaluated, and the refusal carries the latest expiry among the
full ones.** A caller is allowed again only when the last window clears, so
answering with the first tier that happens to be full advertises a wait another
tier is still holding — and a client obeying `Retry-After` exactly earns a
second 429, which is the one promise this header makes
([0014](0014-do-not-trust-forwarding-headers.md)). With the shipped numbers that
is reachable in about ten requests: five spread across an hour and five inside a
minute leaves both windows full, and the burst tier's 55-second answer left 540
seconds of the hourly one still to run.

The tier reported is the binding one rather than the first asked, because it is
the window the caller is actually waiting out and so the only name that agrees
with the wait they were given. It is also the more useful of the two for triage,
since `hourly` means a patient caller and `burst` a hasty one
([../monitoring.md](../monitoring.md#a-rate-limiter-tripping)). Order breaks
ties, and nothing else.

Both windows counting the same rows is what makes this cheaper than it sounds:
the burst tier adds a second `COUNT` over an already-open transaction and no
extra write at all. The properties that fall out of the single insert are worth
naming, because each was a separate piece of bookkeeping before:

- **A request refused by any tier is recorded by none of them**, so a caller
  cannot spend their hourly allowance on requests that were never served. 0016
  arranged this by consulting the tiers in sequence; now it is structural.
- **The prune uses the widest window.** Pruning at the burst tier's 60 seconds
  would delete the history the hourly tier is made of, which is the one
  mistake in this design that would look correct and test green against any
  single-tier case.

**2. Process memory holds refusals, not counts.** `_RATE_LIMIT_REFUSALS` maps a
bucket key to the deadline the store issued and the tier that issued it. A
second request from a refused caller inside that deadline is answered without
opening the database.

This is sound in the one direction that matters: **the cache can only refuse a
caller the store is already refusing.** The deadline is the store's own answer
to "when could this be allowed", and until the request that filled the window
leaves it, the count cannot fall. So a stale entry is a wasted disk hit, never a
wrongly refused supporter. The one way it over-refuses is `reset()` clearing the
table under a worker that has not forgotten — a hand or test operation, never
part of serving a request.

That claim survives only if the deadline is **exact**. `Retry-After` is rounded
up, because a client has to be able to obey it literally and a truncated value
sends them back inside the window ([0014](0014-do-not-trust-forwarding-headers.md)).
Rounding is the right answer for the header and the wrong one for the cache: a
deadline built from it holds the refusal up to a second past the moment the
window clears, which is the cache inventing a refusal rather than repeating one.
So `Refusal` carries the exact `expires_in` and exposes `retry_after` as the
rounded view of it, and the two consumers take the one they need.

It is also the shape the old tier wanted to be. A flood costs a store round trip
each time the shared window admits another request rather than one per request,
and unlike a counter it engages during the flood rather than before it.

**Not one per window** — the entry expires with the row that frees the window,
and a sustained flood then spends two round trips per freed slot: one that is
admitted and recorded, and one that is refused and re-arms the cache. So the
cost is on the order of twice the tier's limit per window per worker, against
one per request without it. At the shipped 5/60s that is roughly ten round trips
a minute per worker under a flood of any size, which is the saving worth
quoting. Per worker because this dictionary is a module global like everything
else in a Passenger process — the difference from the counter it replaces is
that being process-local costs disk here rather than correctness.

**3. A fallback burst counter runs while, and only while, the store is
unreachable.** Both tiers are one call now, so without this a database the app
cannot read would leave the form endpoints unlimited for the length of the
incident — on endpoints that send mail from the campaign's own SMTP account,
which is the outcome 0009 wanted a limiter for at all.

`_DEGRADED_BURST_COUNTS` is 0009's original per-worker deque, kept for the one
case where it is still the best answer available. It is exactly as weak as it
always was — a real ceiling of `5 x N` — and that is the point: the choice here
is not between a correct limit and a weak one, it is between a weak one and
none.

Three properties keep it from quietly becoming a second limit:

- **It counts only while degraded**, so nothing is written to it while the
  store is answering. A counter kept warm through healthy traffic would be a
  per-worker limit running invisibly in parallel with the real one, which is the
  defect this record exists to remove.

  It is not, however, wiped when the store recovers, and an incident inside a
  minute of the last one therefore inherits what that one counted. That is
  deliberate: those requests really were served by this worker inside the burst
  window, so counting them is the accurate reading of "five per sixty seconds",
  and clearing on recovery would hand a flapping store ten. The entries age out
  on the window like any other count, so the dictionary empties itself within a
  window of the incident ending.

- **It stops being consulted the moment the store answers again**, including
  about the requests it allowed and never recorded. A caller it had just refused
  is served, because the shared tiers have never seen them. The store is
  authoritative whenever it can speak.
- **Its refusals are never written to the refusal cache.** That cache is allowed
  to refuse people precisely because the store issued its deadlines; a guess made
  by one worker during an outage does not carry that warrant.

For this to be possible at all, `consume` has to distinguish "allowed" from "I
could not count", which it did not — both were `None`. It now returns a
`Verdict`, and the two no-news cases are named `ALLOWED` and `UNAVAILABLE`. The
distinction is easy to lose in a refactor and the loss is silent, so it is
pinned at both failure paths in the store, including the mid-transaction one
that every unusable-file test misses.

**4. A database that just failed is not asked again for ten seconds.**
`_connect` carries a five-second busy timeout, so without this the fallback
above is reached only by paying that timeout on every request — including the
requests it is about to refuse, which is precisely a flood. Each one holds a
Passenger worker for five seconds and writes an exception to the log, which
turns a database incident into the worker pile-up [0018](0018-cap-concurrent-submissions.md)
exists to prevent, arriving on the path that was supposed to be the cheap one.

`STORE_BACKOFF_SECONDS` lives in the store rather than in `app.py` so every
entry point is covered by construction. `acquire` holds the same timeout against
the same file, and a submission would otherwise pay it again on its way into the
concurrency cap — the fix landing on the case in front of you while its siblings
keep the hole open. Each keeps its own fail-open answer; what it skips is the
wait before reaching it.

**`release` is the deliberate exception, and it is not symmetric with the
others.** Skipping it leaves a row that `acquire` counts against the cap until
the TTL expires — 270 seconds by default — so a ten-second incident became
minutes of `503`s after the database came back, and on `/health/deep`, whose
entire budget is two slots, the probe refusing itself. That is a worse outcome
than the wait it avoided, and it is caused by the avoidance rather than by the
incident.

So `acquire` marks the tokens it hands back without recording anything, and
`release` drops those without a round trip while still attempting a real one.
That keeps the common case free — during an incident `acquire` is not recording,
so its tokens cost nothing to release — and bounds the waits actually paid by
how many slots exist: a dozen submissions and two probes, once each, at the end
of a request whose work is already done.

There is no health signal to wait for. The first call after the window simply
tries, so one request per worker per window probes and the rest are answered
from the last failure. The cost is that **recovery is delayed by up to the
window**: for ten seconds after the database is readable again, a worker that
has not probed is still on its per-worker fallback.

**5. `RATE_LIMIT_MAX_BUCKETS` becomes `RATE_LIMIT_MAX_TRACKED_KEYS`,** and now
bounds both in-process dictionaries. The cap and its low-water mark are
unchanged. The refusal cache evicts the entries nearest their deadline, costing
a store round trip and nothing else. The fallback counters are cleared
wholesale instead, which is blunt on purpose: they only hold anything during an
incident, and a reset allowance is the same failure selective eviction would
have caused one key at a time.

## The property, not the three routes to breaking it

Three separate defects on this branch were the same broken promise: **a client
that honours `Retry-After` exactly must not be refused again**, which
[0014](0014-do-not-trust-forwarding-headers.md) established and which is the
only thing the header actually says. Truncating the value broke it. A window
holding more than its limit broke it. Answering with the first full tier while a
later one still held broke it. Each was found in review after the previous fix
had shipped, and each got a test for its own route.

Routes are not the unit worth testing here. `test_every_refusal_advertises_a_wait_that_is_actually_enough`
generates three hundred states from a fixed seed — arbitrary row patterns,
including windows holding more than their limit, and both tier orders — and
asserts the property directly on every refusal. It catches all three of the
defects above when their fixes are reverted, and would have caught the second
and third before they were written.

It also asserts that the generator still produces refusals. A generative test
that stops generating the interesting case asserts nothing while continuing to
pass, which is the failure mode a property test is most likely to rot into.

## Consequences

- **The documented limit is the enforced limit.** 5 per 60 seconds, per client
  per endpoint, across every worker and across deploys — the same guarantee the
  hourly tier has had since 0016. Every doc that described the burst tier as
  per-worker is corrected in the same commit as this record.
- **An unreachable store degrades to `5 x N`, which is what the burst tier was
  enforcing before this record.** The hour-long tier has no fallback and cannot
  have one — process memory could never hold it, which is why 0016 moved it in
  the first place — so a store outage still means an unbounded hourly
  allowance, bounded only by the burst window underneath it. That is a real
  weakening and it is where 0016's reasoning still governs: refusing a real
  volunteer is the worse failure. The honeypot, the origin check and
  Cloudflare's rules are unaffected either way.
- **A store outage is visible only in the logs, and now less loudly.** Every
  failure logs, but nothing pages, and the 429s the fallback issues are
  indistinguishable from ordinary burst refusals in telemetry — same
  `rate_limit.tier`. The backoff also cuts the logging from once per request to
  once per worker per window, which is the right trade for a log nobody is
  tailing but does mean an incident is quieter. Making the degraded mode legible
  to New Relic needs an attribute and an alert to read it, which is a monitoring
  decision rather than part of this one.
- **The burst tier will refuse more traffic than it used to**, because it is now
  doing what it says. The alert threshold in
  [../monitoring.md](../monitoring.md#the-rate-limit-thresholds-are-counted-in-a-11-sample) was calibrated
  against recorded refusals while the effective ceiling was `5 x N`, so expect
  the burst condition to be noisier and re-measure before trusting the number.
  The hourly condition may go slightly quieter for the opposite reason: a caller
  bursty enough to leak past `5 x N` used to reach it and be refused there, and
  is now stopped a tier earlier. That is the campaign-visible condition, so the
  change is worth knowing — the patient caller it was sized against is
  unaffected either way.
- **A burst refusal now costs a store round trip where it used to cost
  nothing.** Only the burst tier changes here: an hourly refusal already queried
  SQLite on every attempt, because reaching that tier at all meant the burst
  tier had allowed the request. The refusal cache bounds the new cost at roughly
  twice the tier's limit per window per worker — the entry expires with the row
  that frees the window, so a sustained flood re-arms it once per freed slot
  rather than once per window — against one round trip per request with no cache
  at all. Paid only by callers being refused, and per worker, since the cache is
  process-local.
- **Nothing to migrate, and the deploy order does not matter.** The schema is
  unchanged — same `hits` table, same columns, same rows — so an old worker and
  a new one can serve out of the same file during a restart. The old one simply
  does not enforce the burst window in SQLite while it lives. The renamed
  variable is not set in production; were it set, the new name would be unread
  and the cap would fall back to its default of 10,000.
- **The rate limiter stops being a place a limit can hide; the process does
  not.** The defect in #158 was possible because a control described in four
  documents lived in a module global whose scope nobody restated. What is left
  in memory here cannot be mistaken for the limit, because it holds no counts
  and the fallback that does is named for the condition it runs in.

  The same shape survives elsewhere and this record does not close it.
  `_EDGE_LOG_STATE` throttles the unproxied-caller warning "at most once per
  window" ([0020](0020-authenticate-the-origin-path.md)) out of a module global,
  so the real rate is once per window _per worker_ and the rollout's audit step
  reads `suppressed` counts fragmented across them. `_deep_health_cache` is the
  same construction, but [0017](0017-origin-trust-boundary-and-health-probe-cache.md)
  states its scope outright and sizes the consequence, which is the difference
  between a per-worker cache that is documented and one that is not.

## Alternatives considered

- **Accept it and correct the documentation.** Cheapest and honest, and it was a
  real option: the hourly tier is genuinely cross-worker and does bound
  sustained abuse. Declined because the burst tier is the control that answers a
  double-click and a scanner sweep, and `5 x N` floats _upward_ with load —
  loosening exactly when traffic is heaviest.
- **Lower the per-worker limit to compensate.** Setting 2 approximates 6
  effective at three workers. Same objection, worse: the effective limit still
  floats with worker count, and now the documented number is wrong in a second
  way.
- **Rate-limit at Cloudflare's edge instead.** The option that did not exist
  when 0009 chose process memory, and the first thing to check now that
  [0019](0019-cloudflare-in-front.md) puts an edge in front. Checked against the
  plan the zone is actually on — `Free Website`, confirmed through the API — and
  it cannot express either tier:

  | Parameter                | Free plan                     |
  | ------------------------ | ----------------------------- |
  | Number of rules          | **1**                         |
  | Counting characteristics | **IP only**, preset           |
  | Counting period          | **10 s only**                 |
  | Mitigation timeout       | **10 s only**                 |
  | Action                   | **Block only** (no challenge) |

  One rule for the whole zone against three scopes limited separately here, no
  60-second window, no hour-long window. Three further objections survive an
  upgrade, so this is not merely a billing question:

  - **Cloudflare's counters are per data centre.** Its own documentation says
    rate limiting rules "are not designed to allow a precise number of requests
    to reach your origin server" and points at the per-data-centre scope of the
    counters. That is the same class of defect as this one, sharded by colo
    instead of by worker — an odd thing to adopt as the fix for it.
  - **The edge cannot see the direct-to-origin path.** 0019 records that
    `mail.voteforjulia.com` publishes the origin address, so a caller with a
    `Host:` header skips Cloudflare entirely. [0020](0020-authenticate-the-origin-path.md)
    is the answer to that, and it fails open until armed; a limiter behind it is
    what makes it defence in depth rather than a single wall.
  - **It is a fifth drift surface.** The custom rules, the Transform Rules,
    `monitoring/`, branch protection, and now a tuned number living only in a
    dashboard. The existing edge rules are stable predicates; a threshold is
    not.

  What the edge _is_ good for is the volumetric case the origin cannot answer
  cheaply — one free rule blocking, say, 5 POSTs per 10 seconds saves spawning a
  worker at all. That is a different control from this one and is not decided
  here.

- **Redis, or a service with real shared counters.** 0009 declined it on a
  shared host and that has not changed. SQLite in `tmp/` has been the
  cross-worker store since 0016 and this decision buys nothing more than putting
  one more counter in it.
