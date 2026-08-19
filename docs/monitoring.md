# Monitoring

What watches the site, what will page you, and how to tell a real outage from a
false alarm.

Why it is set up this way is [ADR-0013](adr/0013-server-side-apm.md) (and
[ADR-0011](adr/0011-browser-side-observability.md), which it supersedes). The
agent's environment variables and the host's resource limits are in
[hosting.md](hosting.md#new-relic-agent-environment).

## The account

Everything lives in New Relic account **8127277**. Three things report into it:

| Source         | Reports as              | Configured in                                 |
| -------------- | ----------------------- | --------------------------------------------- |
| Browser agent  | `voteforjulia`          | [src/lib/newrelic.ts](../src/lib/newrelic.ts) |
| Production API | `voteforjulia-api`      | cPanel env vars on the `api` app              |
| Test API       | `voteforjulia-api-test` | cPanel env vars on the `api_test` app         |

The browser agent's licence and application IDs are public by design and live in
client code. The APM licence key is an **ingest** key set per app in cPanel —
not the `NRAK-` user key the source map upload uses. They are different
credentials and the agent fails silently with the wrong one.

## Configuration lives in this repo

New Relic has no export-to-git story, so the definitions are kept here by hand:

- **[monitoring/dashboard.json](../monitoring/dashboard.json)** — the "Vote for
  Julia — Site Health" dashboard, 20 widgets across two pages. Re-import via
  Dashboards → Import dashboard.
- **[monitoring/alerts.graphql](../monitoring/alerts.graphql)** — the synthetic
  monitors, the alert policy, and its three conditions, as NerdGraph mutations.

**These drift.** Nothing syncs them; editing a widget in the UI does not update
the file. If you change something in New Relic, change it here too, or the next
person to need it rebuilds from a stale copy. To pull the live dashboard back
down, use the `get_dashboard` NerdGraph query on the dashboard's GUID — note it
omits widget `layout`, so merge rather than overwrite.

There is also an older `voteforjulia` dashboard from 2026-06-02, predating this
setup and not tracked here.

## What is watched

### Synthetic monitors

Both probe `/health/deep`, which unlike `/health` actually authenticates against
SMTP and reads spreadsheet metadata — see
[architecture.md](architecture.md) for why there are two health endpoints.

| Monitor                              | Target     | Period | Alerts? |
| ------------------------------------ | ---------- | ------ | ------- |
| `voteforjulia-api /health/deep`      | production | 15 min | **yes** |
| `voteforjulia-api-test /health/deep` | test       | 30 min | no      |

**The periods are a billing constraint, not a tuning choice.** Both were
lengthened on 2026-08-10 — production from 5 min, test from 15 — because
5-minute checks ran over the plan's budget. Two things follow, and both are
easy to miss:

- **The alert's aggregation window has to track the period.** See the
  [alert conditions](#alert-conditions) below; changing one without the other
  stops the alert firing at all.
- **`/health/deep` has its own rate-limit allowance** (30/hour, against the
  form endpoints' 10) so a monitor can never 429 itself into a false alert.
  `test_health_deep_allowance_fits_the_synthetic_monitor` in
  [api/test_app_pipeline.py](../api/test_app_pipeline.py) fails if a future
  period change outgrows it. Raise the allowance before shortening the period.
- **Its results are cached for 60 seconds**
  ([ADR-0017](adr/0017-origin-trust-boundary-and-health-probe-cache.md)), so the
  endpoint cannot be used as an amplifier against SMTP and Sheets. At a 15- or
  30-minute period every scheduled check still runs the real probes, and the
  `Age` response header says which it got — `0` means the probes ran for that
  request. **Keep any future period comfortably above the TTL**: a period below
  it would have the monitor grading a cached answer, and an outage could clear
  and re-alert against a result nothing re-measured.

**The test monitor is deliberately not wired to the policy.** Every PR deploy
restarts `api_test` and it briefly fails. Alerting on that would train you to
ignore alerts, which is worse than not having them.

Two details in the monitor config that look optional and are not:

- **`shouldBypassHeadRequest: true`** — a SIMPLE monitor sends `HEAD` by
  default, which returns no body, and the body is the entire check.
- **The validation string is `"status":"ok"` with no space.** Flask's `jsonify`
  emits compact JSON. A copy taken from pretty-printed output never matches.

### Alert conditions

All three sit on the **`voteforjulia — API`** policy (`PER_CONDITION`, so an
SMTP outage and a Sheets outage open separate issues rather than collapsing into
one).

Read back from the account on 2026-08-10, all three exist and are enabled:

| Condition                                 | ID         |
| ----------------------------------------- | ---------- |
| Policy `voteforjulia — API`               | `7831111`  |
| API dependency check failing (production) | `64880222` |
| API error rate above 5% (production)      | `64880233` |
| API not reporting (production)            | `64880240` |

**Conditions existing is not the same as being alerted.** A policy with no
notification workflow and destination raises issues that sit in the UI and reach
nobody, which looks identical to "nothing has gone wrong". The account had **no
issues at all** as of 2026-08-10, which is consistent both with nothing breaking
and with the conditions never having evaluated — so it is not evidence either
way. Confirm a workflow exists (Alerts → Workflows) and send yourself a test
notification; that is the only check that proves the path end to end.

| Condition                    | Fires when                                    |
| ---------------------------- | --------------------------------------------- |
| API dependency check failing | the production synthetic fails twice in a row |
| API error rate above 5%      | >5% of transactions error for 5 minutes       |
| API not reporting            | no transactions for 30 minutes                |

The third exists because **silence is not a signal**. If the worker dies or the
agent crashes, error _rate_ has no data to be high on, so it uses
`fillOption: STATIC, fillValue: 0` to make absence look like zero throughput.

**Two of the three are coupled to the synthetic's period**, and neither
dependency is visible from the New Relic UI. Lengthening the monitor to 15
minutes on 2026-08-10 made the values in `alerts.graphql` wrong, and they were
corrected in the same change — but **whether the live conditions were ever
updated has not been established**, because a condition's signal block cannot be
read back through the read-only MCP server. Check the two below in the UI before
trusting either.

- **"API dependency check failing" — keep `aggregationWindow` equal to the
  period and `thresholdDuration` at twice it.** At the current 15 minutes that
  is 900 and 1800. The condition fills empty windows with 0 and requires _every_
  window in `thresholdDuration` to breach, so a window shorter than the period
  guarantees a filled zero between checks and the breach can never be sustained.
  It then fails silently, which is the worst way for an alert to fail. Detection
  now takes about 30 minutes — the cost of the longer period, not a choice.
- **"API not reporting" needs six consecutive empty 5-minute windows**, and the
  synthetic is most of this API's baseline traffic. At a 15-minute period a
  check lands in every third window, so the longest run of zeros is two. A
  30-minute period would make that run five against a threshold of six, and the
  condition would start flapping. Lengthen `thresholdDuration` alongside any
  further increase.

## When something fires

### Is it real?

**Check whether every location failed at once.** This is the fastest
discriminator and it is the one thing that is not obvious from the UI:

```
SELECT monitorName, result, locationLabel, responseStatus
FROM SyntheticCheck WHERE result = 'FAILED' SINCE 2 hours ago
```

- **All locations failed within the same minute** → the endpoint really is
  broken. Nothing about a genuine outage is location-specific.
- **One location failed while others passed** → nothing about the API is
  location-specific, so suspect something between the probe and the app. The
  known candidate is the
  [Imunify360 WAF](hosting.md#imunify360-waf-disabled), which challenges by
  source IP reputation and would flag the AWS ranges synthetics run from. A
  challenged request returns **HTTP 200** with a verification splash, so the
  status code looks healthy and only the response validation catches it — a
  false positive on a working API.

  **Every hostname it could affect has been excluded since 2026-08-15** — the
  2026-08-01 request this page credited until now covered
  `test.voteforjulia.com` alone, and the rest went on being challenged for two
  more weeks ([hosting.md](hosting.md#imunify360-waf-disabled)). So this should
  not happen now, which is what makes a single-location failure worth taking
  seriously as evidence the WAF is back rather than dismissing as noise.

### A 503 from the submission cap

`API error rate above 5%` counts these, deliberately — the site turning
supporters away is worth knowing about. Tell them apart from a genuine fault by
the log line, which names the cap:

```
/send-email refused: 12 submissions already in flight
```

That is not a bug report. It means twelve submissions were being served at once,
and the usual cause is SMTP or Sheets responding slowly enough that ordinary
traffic stacks up — so check `/health/deep` before looking at the form code at
all. Raising `MAX_CONCURRENT_SUBMISSIONS` is the wrong first move: the cap is
sized against the account's memory limit, and lifting it trades a shed
submission for an LVE fault that takes the whole account down.
See [ADR-0018](adr/0018-cap-concurrent-submissions.md).

### If it is real

`/health/deep` reports which dependency broke:

```
curl -s -D /dev/stderr https://api.voteforjulia.com/health/deep | jq
```

`-D /dev/stderr`, not `-D -`: the latter writes the headers to stdout, where
they reach `jq` ahead of the body and it dies on `HTTP/2 200` instead of showing
you the probe result.

Read `Age` from the headers first. Anything above `0` is a cached result, so a
green answer may predate the alert by up to a minute — wait it out and ask
again rather than concluding the alert was noise.

- `"smtp": "fail"` → the mail server or its credentials. This is the
  2026-07-30 failure mode; check `EMAIL_PASSWORD` for a `$`
  ([hosting.md](hosting.md#app-env-vars-must-not-contain-)) before anything else.
- `"sheets": "fail"` → service account credentials, or the sheet stopped being
  shared with it.

The response deliberately says only `fail` — the underlying exception text
quotes credentials, so it is never returned to an unauthenticated caller. The
detail goes to the agent instead, tagged with which dependency broke:

```
SELECT count(*) FROM TransactionError
WHERE appName = 'voteforjulia-api' FACET health.dependency, error.class
SINCE 24 hours ago
```

That attribute exists because the first version swallowed the exception
entirely: nine production 503s recorded a status code and nothing else, and
finding out they were all Sheets took an SSH session into
`~/api/stderr.log`. The full traceback is still there if the agent's copy is
not enough.

### Stale Sheets connections

The failure to expect, because it has already happened: `BrokenPipeError` from
Google Sheets. The client is cached for the worker's lifetime and its
keep-alive socket gets closed while idle, so the next call writes into a dead
connection.

Reads rebuild the client and retry once. **The append deliberately does not** —
a connection error surfaces while reading the response, which cannot be told
apart from a request the server already applied, so a retry could duplicate a
supporter's row. It clears the cached client and fails, which returns a 502 and
logs the raw body for recovery.

One useful side effect: `/health/deep` exercises the same cached client on every
probe, so a stale connection is often discovered and discarded before a real
submission meets it. Two things keep that a mitigation rather than a guard. The
cache is a module-level dict in
[sheets_service.py](../api/services/sheets_service.py), so it is **per Passenger
worker** — a probe refreshes only the worker that served it, and a submission
routed to any other worker still meets that worker's own idle socket. And
**lengthening the monitor's period widened the gap**: at the current 15 minutes
the window in which a submission can be the first caller to touch a dead socket
is three times what it was at 5.

### Turning it off

Clearing `NEW_RELIC_LICENSE_KEY` on an app and restarting disables the agent
without a deploy. That is the escape hatch if the agent itself ever becomes the
problem.

## Querying it

Some NRQL specifics for this account that cost time to rediscover:

- **`parseUrl()` is gated behind an unenabled beta flag.** Split environments
  with `FACET CASES (WHERE pageUrl LIKE ... AS '...')` instead.
- **One browser app holds production, test, and localhost traffic.** Filter with
  `WHERE pageUrl NOT LIKE '%localhost%' AND pageUrl NOT LIKE '%test.voteforjulia%'`,
  which is what every production widget in the dashboard does.
- **A deleted monitor's checks stay in `SyntheticCheck`.** An `API Health`
  monitor from the initial setup still has rows, so filter by `monitorName`.
- **Core Web Vitals are in seconds**, not milliseconds — an INP threshold of
  `0.2` is 200ms.
