# 0021. Alert on signals the host cannot drop

**Status:** Accepted
**Date:** 2026-08-19

Revisits the alerting built in [0013](0013-server-side-apm.md). That record
chose server-side APM and listed "alerting on synthetic failure and on APM error
rate" as a consequence. Half of that consequence turned out to rest on data this
host does not reliably deliver.

## Context

### The measurement

Read from account 8127277 on 2026-08-19, over the preceding seven days:

| Signal                               | Volume                |
| ------------------------------------ | --------------------- |
| `SyntheticCheck` for `/health/deep`  | 192/day, 100% SUCCESS |
| `Transaction` for `voteforjulia-api` | 1–11 per **6 hours**  |

The synthetic runs every 15 minutes from two locations, so 192 checks a day is
exactly right and every one of them succeeded. Each is an HTTP request the API
served. APM recorded about 3% of them.

### Why

Nothing is broken. The mechanism was already written down, one document over, as
a memory-management note rather than an observability one — from
[../hosting.md](../hosting.md#watch-worker-memory): this host "spawns them per
request and reaps them when idle", and `ps` at a quiet moment "returns _nothing
at all_".

The New Relic Python agent harvests on a 60-second cycle and registers with the
collector on a background thread. A worker that accepts one probe, answers it,
and is reaped seconds later never reaches a harvest, so what it recorded dies
with the process. Under sustained load workers live long enough to report, which
means **the loss is biased toward idle periods, not uniform** — and therefore no
fixed factor scales a recorded count back to a real one.

### What that broke

Two of the three live conditions were built on `Transaction`.

**`API not reporting` (`64880240`) was measuring worker lifetime.** It counted
transactions with empty windows filled to zero, on the reasoning that silence is
not a signal. The reasoning is right. The data source made it fire on healthy
days: it opened issue `6d261d33` on 2026-08-17 and was still open, acknowledged
and unclosed, two days later — raised during a stretch in which the synthetic
was 192/192 green.

**`API error rate above 5%` (`64880233`) was a bot detector.** It asked for
`percentage(count(*), WHERE error IS true)`. Two separate faults:

- The `error` intrinsic is set only when an exception reaches the agent
  (`newrelic` 13.4.0 sets it from `TransactionNode.errors`, populated by
  `notice_error`). A 503 from the submission cap and a 429 from either rate
  limiter are `jsonify` responses with a status code assigned. Nothing raises,
  so nothing was counted. [../monitoring.md](../monitoring.md) asserted the
  opposite — that the condition counted the cap's 503s "deliberately" — in the
  runbook section a reader reaches mid-incident.
- Over 30 days the only transactions carrying `error IS true` were **12 HTTP
  405s**, from bots probing with the wrong method. Against 266 recorded
  transactions that is 4.5%, against a 5% threshold.

A percentage was the wrong shape regardless. At 1–11 transactions per 6 hours, a
single bot probe inside a 60-second window is 100%.

### And the third condition was dead

The one condition not built on `Transaction` was not working either, for an
unrelated reason that only became visible once a write-capable credential made
`signal` readable. Read back on 2026-08-19, the live
`API dependency check failing` had:

|                     | Live    | Required at a 15-minute period |
| ------------------- | ------- | ------------------------------ |
| `aggregationWindow` | **300** | 900                            |
| `thresholdDuration` | **600** | 1800                           |

Those are the pre-2026-08-10 values, from when the monitor ran every 5 minutes.
`alerts.graphql` was corrected in the same change that lengthened the period.
**The live condition never was.**

The consequence is the silent failure [../monitoring.md](../monitoring.md)
had already described in the abstract, arrived at concretely. Checks land in one
900-second stretch out of every three; the other two windows fill with zero;
`thresholdOccurrences: ALL` over a 600-second duration needs two _consecutive_
300-second windows above threshold. Two consecutive breaching windows cannot
occur. **The production outage alert had been incapable of firing for nine
days**, on the single condition the whole policy exists for.

Two things are worth separating here. The drift itself is ordinary — a file was
corrected and the live system was not. What made it survive is that
`monitoring.md` had _already written down the exact mechanism_, flagged that the
live values were unverified, and named the check that would settle it; the check
just could not be run, because the read-only MCP server cannot return a
condition's `signal` block. The documentation was not missing. **The
verification was impossible, and "unverified" was allowed to stay unverified
indefinitely because nothing forced it.**

### The general shape

This is the third drift surface in this project, and the first one where the
drift is between a document and physics rather than between two documents. The
condition definitions in `monitoring/alerts.graphql` were internally consistent,
carefully commented, and coupled correctly to the monitor's period. They were
also querying an event stream that arrives ~3% complete, and nothing in the
definition, the UI, or the runbook said so.

The tell was available the whole time and nobody looked: a monitor at 192
successes a day and an APM app at single-digit transactions per six hours cannot
both be describing the same endpoint.

## Decision

**Alert on `SyntheticCheck` wherever the question can be asked of it, and use
absolute counts rather than percentages everywhere else.**

Concretely:

- **`API not reporting` → `Synthetic monitor not running`.** Same question — is
  anything still watching? — asked of the synthetic's own checks. Those are
  produced by New Relic's infrastructure, not by a process this host reaps, so
  an empty window means the monitor genuinely stopped: disabled, out of plan
  budget, or a New Relic outage.
- **`API error rate above 5%` → `API serving 5xx`.** Reads
  `numeric(response.status) >= 500` directly, so it needs no exception and
  catches the cap's 503s that the old condition provably missed. An absolute
  count, sustained, rather than a ratio.
- **Rate-limit trips get a custom attribute**, `rate_limit.tier` plus
  `rate_limit.scope`, recorded in `api/app.py` at the single point that returns
  a 429. Both tiers return identical responses, so without it a burst refusal
  and an hourly refusal are indistinguishable — and the hourly one is the only
  one worth waking up for.
- **Thresholds on the rate-limit conditions are declared as guesses** in the
  file, to be tuned after a week of data. Given a biased sampling loss of
  unknown size, a derived-looking number would be false precision, and this
  repository has been bitten by exactly that before (`INFLIGHT_TTL_SECONDS`).

**Absolute counts over percentages** is the part that generalises. A ratio
implies a denominator the host cannot supply. A count claims only "at least this
many", which is what a sample honestly supports.

## Consequences

- **Two conditions must be deleted, not edited.** Their IDs are recorded in
  `monitoring.md`; the replacements get new ones.
- **The rate-limit conditions cannot be created until `rate_limit.tier` is
  deployed and reporting.** A NRQL condition on an attribute nothing emits is
  not an error — it evaluates to nothing and sits green, which is
  indistinguishable from healthy. This is the same silent-failure mode as the
  aggregation-window trap in [0013](0013-server-side-apm.md)'s wake, arriving
  from a new direction.
- **APM keeps its diagnostic value and loses its alerting value.** The
  `health.dependency` attribute on `TransactionError` is still how a 503 gets
  attributed to SMTP or Sheets after the fact; that use never needed
  completeness. Only the conditions moved.
- **The 3% figure is not stable** and should not be treated as a constant. It is
  a function of traffic shape and Passenger's idle timeout, neither of which is
  pinned.
- **`/health` and `/health/deep` remain the ground truth for "is it up".** This
  ADR moves alerting closer to them rather than adding anything new to trust.
- **A fix for the sampling itself was considered and rejected.**
  `NEW_RELIC_STARTUP_TIMEOUT` would make each worker block until the agent
  registers, which on a host that spawns a worker per request means paying
  registration latency on every cold request — trading a monitoring gap for a
  user-visible one. Not worth it for a signal `SyntheticCheck` already covers.
